"""GUI 入口：装配窗口、底部导航栏与三个页面，并处理页面间刷新。

启动方式：
  python main.py gui
  或  flet 环境下 ft.run(main)
"""
import flet as ft

from . import theme
from .pages.home import HomePage
from .pages.module import ModulePage
from .pages.settings import SettingsPage
from .pages.import_page import ImportPage


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

    home = HomePage(page)
    module_page = ModulePage(page, on_changed, file_picker)
    import_page = ImportPage(page, on_changed, file_picker)
    settings_page = SettingsPage(page, on_changed)
    _refs["module"] = module_page

    pages = [home, module_page, import_page, settings_page]
    content = ft.Container(content=home.content, expand=True,
                           padding=ft.Padding.all(16))

    nav = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.INFO_OUTLINED, selected_icon=ft.Icons.INFO,
                label="主页"),
            ft.NavigationBarDestination(
                icon=ft.Icons.LIST_OUTLINED, selected_icon=ft.Icons.LIST,
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
        if idx == 1:
            module_page.reload()
        page.update()

    nav.on_change = on_nav
    page.navigation_bar = nav

    # 顶部标题栏：官方 AppBar（Page 一等属性），Flet 自动管理顶栏+内容区+底栏，
    # 不再手搓 Container+Row 伪造顶栏。
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
        _apply_titlebar(page.title, page.theme_mode == ft.ThemeMode.DARK)
    page.run_thread(_init_titlebar)


def _toggle_theme(page: ft.Page):
    page.theme_mode = (ft.ThemeMode.LIGHT
                       if page.theme_mode == ft.ThemeMode.DARK
                       else ft.ThemeMode.DARK)
    _apply_titlebar(page.title, page.theme_mode == ft.ThemeMode.DARK)
    page.update()


# ── DWM 标题栏适配 ──────────────────────────────────────────
# Win10 1903+ / Win11: DWMWA_USE_IMMERSIVE_DARK_MODE (20)
# Win11 专属:           DWMWA_CAPTION_COLOR (35)  精确背景色（Win10 静默忽略）
# 背景色取自深色 Material 3 surface（种子 #2E8B57 推导）: #0F1511
# DWM 颜色格式 = ABGR (DWORD): 0xFF + B + G + R
_DWMWA_IMMERSIVE_DARK = 20
_DWMWA_CAPTION_COLOR  = 35
_CAPTION_ABGR         = 0xFF11150F  # #0F1511 → A=FF B=11 G=15 R=0F


def _apply_titlebar(title: str, dark: bool):
    """通过 Win32 + DWM API 让标题栏匹配窗口深色/浅色模式。"""
    import ctypes
    from ctypes import wintypes

    user32  = ctypes.windll.user32
    dwmapi  = ctypes.windll.dwmapi

    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum(h, _):
        n = user32.GetWindowTextLengthW(h)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, buf, n + 1)
            if buf.value == title:
                found.append(h)
        return True

    user32.EnumWindows(_enum, 0)

    for h in found:
        v_dark = ctypes.c_int(1 if dark else 0)
        dwmapi.DwmSetWindowAttribute(
            h, _DWMWA_IMMERSIVE_DARK,
            ctypes.byref(v_dark), ctypes.sizeof(v_dark))
        # Win11: 精确标题栏背景色（Win10 上此属性不存在，调用静默失败，无副作用）
        v_color = ctypes.c_uint(_CAPTION_ABGR if dark else 0xFFF8F9FF)
        dwmapi.DwmSetWindowAttribute(
            h, _DWMWA_CAPTION_COLOR,
            ctypes.byref(v_color), ctypes.sizeof(v_color))


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