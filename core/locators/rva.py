"""定位方案：RVA（相对虚拟地址）。

配置参数：
  value : RVA（hex 或十进制）

需要 PE 目标：RVA -> 文件偏移。
"""
from __future__ import annotations

from ..context import Context, parse_int
from . import register
from .base import Locator, NeedPEError, OutOfRangeError


@register
class RvaLocator(Locator):
    type = "rva"

    def resolve(self, ctx: Context) -> int:
        if ctx.pe is None:
            raise NeedPEError("rva 定位需要 PE 目标，当前是裸二进制")
        p = ctx.patch.where.params
        if "value" not in p:
            raise NeedPEError("rva 定位缺少 value")
        rva = parse_int(p["value"])
        off = ctx.pe.rva_to_offset(rva)
        if off < 0 or off >= len(ctx.data):
            raise OutOfRangeError(f"RVA 0x{rva:X} 对应偏移 0x{off:X} 越界")
        return off