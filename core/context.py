"""定位 / 写入策略共享的上下文与字节解析工具。

Context 是策略与执行器之间的唯一契约载体：
- data  : 目标二进制原始字节（裸二进制或 PE 均适用）
- pe    : PE 解析结果；裸二进制为 None
- patch : 当前 PatchSpec（纯数据）
- out   : 可写缓冲（applier 提供，策略一般不直接写）

新增定位/写入方案时无需改动本文件，只需继承各自 base 并在自己文件里 @register。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .pe import PE
    from .spec import PatchSpec


@dataclass
class Context:
    data: bytes
    pe: Optional["PE"]
    patch: "PatchSpec"


# ---- 字节 / 数字解析工具 ----

def parse_bytes(text: str) -> bytes:
    """把 '48 8B 05' 或 '488B05' 这样的十六进制串解析成 bytes。

    允许中间含空格或任意空白；也允许逗号分隔。非 hex 字符会抛 ValueError。
    """
    cleaned = re.sub(r"[\s,]+", "", text)
    if len(cleaned) % 2 != 0:
        raise ValueError(f"字节串长度为奇数: {text!r}")
    try:
        return bytes.fromhex(cleaned)
    except ValueError:
        raise ValueError(f"非法的十六进制字节串: {text!r}")


def parse_int(value) -> int:
    """把配置里的整数解析出来。

    支持：int 直接返回；'0x140001234' / '140001234'(hex 带 0x) / '100' 十进制。
    """
    if isinstance(value, int):
        return value
    s = str(value).strip()
    low = s.lower()
    if low.startswith("0x"):
        return int(s, 16)
    if low.startswith("0b"):
        return int(s, 2)
    return int(s, 0)


def find_all(haystack: bytes, needle: bytes) -> list:
    """返回 needle 在 haystack 中所有出现起点（允许重叠）。"""
    if not needle:
        raise ValueError("锚点字节序列不能为空")
    out = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            return out
        out.append(idx)
        start = idx + 1