"""页面实例化 + tab 切换控制（单一职责：页面栈与导航切换）。

集中管理三个页面实例、共享 FilePicker、内容容器，以及 switch_to / on_nav。
底部导航栏（navigation）与本模块解耦：本模块提供 on_nav 回调与 switch_to，
导航栏实例由 bootstrap 构建后注入到 controller.nav。
切换 tab 时同步更新左上角 AppBar 标题（MD3 应用风格）。
"""
from __future__ import annotations

import flet as ft

from . import appbar
from .navigation import NAV_ITEMS
from .pages.home import HomePage
from .pages.module import ModulePage
from .pages.settings import SettingsPage


class PageController:
    """三个页面的容器 + 切换逻辑。"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.file_picker = ft.FilePicker()   # 模块页 / 导入共用，构造即注册
        self.nav = None                      # 导航栏实例，由 bootstrap 注入
        self._module = None

        def on_changed():
            # 设置变更 / 数据刷新后，让模块页重读
            if self._module:
                self._module.reload()

        def goto_tab(idx):
            self.switch_to(idx)

        def do_import():
            # 主页「导入新模块」：切到模组页（idx=1）并弹导入框
            self.switch_to(1)
            self._module._show_import_dialog()

        self.home = HomePage(page, on_changed,
                             on_goto=goto_tab, on_import=do_import)
        self._module = ModulePage(page, on_changed, self.file_picker)
        self._settings = SettingsPage(page, on_changed)
        self.pages = [self.home, self._module, self._settings]
        # 内容区统一套一层 ListView 作为唯一滚动视口（Flet 官方滚动控件）：
        # 页面内容按自然高度排布，超出窗口高度时可上下滚动。
        # 不各页自建 Column(scroll)：Column 的 scroll 主轴是无限高度约束，
        # 内嵌 expand=True 的子项会与之冲突，导致"内容超出却滚不动"。
        # 注意：ListView 的子项参数是 controls（列表），没有 content 参数。
        self.content = ft.ListView(
            controls=[self.home.content],
            expand=True,
            spacing=0,
            padding=ft.Padding.all(16))

    def switch_to(self, idx: int) -> None:
        """切到第 idx 个 tab 并刷新其数据（导航栏 / 主页按钮 / CI 驱动共用）。"""
        # ListView 切页：替换 controls 列表（ListView 无 content 属性）。
        self.content.controls = [self.pages[idx].content]
        if idx == 0:
            self.home.reload()
        elif idx == 1:
            self._module.reload()
        if self.nav is not None:
            self.nav.selected_index = idx
        appbar.set_title(self.page, NAV_ITEMS[idx]["label"])
        self.page.update()

    def on_nav(self, e) -> None:
        """底部导航栏点击回调。"""
        self.switch_to(e.control.selected_index)


def build_page_controller(page: ft.Page) -> PageController:
    return PageController(page)
