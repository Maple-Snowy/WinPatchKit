"""模块配置导入与加载。

- 手动导入 import_config(): 把用户挑选的 .toml 复制进数据目录/configs/
- 便捷导入 auto_import():  启动时把"工具同级目录"(或设置的 auto_import_dir)
                           里的 .toml 自动搬进 configs/，返回被导入的文件
- 加载 list_configs() / load_config(): 从 configs/ 读取并解析为 ModuleSpec

"是否同一配置"的判定依据是**模块ID（[module].id）**，与文件名无关：
- 已存在相同 id 的配置时：
    · 手动导入  -> 覆盖（以最新导入为准，可更换文件名）
    · 便捷导入  -> 跳过（视为已导入，避免每次启动重复处理）

所有配置统一落在数据目录/configs/，工具本体不携带任何配置。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List

from . import datadir
from core import config as cfig


def _tool_dir() -> Path:
    """工具运行所在目录（main.py 所在目录）。"""
    return Path(__file__).resolve().parent.parent


def _is_toml(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() == ".toml"


def _read_id(path: Path) -> str:
    """读取一个 toml 的模块ID；解析失败返回空串。"""
    try:
        return cfig.load_module(str(path)).id
    except Exception:
        return ""


def _existing_by_id() -> Dict[str, Path]:
    """数据目录/configs/ 下 {模块ID: 文件路径}。"""
    out: Dict[str, Path] = {}
    for p in datadir.configs_dir().iterdir():
        if _is_toml(p):
            mid = _read_id(p)
            if mid:
                out[mid] = p
    return out


def import_config(src) -> Path:
    """手动导入：把单个 .toml 导入数据目录/configs/。

    以模块ID判重：若已存在相同 id 的配置则覆盖（删旧放新，文件名以新文件为准）；
    否则新增。返回 configs/ 下的目标路径。
    """
    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(f"配置不存在: {src}")
    if src.suffix.lower() != ".toml":
        raise ValueError(f"只支持 .toml 配置: {src.name}")

    mid = _read_id(src)
    if not mid:
        raise ValueError(f"配置缺少有效 id（模块ID）: {src.name}")

    cfg_dir = datadir.configs_dir()
    dest = cfg_dir / src.name
    # 同一 id 已存在（无论文件名是否相同）-> 覆盖
    existing = _existing_by_id().get(mid)
    if existing is not None and existing != dest:
        existing.unlink()
    shutil.copy2(src, dest)
    return dest


def auto_import(src_dir=None, move: bool = True) -> List[Path]:
    """便捷导入：扫描 src_dir（默认=工具目录）中的 .toml，搬进 configs/。

    move=True  : 从源目录移走（用后即归位，避免下次重复导入）
    move=False : 仅复制到 configs/，保留源文件
    以模块ID判重：configs/ 已有相同 id 的配置则跳过（视为已导入）。
    返回本次实际导入（新增）的配置路径列表。
    """
    base = Path(src_dir) if src_dir else _tool_dir()
    if not base.is_dir():
        return []
    cfg_dir = datadir.configs_dir()
    imported: List[Path] = []
    for f in sorted(base.iterdir()):
        if not _is_toml(f):
            continue
        mid = _read_id(f)
        if not mid:
            continue  # 无有效 id 的配置不自动导入（避免引入无效模块）
        if mid in _existing_by_id():
            continue  # 同一配置已存在，跳过
        dest = cfg_dir / f.name
        if move:
            shutil.move(str(f), str(dest))
        else:
            shutil.copy2(f, dest)
        imported.append(dest)
    return imported


def delete_config(file, permanent: bool = False) -> str:
    """删除一个模块配置。

    permanent=False : 软删除——移入数据目录/trash/（同名冲突时加序号），可恢复。
    permanent=True  : 永久删除——直接 unlink。
    返回一句话说明（供 GUI 提示）。不触碰 backups/（备份独立保留）。
    """
    p = Path(file)
    if not p.is_file():
        raise FileNotFoundError(f"配置不存在: {p.name}")
    if permanent:
        p.unlink()
        return f"已删除: {p.name}"
    trash = datadir.trash_dir()
    dst = trash / p.name
    n = 1
    while dst.exists():
        dst = trash / f"{p.stem}_{n}{p.suffix}"
        n += 1
    shutil.move(str(p), str(dst))
    return f"已移至回收站: {p.name}"


def export_configs(files, dest_dir) -> List:
    """把选中的 .toml 配置复制到 dest_dir。返回 [(文件名, 目标路径), ...]。"""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    done = []
    for f in files:
        src = Path(f)
        if not src.is_file():
            continue
        shutil.copy2(str(src), str(dest / src.name))
        done.append((src.name, str(dest / src.name)))
    return done


def examples_dir() -> Path:
    """项目自带的模块目录（<项目根>/examples），多级子目录均可放置 .toml。"""
    return _tool_dir() / "examples"


def config_files() -> List[Path]:
    """列出所有 .toml 模块配置。

    测试阶段：递归扫描项目 examples/（含多级子目录）。
    examples/ 不存在或为空时，回退到数据目录/configs/（旧行为）。
    """
    ex = examples_dir()
    if ex.is_dir():
        files = sorted(p for p in ex.rglob("*.toml") if _is_toml(p))
        if files:
            return files
    d = datadir.configs_dir()
    return sorted(p for p in d.iterdir() if _is_toml(p))


def load_config(path):
    """从一个 .toml 路径加载 ModuleSpec（不解析 target 相对路径）。"""
    return cfig.load_module(str(path))