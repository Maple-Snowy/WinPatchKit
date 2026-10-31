"""端到端测试：动态生成合法 PE，验证 patch 全链路。

不依赖真实 Windows exe，可在任意平台跑。
覆盖：PE 解析、anchor / va / rva / file_offset 定位、raw / nop 写入、
裸二进制路径、锚点不唯一、VA 落在裸二进制时报错。

运行: python tests/test_winpatchkit.py
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import pe as pe_mod          # noqa: E402
from core import applier                # noqa: E402
from core.spec import ModuleSpec, PatchSpec, Where, Write  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# 在 .text 里放一段已知字节，作为锚点 / VA / 偏移定位目标
ANCHOR = bytes([0x48, 0x8B, 0x05, 0x11, 0x22, 0x33, 0x00])
NEWBYTES = bytes([0x48, 0x8B, 0x0D, 0x11, 0x22, 0x33, 0x00])

# 布局：
#   DOS header (0x40)
#   PE sig + COFF(20) + Optional(240, PE32+) + 1 section header(40)
#   section data (0x200)
IMAGE_BASE = 0x140000000
SEC_RVA = 0x1000
SEC_RAW_PTR = 0x400
SEC_RAW_SIZE = 0x200
# 锚点在 .text 内偏移 SEC_RAW_PTR + 0x10 处
ANCHOR_FILE_OFF = SEC_RAW_PTR + 0x10


def build_pe() -> bytes:
    buf = bytearray()
    # DOS
    buf += b"MZ" + b"\x00" * (0x3C - 2)
    e_lfanew = 0x40
    buf += struct.pack("<I", e_lfanew)
    # 现在 len == 0x40
    # PE signature
    buf += b"PE\x00\x00"
    # COFF (20 bytes)
    machine = 0x8664
    num_sections = 1
    timestamp = 0
    sym_ptr, nsym = 0, 0
    size_opt = 240
    characteristics = 0x0022
    buf += struct.pack("<HHIIIHH", machine, num_sections, timestamp,
                       sym_ptr, nsym, size_opt, characteristics)
    # Optional header (PE32+), 需要 240 字节
    opt = bytearray(240)
    struct.pack_into("<H", opt, 0, 0x20B)      # Magic PE32+
    struct.pack_into("<B", opt, 2, 14)         # MajorLinker
    struct.pack_into("<B", opt, 3, 0)          # MinorLinker
    struct.pack_into("<I", opt, 8, SEC_RAW_SIZE)  # SizeOfCode
    struct.pack_into("<Q", opt, 24, IMAGE_BASE)   # ImageBase
    struct.pack_into("<I", opt, 32, 0x1000)       # SectionAlignment
    struct.pack_into("<I", opt, 36, 0x200)        # FileAlignment
    struct.pack_into("<I", opt, 56, 0x2000)       # SizeOfImage
    struct.pack_into("<I", opt, 60, SEC_RAW_PTR)  # SizeOfHeaders (对齐到文件)
    struct.pack_into("<I", opt, 64, 0x0001)       # Subsystem (Console)
    struct.pack_into("<H", opt, 68, 0x160)        # DllCharacteristics
    struct.pack_into("<Q", opt, 72, 0x100000)     # SizeOfStackReserve
    struct.pack_into("<Q", opt, 80, 0x1000)       # SizeOfStackCommit
    struct.pack_into("<Q", opt, 88, 0x100000)     # SizeOfHeapReserve
    struct.pack_into("<Q", opt, 96, 0x1000)       # SizeOfHeapCommit
    struct.pack_into("<I", opt, 108, 16)          # NumberOfRvaAndSizes
    buf += bytes(opt)
    # Section header .text (40 bytes)
    name = b".text\x00\x00\x00"
    vs = SEC_RAW_SIZE
    va = SEC_RVA
    rs = SEC_RAW_SIZE
    rp = SEC_RAW_PTR
    # characteristics: CODE|EXECUTE|READ
    flags = 0x60000020
    buf += name + struct.pack("<IIIIIIHHI", vs, va, rs, rp, 0, 0, 0, 0, flags)
    # 填充 header 到 SEC_RAW_PTR
    cur = len(buf)
    assert cur <= SEC_RAW_PTR, f"header 过大 {cur}"
    buf += b"\x00" * (SEC_RAW_PTR - cur)
    # section data
    data = bytearray(SEC_RAW_SIZE)
    data[0x10:0x10 + len(ANCHOR)] = ANCHOR
    buf += bytes(data)
    return bytes(buf)


def main():
    tmp = tempfile.mkdtemp(prefix="wptest_")
    pe_path = os.path.join(tmp, "target.exe")
    with open(pe_path, "wb") as f:
        f.write(build_pe())

    print("== PE 解析 ==")
    data, pe = applier.load_target(pe_path)
    check("识别为 PE", pe is not None)
    check("64 位", pe.is_64bit, f"is_64bit={pe.is_64bit}")
    check("ImageBase", pe.image_base == IMAGE_BASE, hex(pe.image_base))
    check("1 个节区", len(pe.sections) == 1)
    check("节区名 .text", pe.sections[0].name == ".text", pe.sections[0].name)
    # VA -> 文件偏移
    va_anchor = IMAGE_BASE + SEC_RVA + 0x10
    off = pe.va_to_offset(va_anchor)
    check("VA->offset", off == ANCHOR_FILE_OFF, f"got 0x{off:X} want 0x{ANCHOR_FILE_OFF:X}")
    check("RVA->offset", pe.rva_to_offset(SEC_RVA + 0x10) == ANCHOR_FILE_OFF)

    print("== 锚点定位 ==")
    check("锚点在预期位置", data[ANCHOR_FILE_OFF:ANCHOR_FILE_OFF + len(ANCHOR)] == ANCHOR)
    from core.context import find_all
    check("锚点唯一", len(find_all(data, ANCHOR)) == 1, f"got {len(find_all(data, ANCHOR))}")

    print("== 全链路 patch ==")
    spec = ModuleSpec(
        name="t", target=pe_path,
        id="test-pe", version="1.0",
        out=os.path.join(tmp, "out.exe"),
        patches=[
            # anchor + raw
            PatchSpec("anchor_raw",
                      Where("anchor", {"pattern": ANCHOR.hex(), "delta": 0}),
                      Write("raw", {"bytes": NEWBYTES.hex()})),
            # va + nop（覆盖 5 字节，位置在 section 内 0x40）
            PatchSpec("va_nop",
                      Where("va", {"value": hex(IMAGE_BASE + SEC_RVA + 0x40)}),
                      Write("nop", {"length": 5})),
            # file_offset + raw
            PatchSpec("fo_raw",
                      Where("file_offset", {"value": hex(SEC_RAW_PTR + 0x80)}),
                      Write("raw", {"bytes": "DE AD BE EF"})),
            # rva + nop（挪到 0xC0，避免与 fo_raw@0x80 重叠）
            PatchSpec("rva_nop",
                      Where("rva", {"value": hex(SEC_RVA + 0xC0)}),
                      Write("nop", {"length": 3})),
        ],
    )
    report = applier.run(spec, write=True)
    print(report.summary())
    check("全部成功", report.all_ok)

    with open(report.out_path, "rb") as f:
        out = f.read()
    check("anchor_raw 生效", out[ANCHOR_FILE_OFF:ANCHOR_FILE_OFF + 7] == NEWBYTES)
    check("va_nop 生效", out[SEC_RAW_PTR + 0x40:SEC_RAW_PTR + 0x45] == b"\x90" * 5)
    check("fo_raw 生效", out[SEC_RAW_PTR + 0x80:SEC_RAW_PTR + 0x84] == bytes([0xDE, 0xAD, 0xBE, 0xEF]))
    check("rva_nop 生效", out[SEC_RAW_PTR + 0xC0:SEC_RAW_PTR + 0xC3] == b"\x90" * 3)
    check("备份存在", os.path.isfile(pe_path + ".bak"))

    print("== 裸二进制路径 ==")
    raw_path = os.path.join(tmp, "raw.bin")
    with open(raw_path, "wb") as f:
        f.write(b"\x00" * 64 + ANCHOR + b"\x00" * 32)
    raw_spec = ModuleSpec(
        name="raw", target=raw_path,
        id="test-raw", version="1.0",
        out=os.path.join(tmp, "raw_out.bin"),
        patches=[
            PatchSpec("r_anchor", Where("anchor", {"pattern": ANCHOR.hex()}),
                      Write("raw", {"bytes": "AA BB CC"})),
            PatchSpec("r_offset", Where("file_offset", {"value": "0x40"}),
                      Write("nop", {"length": 2})),
            # VA 在裸二进制上应失败
            PatchSpec("r_va_bad", Where("va", {"value": "0x140001000"}),
                      Write("raw", {"bytes": "FF"})),
        ],
    )
    rr = applier.run(raw_spec, write=True)
    check("anchor 成功", rr.results[0].ok)
    check("offset 成功", rr.results[1].ok)
    check("VA 在裸二进制失败", not rr.results[2].ok and "NeedPE" in rr.results[2].message,
          rr.results[2].message)

    print("== 锚点不唯一 ==")
    dup_path = os.path.join(tmp, "dup.bin")
    with open(dup_path, "wb") as f:
        f.write(ANCHOR + b"\x00" * 16 + ANCHOR)
    dup_spec = ModuleSpec(
        name="dup", target=dup_path,
        id="test-dup", version="1.0",
        out=os.path.join(tmp, "dup_out.bin"),
        patches=[PatchSpec("only2", Where("anchor", {"pattern": ANCHOR.hex(), "which": 3}),
                           Write("raw", {"bytes": "00"}))],
    )
    rd = applier.run(dup_spec, write=True)
    check("第3次出现不存在->FAIL", not rd.results[0].ok and "Anchor" in rd.results[0].message,
          rd.results[0].message)

    print("== verify 不落盘 ==")
    v = applier.run(spec, write=False)
    check("verify wrote=False", not v.wrote)
    check("verify 全 OK", v.all_ok)

    print(f"\n结果: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())