"""GUI 入口：装配窗口、底部导航栏与三个页面，并处理页面间刷新。

启动方式：
  python main.py gui
  或  flet 环境下 ft.run(main)
"""
import flet as ft

from . import theme
from .pages.home import HomePage
from .pages.settings import SettingsPage
from .pages.import_page import ImportPage


def main(page: ft.Page):
    page.title = theme.APP_TITLE
    page.padding = 0
    page.theme_mode = ft.ThemeMode.SYSTEM
    try:
        page.window.width = 940
        page.window.height = 660
        page.window.min_width = 720
        page.window.min_height = 520
    except Exception:
        pass  # 非桌面端（如 web/测试）无窗口句柄时忽略

    state = {"home": None}

    def on_changed():
        # 设置变更 / 导入完成后，刷新主页（重读模块 + 重探状态）
        home = state.get("home")
        if home is not None:
            home.reload()

    # 文件选择器（导入页使用）。1.0 里 service 构造即注册，无需加 page.overlay；
    # 这里保存引用并显式传给导入页，复用同一实例。
    file_picker = ft.FilePicker()

    home = HomePage(page, on_changed)
    import_page = ImportPage(page, on_changed, file_picker)
    settings_page = SettingsPage(page, on_changed)
    state["home"] = home

    pages = [home, import_page, settings_page]
    content = ft.Container(content=home.content, expand=True,
                           padding=ft.Padding.all(16))

    nav = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME,
                label="模块"),
            ft.NavigationBarDestination(
                icon=ft.Icons.DRIVE_FILE_MOVE_OUTLINED,
                selected_icon=ft.Icons.DRIVE_FILE_MOVE, label="导入"),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS, label="设置"),
        ])

    def on_nav(e):
        idx = e.control.selected_index
        content.content = pages[idx].content
        if idx == 0:
            home.reload()
        page.update()

    nav.on_change = on_nav

    # 标题栏
    header = ft.Container(
        content=ft.Row(
            [ft.Icon(ft.Icons.BUILD_CIRCLE, color=ft.Colors.BLUE_600),
             ft.Column(
                 [ft.Text(theme.APP_TITLE, size=18,
                          weight=ft.FontWeight.BOLD),
                  ft.Text(theme.APP_SUBTITLE, size=11,
                          color=ft.Colors.GREY_500)],
                 spacing=0),
             ft.Container(expand=True),
             ft.IconButton(ft.Icons.DARK_MODE, tooltip="切换明暗",
                           on_click=lambda e: _toggle_theme(page))],
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE)))

    page.add(ft.SafeArea(ft.Column(
        [header,
         ft.Column([content], expand=True, scroll=ft.ScrollMode.AUTO),
         nav],
        spacing=0, expand=True)))

    # 初始加载
    home.reload()


def _toggle_theme(page: ft.Page):
    page.theme_mode = (ft.ThemeMode.LIGHT
                       if page.theme_mode == ft.ThemeMode.DARK
                       else ft.ThemeMode.DARK)
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