"""写入策略注册表与工厂。

新增写入方案：在 core/writers/ 下新建一个 .py，
顶部 @register 该类即可——本文件与 applier 无需改动。
"""
from __future__ import annotations

from typing import Dict, Type

from .base import Writer

_REGISTRY: Dict[str, Type[Writer]] = {}


def register(cls: Type[Writer]) -> Type[Writer]:
    if not cls.type:
        raise ValueError(f"{cls.__name__} 缺少 type 常量")
    if cls.type in _REGISTRY and _REGISTRY[cls.type] is not cls:
        raise ValueError(f"写入器 type 冲突: {cls.type!r}")
    _REGISTRY[cls.type] = cls
    return cls


def available() -> list:
    return sorted(_REGISTRY.keys())


def make(type_name: str) -> Writer:
    if type_name not in _REGISTRY:
        raise KeyError(f"未知写入类型 {type_name!r}，可用: {available()}")
    return _REGISTRY[type_name]()


# ---- 触发注册：每个文件即一种方案 ----
from . import raw          # noqa: E402,F401
from . import nop          # noqa: E402,F401