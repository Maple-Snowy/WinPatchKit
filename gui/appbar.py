"""顶部 AppBar（单一职责）：应用 LOGO + 标题/副标题。

Flet 官方 Scaffold 机制：page.appbar 由 Flet 自动管理顶栏高度，不手搓。
明暗不再提供顶部切换按钮（改由「设置 → 个性化 → 主题模式」控制）。
"""
from __future__ import annotations

import flet as ft

from . import theme


def build_appbar(page: ft.Page) -> ft.AppBar:
    """构建顶部 AppBar（LOGO + 标题/副标题，无 actions）。"""
    return ft.AppBar(
        title=ft.Row(
            [ft.Icon(ft.Icons.BUILD_CIRCLE, color=ft.Colors.PRIMARY),
             ft.Column(
                 [ft.Text(theme.APP_TITLE, size=18, weight=ft.FontWeight.BOLD),
                  ft.Text(theme.APP_SUBTITLE, size=11, color=ft.Colors.GREY_500)],
                 spacing=0,
                 horizontal_alignment=ft.CrossAxisAlignment.START)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10))
