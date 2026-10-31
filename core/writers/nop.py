"""写入方案：nop（按长度填 0x90）。

配置参数：
  length : 要填 NOP 的字节数（必填）

常用于禁用某段指令 / 校验逻辑。
"""
from __future__ import annotations

from ..context import Context, parse_int
from . import register
from .base import Writer, WriterError


@register
class NopWriter(Writer):
    type = "nop"

    def encode(self, ctx: Context) -> bytes:
        p = ctx.patch.write.params
        if "length" not in p:
            raise WriterError("nop 写入缺少 length")
        n = parse_int(p["length"])
        if n < 0:
            raise WriterError(f"nop length 不能为负: {n}")
        return b"\x90" * n