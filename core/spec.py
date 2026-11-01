"""纯数据模型：从 TOML 载入的 PatchSpec / ModuleSpec。

本文件只做数据承载与从 dict 的构造，不含任何执行 / 写入逻辑。
策略对象（定位器 / 写入器）由 applier 依据 where.type / write.type 动态实例化。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Where:
    """定位配置（纯数据）。type 对应 core/locators 下某个策略文件的 Locator.type。"""
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Write:
    """写入配置（纯数据）。type 对应 core/writers 下某个策略文件的 Writer.type。"""
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatchSpec:
    id: str
    where: Where
    write: Write

    @classmethod
    def from_dict(cls, d: Dict[str, Any], index: int) -> "PatchSpec":
        pid = d.get("id") or f"patch_{index + 1}"
        where_raw = d.get("where")
        write_raw = d.get("write")
        if not isinstance(where_raw, dict) or "type" not in where_raw:
            raise ValueError(f"patch[{pid}]: 'where' 必须是含 type 的表")
        if not isinstance(write_raw, dict) or "type" not in write_raw:
            raise ValueError(f"patch[{pid}]: 'write' 必须是含 type 的表")

        where_params = {k: v for k, v in where_raw.items() if k != "type"}
        write_params = {k: v for k, v in write_raw.items() if k != "type"}
        return cls(
            id=pid,
            where=Where(type=where_raw["type"], params=where_params),
            write=Write(type=write_raw["type"], params=write_params),
        )


@dataclass
class ModuleSpec:
    name: str
    target: str
    id: str = ""                       # 模块ID：判断"是否同一配置"的唯一依据
    version: str = ""                  # 模块版本
    out: str = ""                      # 空则 = target 就地写
    base_dir: str = ""                 # 默认 patch 程序路径（target 相对它解析；空=相对 toml 目录）
    scope: str = ""                    # 适用范围（如"Os-Easy多媒体网络教室"），展示用
    patches: list = field(default_factory=list)

    # 说明：是否备份 / 备份文件名（后缀）不写进配置，由主程序在调用
    # applier.run(..., backup=, backup_ext=) 时决定。这样避免每次 apply
    # 都产生重复备份，且能保证只备份"原始文件"一次。

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModuleSpec":
        m = d.get("module")
        if not isinstance(m, dict):
            raise ValueError("TOML 缺少 [module] 表")
        name = m.get("name")
        target = m.get("target")
        mod_id = str(m.get("id", "")).strip()
        version = str(m.get("version", "")).strip()
        if not name:
            raise ValueError("[module] 缺少 name")
        if not target:
            raise ValueError("[module] 缺少 target")
        if not mod_id:
            raise ValueError("[module] 缺少 id（模块ID，用于判断是否同一配置）")

        patches = []
        for i, pd in enumerate(m.get("patches", [])):
            patches.append(PatchSpec.from_dict(pd, i))

        out = m.get("out") or ""
        base_dir = str(m.get("base_dir", "")).strip()
        scope = str(m.get("scope", "")).strip()
        return cls(
            name=name,
            target=target,
            id=mod_id,
            version=version,
            out=out,
            base_dir=base_dir,
            scope=scope,
            patches=patches,
        )