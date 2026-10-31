"""顶部 AppBar（单一职责）：应用 LOGO + 标题/副标题 + 明暗切换按钮。

Flet 官方 Scaffold 机制：page.appbar 由 Flet 自动管理顶栏高度，不手搓。
切换按钮的回调由调用方注入（保持本模块只做 UI 构建）。
"""
from __future__ import annotations

import flet as ft

from . import theme


def build_appbar(page: ft.Page, on_toggle_theme) -> ft.AppBar:
    """构建顶部 AppBar。on_toggle_theme 为点击"切换明暗"的回调（接收 event）。"""
    return ft.AppBar(
        title=ft.Row(
            [ft.Icon(ft.Icons.BUILD_CIRCLE, color=ft.Colors.PRIMARY),
             ft.Column(
                 [ft.Text(theme.APP_TITLE, size=18,
                          weight=ft.FontWeight.BOLD),
                  ft.Text(theme.APP_SUBTITLE, size=11,
                          color=ft.Colors.GREY_500)],
                 spacing=0,
                 horizontal_alignment=ft.CrossAxisAlignment.START)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10),
        actions=[
            ft.IconButton(ft.Icons.DARK_MODE, tooltip="切换明暗",
                          on_click=on_toggle_theme)])