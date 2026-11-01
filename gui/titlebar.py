"""Win32/DWM 标题栏适配（独立职责模块）。

让 Win32 原生标题栏跟随窗口明暗，并在 Win11 上精确贴合 Material 3 表面色，
避免"系统浅色 + 内容深色"的视觉割裂。

    DWMWA_USE_IMMERSIVE_DARK_MODE = 20   Win10 1903+ / Win11：深色标题栏开关
    DWMWA_CAPTION_COLOR           = 35   Win11 22H2+：精确背景色（Win10 静默忽略）

表面色与 Flet 内容区 **逐值一致**：Flet 1.0.5 的 color_scheme_seed 由 Flutter
前端 ColorScheme.fromSeed 渲染，Python 侧拿不到 surface 值；surface 的精确计算
（Google material-color-utilities 算法）在 m3_surface.py，本模块只负责把算出的
surface 应用到 Win32 标题栏。
仅 Windows 有效；非 Windows 平台调用 apply_titlebar 会静默跳过。
"""
from __future__ import annotations

import os

from . import m3_surface

_DWMWA_IMMERSIVE_DARK = 20
_DWMWA_CAPTION_COLOR  = 35


def _colorref(rgb_hex: str) -> int:
    """'#RRGGBB' -> Windows COLORREF（0x00BBGGRR，顶字节必须为 0）。"""
    rgb = m3_surface._hex_to_rgb(rgb_hex) or (0, 0, 0)
    r, g, b = rgb
    return (b << 16) | (g << 8) | r


def apply_titlebar(title: str, dark: bool, seed: str = "#2E8B57") -> None:
    """按窗口标题找 HWND，套用深色 + 随种子色的表面色标题栏。非 Windows 直接返回。"""
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

    surface = m3_surface.surface_color(seed, dark)
    for h in found:
        v_dark = ctypes.c_int(1 if dark else 0)
        dwmapi.DwmSetWindowAttribute(
            h, _DWMWA_IMMERSIVE_DARK,
            ctypes.byref(v_dark), ctypes.sizeof(v_dark))
        v_color = ctypes.c_uint(_colorref(surface))
        dwmapi.DwmSetWindowAttribute(
            h, _DWMWA_CAPTION_COLOR,
            ctypes.byref(v_color), ctypes.sizeof(v_color))