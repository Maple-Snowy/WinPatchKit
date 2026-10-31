"""定位策略基类。

每个定位器只需：
1. 继承 Locator，设置 type 常量
2. 实现 resolve(ctx) -> int（返回写入位置对应的文件偏移）
3. 文件顶部 @register

契约：resolve 只负责"算出文件偏移"，不写任何字节。
需要 PE 的策略在 ctx.pe is None 时应抛 NeedPEError。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..context import Context


class LocatorError(Exception):
    """定位失败的通用异常。"""


class NeedPEError(LocatorError):
    """该定位方式需要 PE 目标，但目标是裸二进制。"""


class AnchorNotUniqueError(LocatorError):
    """锚点出现次数与期望不符。"""


class OutOfRangeError(LocatorError):
    """算出的文件偏移越界。"""


class Locator(ABC):
    type: str = ""

    @abstractmethod
    def resolve(self, ctx: Context) -> int:
        """返回要写入的文件偏移（>= 0）。"""
        raise NotImplementedError