"""GUI 装配编排（单一职责：把各子模块组装到 page）。

只做"调用与接线"，不实现具体逻辑——每个动作都委托给对应模块：
    window.setup_window          窗口初始化（主题/模式/尺寸，读设置）
    pages_view.build_page_controller   页面 + 切换控制
    navigation.build_navigation  底部导航栏
    appbar.build_appbar          顶部 AppBar（无明暗切换按钮）
    sys_theme.resolve            解析种子色 + 明暗（跟随系统 / 自定义）
    titlebar.apply_titlebar      标题栏适配（延迟到 HWND 就绪）
    screenshot.start_screenshot_driver   CI 逐页截图驱动
"""
from __future__ import annotations

import flet as ft

from . import window, appbar, navigation, sys_theme, titlebar, screenshot
from .services import get_settings
from .pages_view import build_page_controller


def main(page: ft.Page):
    """ft.run 的 page 回调：装配整个 GUI。"""
    # 1. 窗口初始化（标题 / 主题 / 主题模式 / 尺寸）
    window.setup_window(page)

    # 2. 页面 + 切换控制器
    ctrl = build_page_controller(page)

    # 3. 底部导航栏（数据驱动），并把实例注入 controller（供 switch_to 同步选中态）
    nav = navigation.build_navigation(ctrl.on_nav)
    ctrl.nav = nav
    page.navigation_bar = nav

    # 4. 顶部 AppBar（无明暗切换按钮）
    page.appbar = appbar.build_appbar(page)

    # 5. 内容区
    page.add(ft.SafeArea(ctrl.content))

    # 6. 延迟：标题栏适配（需 HWND 已创建，故延迟一帧）
    def _init_titlebar():
        import time
        time.sleep(1)
        seed, dark = sys_theme.resolve(get_settings())
        titlebar.apply_titlebar(page.title, dark, seed)
    page.run_thread(_init_titlebar)

    # 7. 延迟：首页为默认页（不走 switch_to），启动后主动加载一次模块概览
    def _first_load():
        import time
        time.sleep(0.5)
        ctrl.home.reload()
    page.run_thread(_first_load)

    # 8. CI 截图驱动（仅 CI 环境激活，本地空跑）
    screenshot.start_screenshot_driver(page, ctrl.switch_to)
