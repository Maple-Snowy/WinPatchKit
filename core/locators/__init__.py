"""定位策略注册表与工厂。

新增定位方案：在 core/locators/ 下新建一个 .py，
顶部 @register 该类即可——本文件与 applier 无需改动。

导入子模块以触发各自的 @register 注册。
"""
from __future__ import annotations

from typing import Dict, Type

from .base import Locator

_REGISTRY: Dict[str, Type[Locator]] = {}


def register(cls: Type[Locator]) -> Type[Locator]:
    """类装饰器：按 cls.type 注册定位器。"""
    if not cls.type:
        raise ValueError(f"{cls.__name__} 缺少 type 常量")
    if cls.type in _REGISTRY and _REGISTRY[cls.type] is not cls:
        raise ValueError(f"定位器 type 冲突: {cls.type!r}")
    _REGISTRY[cls.type] = cls
    return cls


def available() -> list:
    return sorted(_REGISTRY.keys())


def make(type_name: str) -> Locator:
    """按 type 名称实例化定位器（策略无状态，实例即通用）。"""
    if type_name not in _REGISTRY:
        raise KeyError(f"未知定位类型 {type_name!r}，可用: {available()}")
    return _REGISTRY[type_name]()


# ---- 触发注册：每个文件即一种方案 ----
from . import anchor        # noqa: E402,F401
from . import va            # noqa: E402,F401
from . import rva           # noqa: E402,F401
from . import file_offset   # noqa: E402,F401