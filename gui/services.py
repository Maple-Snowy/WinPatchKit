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
import shutil
import sys
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


@dataclass
class PatchDetail:
    """单个 patch 点的探测结果（供详情弹层展示）。"""
    id: str
    offset: int
    status: str          # 'ok' / 'fail' / 'skip'
    message: str


@dataclass
class ModuleDetail:
    """模块详情弹层的数据源：基本信息 + 逐 patch 点探测。"""
    module_id: str
    name: str
    version: str
    target: str
    target_exists: bool
    status: str
    patches: List[PatchDetail] = field(default_factory=list)


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
    """探测全部模块状态（供后台线程调用）。多线程并行，模块多时提速。"""
    if not infos:
        return {}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex:
        pairs = list(ex.map(lambda i: (i.id, _probe_one(base_dir, i)), infos))
    return dict(pairs)


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


def preview_many(base_dir: str, infos: List[ModuleInfo]) -> List[ApplyOutcome]:
    """dry-run 预览：逐 patch 点探测但绝不落盘、不备份。供「预览」按钮。"""
    out: List[ApplyOutcome] = []
    for i in infos:
        if i.parse_error:
            out.append(ApplyOutcome(i.id, False, False, "配置解析失败", [], i.parse_error))
            continue
        try:
            spec = modules.load_config(i.file)
        except Exception as e:
            out.append(ApplyOutcome(i.id, False, False, "配置解析失败", [], str(e)))
            continue
        if not base_dir:
            out.append(ApplyOutcome(i.id, False, False, "未设置基准目录", [],
                                    "请先在顶部指定目标文件基准目录"))
            continue
        spec = cfig.resolve_base(spec, base_dir)
        if not os.path.isfile(spec.target):
            out.append(ApplyOutcome(i.id, False, False, "目标文件不存在", [],
                                    os.path.basename(spec.target)))
            continue
        report = applier.run(spec, write=False)
        lines = []
        for r in report.results:
            flag = "SKIP" if r.skipped else ("OK  " if r.ok else "FAIL")
            off = f"@0x{r.offset:X}" if r.offset >= 0 else ""
            lines.append(f"{flag}  {r.id:<20} {off}  {r.message}")
        okn = sum(r.ok for r in report.results)
        out.append(ApplyOutcome(i.id, report.all_ok, False,
                                f"[预览] {okn}/{len(report.results)} 将成功", lines))
    return out


# ---------------------------------------------------------------- 模块详情

def get_module_detail(base_dir: str, info: ModuleInfo) -> ModuleDetail:
    """构建模块详情（基本信息 + 逐 patch 点探测，不落盘）。供详情弹层。"""
    try:
        spec = modules.load_config(info.file)
    except Exception as e:
        return ModuleDetail(info.id, info.name or info.id, info.version,
                            info.target, False, ModStatus.PARSE_ERROR,
                            [PatchDetail("-", -1, "fail", str(e))])
    if not base_dir:
        return ModuleDetail(info.id, spec.name, spec.version, spec.target,
                            False, ModStatus.MISSING)
    spec = cfig.resolve_base(spec, base_dir)
    exists = os.path.isfile(spec.target)
    if not exists:
        return ModuleDetail(info.id, spec.name, spec.version, spec.target,
                            False, ModStatus.MISSING)
    report = applier.run(spec, write=False)
    patches = []
    for r in report.results:
        flag = "skip" if r.skipped else ("ok" if r.ok else "fail")
        patches.append(PatchDetail(r.id, r.offset, flag, r.message))
    return ModuleDetail(info.id, spec.name, spec.version, spec.target,
                        True, _status_from_report(report), patches)


def _status_from_report(report) -> str:
    total = len(report.results)
    ok = sum(r.ok for r in report.results)
    skipped = sum(r.skipped for r in report.results)
    if ok == total:
        return ModStatus.PATCHED if skipped == total else ModStatus.READY
    if ok == 0:
        return ModStatus.FAILED
    return ModStatus.PARTIAL


# ---------------------------------------------------------------- 删除 / 恢复 / 导出

def delete_module(file, permanent: bool = False) -> str:
    """删除模块配置（软删除进 trash / 永久删除）。返回提示文案。"""
    return modules.delete_config(file, permanent=permanent)


def restore_backup(base_dir: str, info: ModuleInfo, backup_ext: str) -> str:
    """用 backups/ 中的原始备份覆盖回目标文件。返回提示文案。"""
    try:
        spec = modules.load_config(info.file)
    except Exception as e:
        return f"配置解析失败：{e}"
    if not base_dir:
        return "未设置目标文件基准目录"
    spec = cfig.resolve_base(spec, base_dir)
    if not os.path.isfile(spec.target):
        return f"目标文件不存在：{os.path.basename(spec.target)}"
    bak = os.path.join(str(datadir.backups_dir()),
                       os.path.basename(spec.target) + backup_ext)
    if not os.path.isfile(bak):
        return f"没有可用备份：{os.path.basename(bak)}"
    shutil.copy2(bak, spec.target)
    return f"已恢复：{os.path.basename(spec.target)}"


def export_selected(files: List[str], dest_dir: str) -> List[Tuple[str, str]]:
    """把选中的 .toml 配置复制到目标目录。返回 [(文件名, 目标路径), ...]。"""
    return modules.export_configs(files, dest_dir)


def open_path(path: str) -> None:
    """在系统文件管理器中打开目录（仅 Windows）。异常静默。"""
    if not path or not os.path.isdir(path):
        return
    if os.name == "nt":
        os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')


def open_configs_dir() -> None:
    """在文件管理器中打开数据目录/configs/。异常静默。"""
    open_path(str(datadir.configs_dir()))


# ---------------------------------------------------------------- 设置

def get_settings() -> dict:
    return Settings.load().as_dict()


def save_settings(d: dict) -> None:
    s = Settings.load()
    for k in ("auto_import_dir", "target_base_dir", "backup", "backup_ext",
              "theme_mode", "theme_follow_system", "theme_seed"):
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
