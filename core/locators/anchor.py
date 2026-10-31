"""定位方案：锚点（anchor）。

配置参数（where 表内，除 type 外）：
  pattern       : 十六进制字节序列，如 "48 8B 05 11 22 33 00"（必填）
  unique        : 默认 true。要求锚点在文件中恰好出现 1 次（安全定位）。
                  设为 false 时允许按 which 取第 N 次出现。
  which         : 第几次出现，默认 1（1-based），仅 unique=false 时有意义
  delta         : 相对锚点起点的偏移（可负），默认 0
  sanity_window : 可选。从锚点命中处开始往后取 N 字节的窗口
  sanity_pattern: 可选。窗口内必须出现该字节序列（语义二次校验）
                  例如函数入口附近应出现 call [abs ptr] 的 ff15

裸二进制与 PE 均可用。
"""
from __future__ import annotations

from ..context import Context, find_all, parse_bytes, parse_int
from . import register
from .base import Locator, AnchorNotUniqueError, LocatorError, OutOfRangeError


@register
class AnchorLocator(Locator):
    type = "anchor"

    def resolve(self, ctx: Context) -> int:
        p = ctx.patch.where.params
        if "pattern" not in p:
            raise AnchorNotUniqueError("anchor 定位缺少 pattern")
        needle = parse_bytes(p["pattern"])
        unique = bool(p.get("unique", True))
        which = parse_int(p.get("which", 1))

        hits = find_all(ctx.data, needle)
        if unique:
            if len(hits) != 1:
                raise AnchorNotUniqueError(
                    f"锚点 {p['pattern']!r} 出现 {len(hits)} 次（unique 要求恰好 1 次），版本可能不符"
                )
            base = hits[0]
        else:
            if which < 1:
                raise AnchorNotUniqueError(f"anchor which 必须 >= 1，得到 {which}")
            if len(hits) < which:
                raise AnchorNotUniqueError(
                    f"锚点 {p['pattern']!r} 仅出现 {len(hits)} 次，无法取第 {which} 次"
                )
            base = hits[which - 1]

        pos = base + parse_int(p.get("delta", 0))
        if pos < 0 or pos >= len(ctx.data):
            raise OutOfRangeError(f"anchor 算出的偏移 0x{pos:X} 越界（文件大小 0x{len(ctx.data):X}）")

        # sanity：命中处附近窗口内必须出现特征字节
        if p.get("sanity_pattern") is not None:
            window = parse_int(p.get("sanity_window", 0x40))
            spat = parse_bytes(p["sanity_pattern"])
            if spat not in ctx.data[pos:pos + window]:
                raise LocatorError(
                    f"sanity 校验失败：命中处后 0x{window} 窗口内未见 {spat.hex()}"
                )
        return pos