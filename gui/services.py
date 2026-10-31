"""GUI 与引擎之间的桥接层（页面唯一数据源）。

core/ 是 OS 无关的 patch 引擎，app/ 负责数据目录 / 设置 / 导入。
本模块把它们的同步调用包装成 GUI 友好的「结构化结果」（dataclass），
让页面 (pages/) 只依赖这里暴露的对象与函数，不直接触碰
ApplyReport / ModuleSpec 内部字段——这是"展示与执行解耦"的接缝。

线程：这里所有函数都是同步阻塞（读文件 / 定位 / 写盘），由 GUI 用
page.run_thread 放进后台线程执行，避免卡住窗口。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from app import datadir, modules
from app.settings import Settings
from core import config as cfig
from core import applier


# ---------------------------------------------------------------- 状态枚举

class ModStatus:
    MISSING = "missing"            # 目标文件缺失
    READY = "ready"                # 可应用
    PATCHED = "patched"            # 已打补丁（幂等跳过）
    PARTIAL = "partial"            # 部分 patch 可定位
    FAILED = "failed"              # 全部 patch 失败
    PARSE_ERROR = "parse_error"    # 配置解析失败


# ---------------------------------------------------------------- 结构化结果

@dataclass
class ModuleInfo:
    id: str
    name: str
    version: str
    target: str
    file: str
    parse_error: str = ""


@dataclass
class StatusInfo:
    module_id: str
    status: str = ModStatus.MISSING
    ok: int = 0
    total: int = 0
    skipped: int = 0
    detail: str = ""


@dataclass
class ApplyOutcome:
    module_id: str
    ok: bool
    wrote: bool
    summary: str
    lines: List[str] = field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------- 读取模块

def list_modules() -> List[ModuleInfo]:
    """列出 configs/ 下所有模块；解析失败的也列出并标记 parse_error。"""
    out: List[ModuleInfo] = []
    for p in modules.config_files():
        name = os.path.basename(str(p))
        try:
            spec = modules.load_config(p)
            out.append(ModuleInfo(id=spec.id, name=spec.name,
                                  version=spec.version, target=spec.target,
                                  file=str(p)))
        except Exception as e:
            out.append(ModuleInfo(id=name, name=name, version="",
                                  target="", file=str(p), parse_error=str(e)))
    return out


# ---------------------------------------------------------------- 状态探测

def _probe_one(base_dir: str, info: ModuleInfo) -> StatusInfo:
    if info.parse_error:
        return StatusInfo(info.id, ModStatus.PARSE_ERROR, detail=info.parse_error)
    try:
        spec = modules.load_config(info.file)
    except Exception as e:
        return StatusInfo(info.id, ModStatus.PARSE_ERROR, detail=str(e))
    if not base_dir:
        return StatusInfo(info.id, ModStatus.MISSING, detail="未设置目标文件基准目录")
    spec = cfig.resolve_base(spec, base_dir)
    if not os.path.isfile(spec.target):
        return StatusInfo(info.id, ModStatus.MISSING,
                          detail=f"目标不存在: {os.path.basename(spec.target)}")
    report = applier.run(spec, write=False)
    total = len(report.results)
    ok = sum(r.ok for r in report.results)
    skipped = sum(r.skipped for r in report.results)
    if ok == total:
        if skipped == total:
            return StatusInfo(info.id, ModStatus.PATCHED, ok, total, skipped, "已打补丁")
        return StatusInfo(info.id, ModStatus.READY, ok, total, skipped, f"{ok}/{total} 可应用")
    if ok == 0:
        return StatusInfo(info.id, ModStatus.FAILED, ok, total, skipped, "无法应用")
    return StatusInfo(info.id, ModStatus.PARTIAL, ok, total, skipped, f"仅 {ok}/{total} 可定位")


def probe_all(base_dir: str, infos: List[ModuleInfo]) -> Dict[str, StatusInfo]:
    """探测全部模块状态（供后台线程调用）。"""
    return {i.id: _probe_one(base_dir, i) for i in infos}


# ---------------------------------------------------------------- 应用补丁

def apply_module(base_dir: str, info: ModuleInfo, backup: bool, backup_ext: str) -> ApplyOutcome:
    if info.parse_error:
        return ApplyOutcome(info.id, False, False, "配置解析失败", [], info.parse_error)
    try:
        spec = modules.load_config(info.file)
    except Exception as e:
        return ApplyOutcome(info.id, False, False, "配置解析失败", [], str(e))
    if not base_dir:
        return ApplyOutcome(info.id, False, False, "未设置目标文件基准目录", [],
                            "请先在“设置”中指定目标文件基准目录")
    spec = cfig.resolve_base(spec, base_dir)
    if not os.path.isfile(spec.target):
        return ApplyOutcome(info.id, False, False, "目标文件不存在", [],
                            os.path.basename(spec.target))
    report = applier.run(spec, write=True, backup=backup,
                         backup_dir=str(datadir.backups_dir()), backup_ext=backup_ext)
    lines = []
    for r in report.results:
        flag = "SKIP" if r.skipped else ("OK  " if r.ok else "FAIL")
        off = f"@0x{r.offset:X}" if r.offset >= 0 else ""
        lines.append(f"{flag}  {r.id:<20} {off}  {r.message}")
    okn = sum(r.ok for r in report.results)
    return ApplyOutcome(info.id, report.all_ok, report.wrote,
                        f"总计 {okn}/{len(report.results)} 成功", lines)


def apply_many(base_dir: str, infos: List[ModuleInfo], backup: bool,
               backup_ext: str) -> List[ApplyOutcome]:
    return [apply_module(base_dir, i, backup, backup_ext) for i in infos]


# ---------------------------------------------------------------- 设置

def get_settings() -> dict:
    return Settings.load().as_dict()


def save_settings(d: dict) -> None:
    s = Settings.load()
    for k in ("auto_import_dir", "target_base_dir", "backup", "backup_ext"):
        if k in d:
            s.set(k, d[k])
    s.save()


# ---------------------------------------------------------------- 导入

def import_files(paths: List[str]) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """手动导入多个 .toml。返回 (成功, 失败) 两个 (文件名, 说明) 列表。"""
    done: List[Tuple[str, str]] = []
    failed: List[Tuple[str, str]] = []
    for p in paths:
        name = os.path.basename(str(p))
        try:
            dest = modules.import_config(p)
            done.append((name, str(dest)))
        except Exception as e:
            failed.append((name, str(e)))
    return done, failed


def auto_import() -> List[str]:
    """便捷导入（扫描工具目录 / 设置目录）。返回被导入的文件名列表。"""
    return [p.name for p in modules.auto_import(move=True)]
