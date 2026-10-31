"""定位方案：文件偏移（file_offset）。

配置参数：
  value : 文件中的绝对偏移（hex 或十进制）

裸二进制与 PE 均可用，最基础的定位方式。
"""
from __future__ import annotations

from ..context import Context, parse_int
from . import register
from .base import Locator, OutOfRangeError


@register
class FileOffsetLocator(Locator):
    type = "file_offset"

    def resolve(self, ctx: Context) -> int:
        p = ctx.patch.where.params
        if "value" not in p:
            raise OutOfRangeError("file_offset 定位缺少 value")
        off = parse_int(p["value"])
        if off < 0 or off >= len(ctx.data):
            raise OutOfRangeError(f"文件偏移 0x{off:X} 越界（文件大小 0x{len(ctx.data):X}）")
        return off