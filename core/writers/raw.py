"""写入方案：raw（直接写字节）。

配置参数：
  bytes : 十六进制字节序列，如 "48 8B 0D 11 22 33 00"（必填）
"""
from __future__ import annotations

from ..context import Context, parse_bytes
from . import register
from .base import Writer, WriterError


@register
class RawWriter(Writer):
    type = "raw"

    def encode(self, ctx: Context) -> bytes:
        p = ctx.patch.write.params
        if "bytes" not in p:
            raise WriterError("raw 写入缺少 bytes")
        return parse_bytes(p["bytes"])