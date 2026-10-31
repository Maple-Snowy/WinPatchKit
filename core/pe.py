"""PE 解析器（纯 Python，零第三方依赖）。

职责：
- 识别 PE 文件（DOS 头 + PE 签名）
- 解析 Section 表
- 提供 VA <-> RVA <-> 文件偏移 互算

只读、不写。写入逻辑全部在 applier.py。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional


class NotPEError(ValueError):
    """目标不是 PE 文件。"""


@dataclass
class Section:
    name: str
    virtual_address: int      # 节区起始 VA（ImageBase 不含，是相对 ImageBase 的 RVA 语义值）
    virtual_size: int
    raw_size: int             # 在文件中的大小
    raw_ptr: int              # 在文件中的起始偏移


@dataclass
class PE:
    is_64bit: bool
    image_base: int
    sections: List[Section]

    def rva_to_offset(self, rva: int) -> int:
        """RVA -> 文件偏移；越界或落在非原始数据区时抛错。"""
        for sec in self.sections:
            sec_end = sec.raw_ptr + sec.raw_size
            if sec.virtual_address <= rva < sec.virtual_address + max(sec.virtual_size, sec.raw_size):
                off = sec.raw_ptr + (rva - sec.virtual_address)
                if off < sec_end:
                    return off
                # RVA 落在 VirtualSize 超过 RawSize 的尾部（如 .bss），无文件实体
                raise ValueError(
                    f"RVA 0x{rva:X} 落在节区 {sec.name!r} 的非实体区域（VirtualSize > RawSize）"
                )
        raise ValueError(f"RVA 0x{rva:X} 不属于任何节区")

    def va_to_offset(self, va: int) -> int:
        """VA -> 文件偏移。"""
        rva = va - self.image_base
        if rva < 0:
            raise ValueError(f"VA 0x{va:X} 小于 ImageBase 0x{self.image_base:X}")
        return self.rva_to_offset(rva)

    def va_to_rva(self, va: int) -> int:
        return va - self.image_base


def is_pe(data: bytes) -> bool:
    """判断字节串是否为 PE（检查 DOS 头 e_lfanew 指向的 PE 签名）。"""
    if len(data) < 0x40:
        return False
    if data[:2] != b"MZ":
        return False
    try:
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    except struct.error:
        return False
    if e_lfanew + 4 > len(data):
        return False
    return data[e_lfanew:e_lfanew + 4] == b"PE\x00\x00"


def parse_pe(data: bytes) -> PE:
    """解析 PE 头与 Section 表。非 PE 抛 NotPEError。"""
    if not is_pe(data):
        raise NotPEError("目标不是 PE 文件（缺少有效 MZ / PE 签名）")

    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    coff_off = e_lfanew + 4

    # COFF File Header
    machine, num_sections = struct.unpack_from("<HH", data, coff_off)
    size_opt_hdr = struct.unpack_from("<H", data, coff_off + 16)[0]
    characteristics = struct.unpack_from("<H", data, coff_off + 20)[0]

    # 判定 32/64 位：优先看 Optional Header 的 Magic（0x10B=PE32, 0x20B=PE32+）
    opt_off = coff_off + 20
    magic = struct.unpack_from("<H", data, opt_off)[0]
    if magic == 0x20B:
        is_64bit = True
        image_base = struct.unpack_from("<Q", data, opt_off + 24)[0]
    elif magic == 0x10B:
        is_64bit = False
        image_base = struct.unpack_from("<I", data, opt_off + 28)[0]
    else:
        # 回退到 machine
        is_64bit = machine in (0x8664,)
        if is_64bit:
            image_base = struct.unpack_from("<Q", data, opt_off + 24)[0]
        else:
            image_base = struct.unpack_from("<I", data, opt_off + 28)[0]

    # Section 表紧随 Optional Header
    sec_table_off = opt_off + size_opt_hdr
    sections: List[Section] = []
    for i in range(num_sections):
        base = sec_table_off + i * 40
        name_b = data[base:base + 8]
        name = name_b.rstrip(b"\x00").decode("latin-1")
        (virtual_size, virtual_address, raw_size, raw_ptr) = struct.unpack_from(
            "<IIII", data, base + 8
        )
        sections.append(
            Section(
                name=name,
                virtual_address=virtual_address,
                virtual_size=virtual_size,
                raw_size=raw_size,
                raw_ptr=raw_ptr,
            )
        )

    return PE(is_64bit=is_64bit, image_base=image_base, sections=sections)
