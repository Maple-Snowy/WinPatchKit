"""GUI 入口（gui/app.py）：Flet App 组合器。

只做"装配"，不做具体实现——各职责已拆到独立模块：
   navigation.py   底部导航栏（NAV_ITEMS 数据驱动，可配置）
   titlebar.py     Win32/DWM 标题栏适配（深色 + 精确背景色）
   screenshot.py   CI 逐页截图驱动
   theme.py        文案 / 主题常量
   pages/          三个页面（home / module / settings）
   services.py     GUI↔引擎桥接层

启动方式：
   python main.py gui     （main.py 里 from gui.app import run）
   或  flet 环境下 ft.run(main)
"""
from __future__ import annotations

import flet as ft

from . import theme
from . import titlebar
from . import navigation
from . import screenshot
from .pages.home import HomePage
from .pages.module import ModulePage
from .pages.settings import SettingsPage


def main(page: ft.Page):
    page.title = theme.APP_TITLE
    page.padding = 0
    page.theme = ft.Theme(color_scheme_seed="#2E8B57")
    page.theme_mode = ft.ThemeMode.DARK
    try:
        page.window.width = 940
        page.window.height = 660
        page.window.min_width = 720
        page.window.min_height = 520
    except Exception:
        pass

    # 文件选择器（模块页 / 导入页共用）
    file_picker = ft.FilePicker()

    _refs = {}

    def on_changed():
        mp = _refs.get("module")
        if mp:
            mp.reload()

    def goto_tab(idx):
        _refs["switch"](idx)

    def do_import():
        # 主页「导入新模块」：切到模组页（idx=1）并弹导入框
        _refs["switch"](1)
        _refs["module"]._show_import_dialog()

    home = HomePage(page, on_changed, on_goto=goto_tab, on_import=do_import)
    module_page = ModulePage(page, on_changed, file_picker)
    settings_page = SettingsPage(page, on_changed)
    _refs["module"] = module_page

    pages = [home, module_page, settings_page]
    content = ft.Container(content=home.content, expand=True,
                           padding=ft.Padding.all(16))

    # 页面切换（导航栏 / 主页按钮 / CI 驱动共用）
    def switch_to(idx):
        content.content = pages[idx].content
        if idx == 0:
            home.reload()
        elif idx == 1:
            module_page.reload()
        nav.selected_index = idx
        page.update()

    def on_nav(e):
        switch_to(e.control.selected_index)

    # 导航栏由 navigation 模块据 NAV_ITEMS 生成（数据驱动）
    nav = navigation.build_navigation(on_nav)
    page.navigation_bar = nav
    _refs["switch"] = switch_to

    # 顶部标题栏：官方 AppBar（Page 一等属性），Flet 自动管理顶栏+内容区+底栏
    page.appbar = ft.AppBar(
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
                          on_click=lambda e: _toggle_theme(page))])

    page.add(ft.SafeArea(content))

    # 窗口创建后异步套深色标题栏（需 HWND 已存在，故延迟一帧）
    def _init_titlebar():
        import time
        time.sleep(1)
        titlebar.apply_titlebar(page.title,
                                page.theme_mode == ft.ThemeMode.DARK)
    page.run_thread(_init_titlebar)

    # 首页为默认页（不走 switch_to），启动后主动加载一次模块概览
    def _first_load():
        import time
        time.sleep(0.5)
        home.reload()
    page.run_thread(_first_load)

    # CI 截图驱动（仅 CI 环境激活，本地空跑）
    screenshot.start_screenshot_driver(page, switch_to)


def _toggle_theme(page: ft.Page):
    page.theme_mode = (ft.ThemeMode.LIGHT
                       if page.theme_mode == ft.ThemeMode.DARK
                       else ft.ThemeMode.DARK)
    titlebar.apply_titlebar(page.title, page.theme_mode == ft.ThemeMode.DARK)
    page.update()


def run():
    """阻塞式启动 GUI（由 `python main.py` 无参数或 `python main.py gui` 调用）。

    CI/自动化：设置环境变量 WINPATCHKIT_GUI_AUTO_CLOSE_AFTER=<秒数> 后，
    窗口打开该时长自动退出（用于 CI 截图验证）。
    """
    import os as _os

    delay = _os.environ.get("WINPATCHKIT_GUI_AUTO_CLOSE_AFTER", "").strip()
    if delay:
        def _auto_close():
            import os
            import time
            time.sleep(float(delay))
            os._exit(0)
        import threading
        t = threading.Thread(target=_auto_close, daemon=True)
        t.start()
    ft.run(main)