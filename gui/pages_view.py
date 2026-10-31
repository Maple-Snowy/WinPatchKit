"""页面实例化 + tab 切换控制（单一职责：页面栈与导航切换）。

集中管理三个页面实例、共享 FilePicker、内容容器，以及 switch_to / on_nav。
底部导航栏（navigation）与本模块解耦：本模块提供 on_nav 回调与 switch_to，
导航栏实例由 bootstrap 构建后注入到 controller.nav。
"""
from __future__ import annotations

import flet as ft

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
        self.content = ft.Container(content=self.home.content, expand=True,
                                    padding=ft.Padding.all(16))

    def switch_to(self, idx: int) -> None:
        """切到第 idx 个 tab 并刷新其数据（导航栏 / 主页按钮 / CI 驱动共用）。"""
        self.content.content = self.pages[idx].content
        if idx == 0:
            self.home.reload()
        elif idx == 1:
            self._module.reload()
        if self.nav is not None:
            self.nav.selected_index = idx
        self.page.update()

    def on_nav(self, e) -> None:
        """底部导航栏点击回调。"""
        self.switch_to(e.control.selected_index)


def build_page_controller(page: ft.Page) -> PageController:
    return PageController(page)