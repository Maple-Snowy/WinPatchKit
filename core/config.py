"""TOML 配置加载。

依赖 Python 3.11+ 内置 tomllib（只读）。
配置是给人手写的，读取即可；不涉及程序化写回。
"""
from __future__ import annotations

import os
import tomllib

from .spec import ModuleSpec


class ConfigError(Exception):
    pass


def load_module(path: str) -> ModuleSpec:
    """从一个 TOML 文件加载 ModuleSpec。"""
    if not os.path.isfile(path):
        raise ConfigError(f"配置文件不存在: {path}")
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"TOML 解析失败: {e}") from e
    except OSError as e:
        raise ConfigError(f"读取配置失败: {e}") from e
    return ModuleSpec.from_dict(data)


def resolve_target(module_toml_path: str, spec: ModuleSpec) -> ModuleSpec:
    """把 spec.target 相对路径解析为相对于 TOML 所在目录的绝对路径。

    若 target 已是绝对路径则原样返回。这样模块目录可以自带被 patch 的目标，
    便于把模块打包成自包含单元。
    """
    if os.path.isabs(spec.target):
        return spec
    base = os.path.dirname(os.path.abspath(module_toml_path))
    spec.target = os.path.normpath(os.path.join(base, spec.target))
    if spec.out and not os.path.isabs(spec.out):
        spec.out = os.path.normpath(os.path.join(base, spec.out))
    return spec


def resolve_base(spec: ModuleSpec, base_dir: str) -> ModuleSpec:
    """把相对路径的 target / out 解析为相对于 base_dir 的绝对路径。

    base_dir 通常是"目标文件所在目录"（如 OsEasy 安装目录）。
    因为模块配置不再与目标同目录存放，运行时需由主程序给定该基准目录。
    若 target 已是绝对路径则原样返回；base_dir 为空时不改动。
    """
    if not base_dir or os.path.isabs(spec.target):
        return spec
    spec.target = os.path.normpath(os.path.join(base_dir, spec.target))
    if spec.out and not os.path.isabs(spec.out):
        spec.out = os.path.normpath(os.path.join(base_dir, spec.out))
    return spec