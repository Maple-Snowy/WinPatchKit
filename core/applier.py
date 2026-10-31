"""执行器：把一组 PatchSpec 应用到二进制。

这是项目里唯一做"写文件 / 改字节"的地方。
定位器负责算偏移、写入器负责算字节，本模块负责把它们拼起来并落盘。

安全机制（可移植自 OsEasy 的幂等 / orig 校验思想）：
- 每条 patch 可带 expect（期望的当前原始字节）。
  · 写前校验：当前字节 != expect -> FAIL（版本漂移/定位错误）
  · 幂等：当前字节 == 目标字节 -> 跳过（已 patch），不重复写
- apply / verify 共用定位+编码逻辑；verify 不落盘，只报告结果。

流程：
  1. 读目标字节
  2. 若为 PE 则解析（支持 VA/RVA 定位）；否则 pe=None（裸二进制）
  3. 逐条 patch：定位 -> (校验) -> 写字节（在内存缓冲上进行）
  4. 备份原文件（可选）
  5. 写出结果
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from . import pe as pe_mod
from .context import Context, parse_bytes
from .locators import make as make_locator
from .spec import ModuleSpec, PatchSpec
from .writers import make as make_writer


@dataclass
class PatchResult:
    id: str
    ok: bool
    offset: int = -1
    written: int = 0
    skipped: bool = False
    message: str = ""


@dataclass
class ApplyReport:
    module: str
    target: str
    out_path: str
    results: List[PatchResult]
    wrote: bool

    @property
    def all_ok(self) -> bool:
        return all(r.ok for r in self.results)

    def summary(self) -> str:
        lines = [f"[{self.module}] {self.target} -> {self.out_path or '(仅校验)'}"]
        for r in self.results:
            if r.skipped:
                flag = "SKIP"
            else:
                flag = "OK  " if r.ok else "FAIL"
            off = f"@0x{r.offset:X}" if r.offset >= 0 else ""
            lines.append(f"  {flag}  {r.id:<20} {off}  {r.message}")
        okn = sum(r.ok for r in self.results)
        skn = sum(r.skipped for r in self.results)
        lines.append(f"  总计 {okn}/{len(self.results)} 成功，{skn} 跳过")
        return "\n".join(lines)


class PatchError(Exception):
    """加载或执行阶段的致命错误。"""


def load_target(path: str):
    """读目标字节；若是 PE 则解析并返回 (data, pe)，否则 (data, None)。"""
    if not os.path.isfile(path):
        raise PatchError(f"目标文件不存在: {path}")
    with open(path, "rb") as f:
        data = f.read()
    if not data:
        raise PatchError(f"目标文件为空: {path}")
    pe = pe_mod.parse_pe(data) if pe_mod.is_pe(data) else None
    return data, pe


def _apply_one(buf: bytearray, ctx: Context, patch: PatchSpec) -> PatchResult:
    """对单条 patch：定位 + (校验) + 写入 buf。失败返回 ok=False，不抛致命异常。"""
    try:
        locator = make_locator(patch.where.type)
        writer = make_writer(patch.write.type)
        offset = locator.resolve(ctx)
        blob = writer.encode(ctx)
        if offset < 0 or offset + len(blob) > len(buf):
            return PatchResult(patch.id, False, offset, 0,
                               f"越界: 0x{offset:X}+{len(blob)} 超出文件 0x{len(buf):X}")

        # 可选的 orig 校验 + 幂等
        expect_hex = patch.write.params.get("expect", patch.where.params.get("expect"))
        if expect_hex is not None:
            expect = parse_bytes(expect_hex)
            # 幂等：实际写入区已是目标态则跳过（按 new 长度比较，兼容 new 比 orig 短）
            if bytes(buf[offset:offset + len(blob)]) == blob:
                return PatchResult(patch.id, True, offset, 0, True, "已是目标状态，跳过")
            # 原字节校验：当前应为期望的原始字节（按 orig 长度比较）
            if bytes(buf[offset:offset + len(expect)]) != expect:
                return PatchResult(
                    patch.id, False, offset, 0, False,
                    f"原字节不符: 实际 {bytes(buf[offset:offset + len(expect)]).hex(' ')} ≠ 期望 {expect.hex(' ')}"
                )

        buf[offset:offset + len(blob)] = blob
        return PatchResult(patch.id, True, offset, len(blob), False, "已写入")
    except Exception as e:  # 策略级错误统一收口为 FAIL，不让单条失败中断整体
        return PatchResult(patch.id, False, -1, 0, False, f"{type(e).__name__}: {e}")


def run(spec: ModuleSpec, write: bool = True, backup: bool = True,
        backup_dir: Optional[str] = None, backup_ext: str = ".bak") -> ApplyReport:
    """执行模块。

    write        : False 时只校验，不备份也不落盘。
    backup       : 是否备份，由主程序决定（默认 True）。
    backup_dir   : 备份存放目录（主程序决定）。None 则备份到 target 同目录。
    backup_ext   : 备份后缀（默认 ".bak"），由主程序决定。

    备份策略：只对原始文件备份一次。备份文件名 = basename(target)+backup_ext，
    动手前检查其是否已存在，存在则跳过（保留最初那份原始备份），不存在才写入
    当前（原始）内容。这样即使后续对已修补文件再次 apply，也不会把修补后的
    文件误存为备份。
    """
    data, pe = load_target(spec.target)
    buf = bytearray(data)

    results: List[PatchResult] = []
    for patch in spec.patches:
        ctx = Context(data=bytes(buf), pe=pe, patch=patch)
        results.append(_apply_one(buf, ctx, patch))

    if not write:
        return ApplyReport(spec.name, spec.target, "", results, wrote=False)

    if backup:
        if backup_dir is None:
            bak = spec.target + backup_ext
        else:
            os.makedirs(backup_dir, exist_ok=True)
            bak = os.path.join(backup_dir, os.path.basename(spec.target) + backup_ext)
        if not os.path.exists(bak):  # 已存在则跳过：只备份原始文件一次
            with open(bak, "wb") as f:
                f.write(data)

    out_path = spec.out or spec.target
    with open(out_path, "wb") as f:
        f.write(buf)

    return ApplyReport(spec.name, spec.target, out_path, results, wrote=True)