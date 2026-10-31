"""Win32/DWM 标题栏适配（独立职责模块）。

让 Win32 原生标题栏跟随窗口明暗，并在 Win11 上精确贴合 Material 3 背景色，
避免"系统浅色 + 内容深色"的视觉割裂。

   DWMWA_USE_IMMERSIVE_DARK_MODE = 20   Win10 1903+ / Win11：深色标题栏开关
   DWMWA_CAPTION_COLOR           = 35   Win11 22H2+：精确背景色（Win10 静默忽略）

背景色取自 Material 3 surface（种子 #2E8B57 推导）：
   深色 #0F1511 / 浅色 #F8F9FF

仅 Windows 有效；非 Windows 平台调用 apply_titlebar 会静默跳过。
"""
from __future__ import annotations

import os

_DWMWA_IMMERSIVE_DARK = 20
_DWMWA_CAPTION_COLOR  = 35
_CAPTION_DARK  = "#0F1511"
_CAPTION_LIGHT = "#F8F9FF"


def _colorref(rgb_hex: str) -> int:
    """'#RRGGBB' -> Windows COLORREF（0x00BBGGRR，顶字节必须为 0）。"""
    h = rgb_hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def apply_titlebar(title: str, dark: bool) -> None:
    """按窗口标题找 HWND，套用深色/精确背景色标题栏。非 Windows 直接返回。"""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi

    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum(h, _):
        n = user32.GetWindowTextLengthW(h)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, buf, n + 1)
            if buf.value == title:
                found.append(h)
        return True

    user32.EnumWindows(_enum, 0)

    for h in found:
        v_dark = ctypes.c_int(1 if dark else 0)
        dwmapi.DwmSetWindowAttribute(
            h, _DWMWA_IMMERSIVE_DARK,
            ctypes.byref(v_dark), ctypes.sizeof(v_dark))
        # Win11: 精确标题栏背景色（Win10 上此属性不存在，调用静默失败，无副作用）
        v_color = ctypes.c_uint(_colorref(_CAPTION_DARK if dark else _CAPTION_LIGHT))
        dwmapi.DwmSetWindowAttribute(
            h, _DWMWA_CAPTION_COLOR,
            ctypes.byref(v_color), ctypes.sizeof(v_color))
