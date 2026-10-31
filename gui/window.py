"""窗口初始化（单一职责）：标题 / 主题 / 主题模式 / 尺寸。"""
from __future__ import annotations

import flet as ft

from . import theme

# 窗口默认与最小尺寸
WINDOW_WIDTH = 940
WINDOW_HEIGHT = 660
WINDOW_MIN_WIDTH = 720
WINDOW_MIN_HEIGHT = 520


def setup_window(page: ft.Page) -> None:
    """初始化窗口外观（调用方在 ft.run 的 page 回调里、页面构建前调用）。"""
    page.title = theme.APP_TITLE
    page.padding = 0
    page.theme = theme.build_page_theme()
    page.theme_mode = ft.ThemeMode.DARK
    try:
        page.window.width = WINDOW_WIDTH
        page.window.height = WINDOW_HEIGHT
        page.window.min_width = WINDOW_MIN_WIDTH
        page.window.min_height = WINDOW_MIN_HEIGHT
    except Exception:
        pass