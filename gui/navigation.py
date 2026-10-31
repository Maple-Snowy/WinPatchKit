"""底部导航栏（独立职责模块，数据驱动可配置）。

所有 tab 集中在 NAV_ITEMS 一处声明：增删/改序 tab 只改这个列表，
build_navigation() 据此生成官方 ft.NavigationBar。
"""
from __future__ import annotations

import flet as ft

# 每个条目：label（文案）/ icon（未选中）/ selected（选中）。
# 主页=房子，模块=与主页"模块概览"卡同款 INVENTORY_2。
NAV_ITEMS = [
    {"label": "主页", "icon": ft.Icons.HOME_OUTLINED,
     "selected": ft.Icons.HOME},
    {"label": "模块", "icon": ft.Icons.INVENTORY_2_OUTLINED,
     "selected": ft.Icons.INVENTORY_2},
    {"label": "设置", "icon": ft.Icons.SETTINGS_OUTLINED,
     "selected": ft.Icons.SETTINGS},
]


def build_navigation(on_change) -> ft.NavigationBar:
    """据 NAV_ITEMS 生成导航栏，绑定 on_change（回调里读 e.control.selected_index）。"""
    return ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=item["icon"], selected_icon=item["selected"],
                label=item["label"])
            for item in NAV_ITEMS
        ],
        on_change=on_change)
