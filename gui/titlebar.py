"""Win32/DWM 标题栏适配（独立职责模块）。

让 Win32 原生标题栏跟随窗口明暗，并在 Win11 上精确贴合 Material 3 表面色，
避免"系统浅色 + 内容深色"的视觉割裂。

    DWMWA_USE_IMMERSIVE_DARK_MODE = 20   Win10 1903+ / Win11：深色标题栏开关
    DWMWA_CAPTION_COLOR           = 35   Win11 22H2+：精确背景色（Win10 静默忽略）

表面色从 Material 3 种子色推导（与 Flet 实际渲染的 surface 保持一致），
这样标题栏能随"种子色 + 明暗"自动匹配，不再写死某一种颜色。
仅 Windows 有效；非 Windows 平台调用 apply_titlebar 会静默跳过。
"""
from __future__ import annotations

import os

_DWMWA_IMMERSIVE_DARK = 20
_DWMWA_CAPTION_COLOR  = 35


def _hex_to_rgb(rgb_hex: str):
    h = (rgb_hex or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def _colorref(rgb_hex: str) -> int:
    """'#RRGGBB' -> Windows COLORREF（0x00BBGGRR，顶字节必须为 0）。"""
    rgb = _hex_to_rgb(rgb_hex) or (0, 0, 0)
    r, g, b = rgb
    return (b << 16) | (g << 8) | r


def _rel_luminance(rgb_hex: str) -> float:
    """WCAG 相对亮度（0 黑 ~ 1 白），用于判断种子偏亮还是偏暗。"""
    rgb = _hex_to_rgb(rgb_hex)
    if not rgb:
        return 0.0
    def _ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * _ch(r) + 0.7152 * _ch(g) + 0.0722 * _ch(b)


def _mix(c1, c2, t):
    """线性插值两个 (r,g,b)，t=0 取 c1、t=1 取 c2。"""
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def _to_hex(rgb) -> str:
    return "#%02X%02X%02X" % rgb


def derive_surface(seed: str, dark: bool) -> str:
    """据种子色推导与 Flet 渲染一致的 Material 3 表面色（标题栏用）。

    深色：取种子低明度的暗调；浅色：近白并带种子极淡色调。
    与之前海绿种子（dark≈#0F1511 / light≈#F8F9FF）的量级一致。
    """
    rgb = _hex_to_rgb(seed) or (46, 139, 87)   # 回退海绿
    sat = (max(rgb) - min(rgb)) / 255.0
    lum = _rel_luminance(_to_hex(rgb))
    if dark:
        v = int(round(16 + lum * 10))
        base = (max(9, int(v * (1 - 0.5 * sat))),
                v, max(9, int(v * (1 - 0.5 * sat))))
        return _to_hex(_mix(rgb, base, 0.92))
    v = int(round(246 + (255 - 246) * sat))
    base = (min(255, max(245, int(v * (1 - 0.15 * sat)))),
            min(255, v), min(255, max(245, int(v * (1 - 0.15 * sat)))))
    # 以近白 base 为主（向 base 走近），仅留极淡种色调：与深色分支同向（t 大→靠近 base）
    return _to_hex(_mix(rgb, base, 0.94))


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

    surface = derive_surface(seed, dark)
    for h in found:
        v_dark = ctypes.c_int(1 if dark else 0)
        dwmapi.DwmSetWindowAttribute(
            h, _DWMWA_IMMERSIVE_DARK,
            ctypes.byref(v_dark), ctypes.sizeof(v_dark))
        # Win11: 精确标题栏背景色（Win10 上此属性不存在，调用静默失败，无副作用）
        v_color = ctypes.c_uint(_colorref(surface))
        dwmapi.DwmSetWindowAttribute(
            h, _DWMWA_CAPTION_COLOR,
            ctypes.byref(v_color), ctypes.sizeof(v_color))