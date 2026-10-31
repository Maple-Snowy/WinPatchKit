"""定位方案：VA（虚拟地址）。

配置参数：
  value : 虚拟地址（hex 或十进制），如 "0x140001234"

需要 PE 目标：把 VA -> RVA -> 文件偏移。裸二进制使用会抛 NeedPEError。
"""
from __future__ import annotations

from ..context import Context, parse_int
from . import register
from .base import Locator, NeedPEError, OutOfRangeError


@register
class VaLocator(Locator):
    type = "va"

    def resolve(self, ctx: Context) -> int:
        if ctx.pe is None:
            raise NeedPEError("va 定位需要 PE 目标，当前是裸二进制")
        p = ctx.patch.where.params
        if "value" not in p:
            raise NeedPEError("va 定位缺少 value")
        va = parse_int(p["value"])
        off = ctx.pe.va_to_offset(va)
        if off < 0 or off >= len(ctx.data):
            raise OutOfRangeError(f"VA 0x{va:X} 对应偏移 0x{off:X} 越界")
        return off