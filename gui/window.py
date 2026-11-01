"""窗口初始化（单一职责）：标题 / 主题 / 主题模式 / 尺寸。"""
from __future__ import annotations

import flet as ft

from . import theme, sys_theme
from .services import get_settings

# 窗口默认尺寸
WINDOW_WIDTH = 940
WINDOW_HEIGHT = 660


def setup_window(page: ft.Page) -> None:
    """初始化窗口外观（在 ft.run 的 page 回调里、页面构建前调用）。

    主题与明暗模式从设置解析：种子色（自定义 / 跟随系统强调色）+ theme_mode。
    """
    page.title = theme.APP_TITLE
    page.padding = 0

    st = get_settings()
    seed, _dark = sys_theme.resolve(st)
    page.theme = theme.build_page_theme(seed)
    page.theme_mode = theme.theme_mode_enum(st.get("theme_mode") or "dark")

    try:
        page.window.width = WINDOW_WIDTH
        page.window.height = WINDOW_HEIGHT
    except Exception:
        pass
