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

    nav = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED,
                selected_icon=ft.Icons.HOME,
                label="主页"),
            ft.NavigationBarDestination(
                icon=ft.Icons.INVENTORY_2_OUTLINED,
                selected_icon=ft.Icons.INVENTORY_2,
                label="模块"),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS, label="设置"),
        ])

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

    nav.on_change = on_nav
    page.navigation_bar = nav
    _refs["switch"] = switch_to

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

    # 首页为默认页（不走 switch_to），启动后主动加载一次模块概览
    def _first_load():
        import time
        time.sleep(0.5)
        home.reload()
    page.run_thread(_first_load)

    # CI 截图驱动：设了 WINPATCHKIT_GUI_SCREENSHOT_DIR 时激活。
    # 监听该目录下 _cmd 文件（内容为 tab 索引），读到即切换页面并写 _ack，
    # 由 CI 轮询 _ack 确认切页完成后再截屏。仅在 CI 环境生效，本地无此变量则空跑。
    _start_screenshot_driver(page, switch_to)


def _toggle_theme(page: ft.Page):
    page.theme_mode = (ft.ThemeMode.LIGHT
                       if page.theme_mode == ft.ThemeMode.DARK
                       else ft.ThemeMode.DARK)
    _apply_titlebar(page.title, page.theme_mode == ft.ThemeMode.DARK)
    page.update()


def _start_screenshot_driver(page: ft.Page, switch_to):
    """CI 截图驱动：监听命令文件，切换页面供 CI 逐页截屏。

    仅当环境变量 WINPATCHKIT_GUI_SCREENSHOT_DIR 已设置时激活（本地无此变量则空跑）。
    握手协议（目录内文件）：
      _cmd  CI 写入，内容为 tab 索引（0/1/2）
      _ack  驱动切页并渲染后写入，内容为索引；CI 轮询到它才截屏
      _stop CI 写入后驱动退出
    切换用 page.run_task（事件循环内），保证 page.update() 合法。
    """
    import os
    shot_dir = os.environ.get("WINPATCHKIT_GUI_SCREENSHOT_DIR", "").strip()
    if not shot_dir:
        return

    async def _loop():
        import asyncio
        os.makedirs(shot_dir, exist_ok=True)
        cmd_f  = os.path.join(shot_dir, "_cmd")
        ack_f  = os.path.join(shot_dir, "_ack")
        stop_f = os.path.join(shot_dir, "_stop")
        while True:
            if os.path.exists(stop_f):
                break
            if os.path.exists(cmd_f):
                idx = 0
                try:
                    with open(cmd_f, "r", encoding="utf-8") as f:
                        idx = int(f.read().strip())
                except Exception:
                    pass
                for p in (cmd_f, ack_f):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                try:
                    switch_to(idx)
                except Exception:
                    pass
                await asyncio.sleep(1.2)   # 等切换 + 内容渲染稳定
                try:
                    with open(ack_f, "w", encoding="utf-8") as f:
                        f.write(str(idx))
                except OSError:
                    pass
            else:
                await asyncio.sleep(0.2)

    page.run_task(_loop)


# ── DWM 标题栏适配 ──────────────────────────────────────────
# 让 Win32 标题栏跟随窗口明暗，并在 Win11 上精确贴合 Material 3 背景色。
#   DWMWA_USE_IMMERSIVE_DARK_MODE = 20  Win10 1903+ / Win11：深色标题栏开关
#   DWMWA_CAPTION_COLOR           = 35  Win11 22H2+：精确背景色（Win10 静默忽略）
# 背景色取自 Material 3 surface（种子 #2E8B57 推导）：
#   深色 #0F1511 / 浅色 #F8F9FF
_DWMWA_IMMERSIVE_DARK = 20
_DWMWA_CAPTION_COLOR  = 35
_CAPTION_DARK  = "#0F1511"
_CAPTION_LIGHT = "#F8F9FF"


def _colorref(rgb_hex: str) -> int:
    """'#RRGGBB' -> Windows COLORREF（0x00BBGGRR，顶字节为 0）。"""
    h = rgb_hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


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
        v_color = ctypes.c_uint(_colorref(_CAPTION_DARK if dark else _CAPTION_LIGHT))
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