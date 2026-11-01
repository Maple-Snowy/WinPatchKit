"""读取 Windows 系统主题（强调色 + 明暗），用于「主题跟随系统」。

「跟随系统」= 读取用户当前 Windows 强调色（AccentColorMenu）作为种子色，
并按系统明暗决定窗口模式——而非 Flet 内置默认配色。
仅 Windows 有效；非 Windows 平台静默回退（强调色回退海绿、明暗回退深色）。
"""
from __future__ import annotations

import os

# 非 Windows 或读取失败时的回退值（海绿，与 SEED_COLOR 一致）
_FALLBACK_SEED = "#2E8B57"


def read_accent_color() -> str:
    """读 Windows 系统强调色，返回 '#RRGGBB'；失败回退海绿。

    来源：HKCU\\Control Panel\\Colors\\AccentColorMenu（值形如 "R G B" 十进制）。
    该键在 Win10 / Win11 上均存在，是标题栏/菜单强调色的权威来源。
    """
    if os.name != "nt":
        return _FALLBACK_SEED
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Control Panel\\Colors") as k:
            val, _ = winreg.QueryValueEx(k, "AccentColorMenu")
        r, g, b = (int(x) for x in str(val).split())
        r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
        return "#%02X%02X%02X" % (r, g, b)
    except Exception:
        return _FALLBACK_SEED


def system_is_dark() -> bool:
    """Windows 当前是否为深色模式。AppsUseLightTheme==0 视为深色；回退 True。"""
    if os.name != "nt":
        return True
    try:
        import winreg
        key = "Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        return int(val) == 0
    except Exception:
        return True


def resolve(st: dict) -> tuple:
    """据设置解析出 (seed, dark) 二元组，供主题构建与标题栏共用。

    seed : 跟随系统 -> Windows 强调色；否则用自定义 theme_seed。
    dark : theme_mode 明暗（'system' 时读系统明暗）。
    """
    if st.get("theme_follow_system"):
        seed = read_accent_color()
    else:
        seed = st.get("theme_seed") or _FALLBACK_SEED
    mode = st.get("theme_mode") or "dark"
    if mode == "system":
        dark = system_is_dark()
    else:
        dark = mode == "dark"
    return seed, dark
