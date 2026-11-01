"""顶部 AppBar（单一职责）：左上=当前页标题（动态）/ 右上=应用 LOGO。

MD3 应用风格：标题在左上角、随页面切换而变；品牌 LOGO 放右上角。
Flet 官方 Scaffold 机制：page.appbar 由 Flet 自动管理顶栏高度，不手搓。
明暗不再提供顶部切换按钮（改由「设置 → 个性化 → 主题模式」控制）。
"""
from __future__ import annotations

import flet as ft

from . import theme


def build_appbar(page: ft.Page, initial_title: str = "主页") -> ft.AppBar:
    """构建顶部 AppBar（左上动态标题 + 右上 LOGO，无明暗切换按钮）。

    标题 Text 句柄暂存于 page._appbar_title，供 set_title() 更新。
    """
    title = ft.Text(initial_title, size=20, weight=ft.FontWeight.BOLD)
    page._appbar_title = title
    return ft.AppBar(
        title=title,
        actions=[ft.Row(
            [ft.Icon(ft.Icons.BUILD_CIRCLE, color=ft.Colors.PRIMARY),
             ft.Text(theme.APP_TITLE, size=15, weight=ft.FontWeight.BOLD)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6)])


def set_title(page: ft.Page, label: str) -> None:
    """更新左上角当前页标题（不触发 update，由调用方统一刷新）。"""
    t = getattr(page, "_appbar_title", None)
    if t is not None:
        t.value = label
