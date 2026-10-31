"""明暗主题切换（单一职责）：切 page.theme_mode 并同步 DWM 标题栏。"""
from __future__ import annotations

import flet as ft

from . import titlebar


def toggle_theme(page: ft.Page) -> None:
    """在明暗间切换主题，并同步标题栏颜色（标题栏需跟随明暗）。"""
    page.theme_mode = (ft.ThemeMode.LIGHT
                       if page.theme_mode == ft.ThemeMode.DARK
                       else ft.ThemeMode.DARK)
    titlebar.apply_titlebar(page.title, page.theme_mode == ft.ThemeMode.DARK)
    page.update()