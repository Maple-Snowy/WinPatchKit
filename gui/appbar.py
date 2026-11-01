"""顶部 AppBar（单一职责）：左上=当前页图标 + 标题（动态）。

MD3 应用风格：图标 + 标题在左上角、随页面切换而变，图标与底部导航栏
选中态一致。顶栏仅此一处，无 LOGO/按钮。
Flet 官方 Scaffold 机制：page.appbar 由 Flet 自动管理顶栏高度，不手搓。
明暗不再提供顶部切换按钮（改由「设置 → 个性化 → 主题模式」控制）。
"""
from __future__ import annotations

import flet as ft

from . import navigation

# 页面标题 -> 顶部图标（与底部导航栏选中态一致，视觉统一）
_PAGE_ICON = {
    "主页": ft.Icons.HOME,
    "模块": ft.Icons.INVENTORY_2,
    "设置": ft.Icons.SETTINGS,
}
_DEFAULT_ICON = ft.Icons.DASHBOARD_OUTLINED


def _title_icon(label: str) -> ft.Icon:
    return ft.Icon(_PAGE_ICON.get(label, _DEFAULT_ICON), size=22,
                   color=ft.Colors.PRIMARY)


def build_appbar(page: ft.Page, initial_title: str = "主页") -> ft.AppBar:
    """构建顶部 AppBar（左上「图标 + 标题」）。

    图标 Icon / 标题 Text 句柄暂存于 page._appbar_icon / page._appbar_title，
    供 set_title() 更新。
    """
    icon = _title_icon(initial_title)
    title = ft.Text(initial_title, size=20, weight=ft.FontWeight.BOLD)
    page._appbar_icon = icon
    page._appbar_title = title
    return ft.AppBar(
        title=ft.Row([icon, ft.Container(width=8), title],
                     alignment=ft.MainAxisAlignment.CENTER,
                     vertical_alignment=ft.CrossAxisAlignment.CENTER))


def set_title(page: ft.Page, label: str) -> None:
    """更新左上角当前页图标 + 标题（不触发 update，由调用方统一刷新）。"""
    icon = getattr(page, "_appbar_icon", None)
    if icon is not None:
        icon.icon = _PAGE_ICON.get(label, _DEFAULT_ICON)
    t = getattr(page, "_appbar_title", None)
    if t is not None:
        t.value = label