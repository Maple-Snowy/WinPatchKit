"""WinPatchKit 启动入口（main.py）。

职责（应用层，依赖 core）：
  1. 确保数据目录（%APPDATA%/WinPatchKit 等）存在
  2. 启动时执行"便捷导入"：把工具同级目录里的 .toml 自动搬进数据目录/configs/
  3. 提供子命令：list / import / apply / verify / info / path

用法:
  python main.py list                     列出已加载的模块
  python main.py import  a.toml b.toml    手动导入一个或多个配置
  python main.py apply   <module>         应用某模块（备份由设置决定，默认启用）
  python main.py verify  <module>         只校验能否定位，不落盘
  python main.py info    <target>         打印目标 PE 信息
  python main.py path                     打印数据目录路径

<module> 可填模块 name 或文件名（在 configs/ 中匹配）。
目标文件基准目录（相对 target）由 settings 的 target_base_dir 决定，
可用 --base 临时覆盖。
"""
from __future__ import annotations

import argparse
import os
import sys

# 使 `python main.py` 能 import core / app（均在项目根目录）
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import datadir, modules, settings          # noqa: E402
from app.settings import Settings                   # noqa: E402
from core import config as cfig                     # noqa: E402
from core import applier                            # noqa: E402


# ---------------------------------------------------------------- 启动逻辑

def startup(verbose: bool = True) -> None:
    """确保数据目录 + 加载设置 + 便捷导入（同级目录 .toml 自动搬入）。"""
    root = datadir.ensure_data_dir()
    if verbose:
        print(f"[data] {root}")
    # 便捷导入：默认扫工具所在目录；设置里可指定其它目录
    imported = modules.auto_import(move=True)
    if verbose and imported:
        print(f"[import] 便捷导入 {len(imported)} 个配置:")
        for p in imported:
            print(f"   + {p.name}")


def _find_config(name_or_id_or_file):
    """按 模块ID / name / 文件名 在 configs/ 中匹配，返回 Path。"""
    files = modules.config_files()
    # 1. 文件名精确匹配（xxx.toml 或 xxx）
    for p in files:
        if p.name == name_or_id_or_file or p.name == name_or_id_or_file + ".toml":
            return p
    # 2. 模块ID / name 匹配
    for p in files:
        try:
            spec = modules.load_config(p)
        except Exception:
            continue
        if spec.id == name_or_id_or_file or spec.name == name_or_id_or_file:
            return p
    raise FileNotFoundError(
        f"configs/ 中找不到模块 {name_or_id_or_file!r}"
        f"（按 id / name / 文件名均未命中，可用: list）"
    )


def _resolve(spec, base_override: str = ""):
    base = base_override or cfig_load_settings().target_base_dir
    return cfig.resolve_base(spec, base) if base else spec


def cfig_load_settings() -> Settings:
    return Settings.load()


# ---------------------------------------------------------------- 子命令

def cmd_list(args) -> int:
    files = modules.config_files()
    if not files:
        print("（configs/ 为空：请导入配置，或把 .toml 放到工具同级目录后启动）")
        return 0
    print(f"已加载 {len(files)} 个模块（{datadir.configs_dir()}）:")
    for p in files:
        try:
            spec = modules.load_config(p)
            desc = (f"{spec.name}  ->  {os.path.basename(spec.target)}\n"
                    f"{'':<42} id={spec.id}  ver={spec.version}")
        except Exception as e:
            desc = f"（解析失败: {e}）"
        print(f"  · {p.name:42} {desc}")
    return 0


def cmd_import(args) -> int:
    for src in args.files:
        dest = modules.import_config(src)
        print(f"  ✓ 导入 {os.path.basename(src)} -> {dest}")
    return 0


def cmd_apply(args) -> int:
    st = Settings.load()
    path = _find_config(args.module)
    spec = modules.load_config(path)
    spec = _resolve(spec, args.base)
    report = applier.run(
        spec, write=True,
        backup=st.backup, backup_dir=str(datadir.backups_dir()),
        backup_ext=st.backup_ext,
    )
    print(report.summary())
    return 0 if report.all_ok else 1


def cmd_verify(args) -> int:
    path = _find_config(args.module)
    spec = modules.load_config(path)
    spec = _resolve(spec, args.base)
    report = applier.run(spec, write=False)
    print(report.summary())
    return 0 if report.all_ok else 1


def cmd_info(args) -> int:
    data, pe = applier.load_target(args.target)
    print(f"文件: {args.target}")
    print(f"大小: {len(data)} 字节 (0x{len(data):X})")
    if pe is None:
        print("类型: 裸二进制（非 PE）")
        return 0
    print(f"类型: PE{' 64-bit' if pe.is_64bit else ' 32-bit'}")
    print(f"ImageBase: 0x{pe.image_base:X}")
    print("节区:")
    for s in pe.sections:
        print(f"  {s.name:<10} VA=0x{s.virtual_address:08X} "
              f"VSize=0x{s.virtual_size:08X} "
              f"RawPtr=0x{s.raw_ptr:08X} RawSize=0x{s.raw_size:08X}")
    return 0


def cmd_path(args) -> int:
    print(datadir.ensure_data_dir())
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="winpatchkit", description="Windows 二进制 patch 工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出已加载的模块").set_defaults(func=cmd_list)

    pi = sub.add_parser("import", help="手动导入配置")
    pi.add_argument("files", nargs="+", help="一个或多个 .toml 路径")
    pi.set_defaults(func=cmd_import)

    for name, func, helpt in (("apply", cmd_apply, "应用模块（备份由设置决定）"),
                              ("verify", cmd_verify, "仅校验能否定位，不落盘")):
        sp = sub.add_parser(name, help=helpt)
        sp.add_argument("module", help="模块 name 或文件名")
        sp.add_argument("--base", default="", help="目标文件基准目录（覆盖设置）")
        sp.set_defaults(func=func)

    ps = sub.add_parser("info", help="打印目标 PE 信息")
    ps.add_argument("target", help="目标文件路径")
    ps.set_defaults(func=cmd_info)

    sub.add_parser("path", help="打印数据目录路径").set_defaults(func=cmd_path)

    args = p.parse_args(argv)
    try:
        startup()
        return args.func(args)
    except (cfig.ConfigError, applier.PatchError, FileNotFoundError) as e:
        print(f"错误: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"未预期错误: {type(e).__name__}: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())