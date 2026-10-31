"""模块页：模块列表 + 勾选 + 批量应用 + 应用结果展示。

布局（从上到下，整体放滚动区）：
  1) 基准目录条：当前"目标文件基准目录" + [浏览] + [保存]
  2) 工具条：[ 全选 ][ 取消 ][ 已选 N ]   [ 刷新状态 ][ 应用补丁 ]
  3) 模块卡片列表（状态徽章 + 明细）
  4) 应用结果区（apply 后出现）
"""
import flet as ft

from .. import services
from ..widgets.module_card import make_card
from ..widgets.report_view import report_view
from ..widgets.status_badge import status_badge


class ModulePage:
    def __init__(self, page: ft.Page, on_changed, file_picker: ft.FilePicker):
        self.page = page
        self.on_changed = on_changed        # 设置变更 / 数据刷新后通知 entry
        self.file_picker = file_picker      # 目录选择（复用 entry 的 FilePicker 实例）
        self.infos = []
        self.widgets = {}                   # index -> (checkbox, badge_box, detail_text)
        self.content = self._build()

    # ---------------------------------------------------------------- UI
    def _build(self) -> ft.Control:
        page = self.page
        # 1) 基准目录条：输入框(expand 撑满) + [浏览] + [保存]
        # label 用短文案，说明放 hint_text；避免长 label 换行且右侧留白。
        self.base_field = ft.TextField(
            label="目标文件基准目录",
            hint_text="模块 target 相对路径的解析基准（留空=工具所在目录）")
        browse_btn = ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="选择目录",
                                   on_click=self._pick_base)
        save_btn = ft.IconButton(ft.Icons.SAVE, tooltip="保存基准目录",
                                 on_click=self._save_base)
        base_row = ft.Container(
            content=ft.Row(
                [ft.Container(self.base_field, expand=True),
                 ft.Container(width=6),
                 browse_btn,
                 save_btn],
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border=ft.Border.all(1, ft.Colors.OUTLINE), border_radius=10)

        # 2) 工具条
        self.sel_count = ft.Text("已选 0", size=13, color=ft.Colors.GREY_600)
        self.apply_btn = ft.Button(
            ft.Row([ft.Icon(ft.Icons.BUILD), ft.Text("  应用补丁")]),
            disabled=True)
        self.apply_btn.on_click = self._apply
        refresh_btn = ft.TextButton(
            ft.Row([ft.Icon(ft.Icons.REFRESH), ft.Text("  刷新状态")]),
            on_click=lambda e: self.probe())
        self.tool_row = ft.Container(
            content=ft.Row(
                [ft.TextButton("全选", on_click=lambda e: self._set_all(True)),
                 ft.TextButton("取消", on_click=lambda e: self._set_all(False)),
                 self.sel_count,
                 ft.Container(expand=True),
                 refresh_btn,
                 self.apply_btn],
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=4, vertical=2))

        # 3) 模块列表
        self.module_list = ft.Column(spacing=8)

        # 4) 结果区
        self.report_box = ft.Column(spacing=8, visible=False)

        return ft.Column(
            [base_row,
             ft.Container(height=10),
             self.tool_row,
             ft.Container(height=10),
             ft.Column([self.module_list], spacing=0, expand=True),
             self.report_box],
            spacing=0, expand=True)

    # ---------------------------------------------------------------- 数据刷新
    def render_list(self):
        self.infos = services.list_modules()
        self.widgets = {}
        self.module_list.controls.clear()
        page = self.page
        if not self.infos:
            self.module_list.controls.append(
                ft.Container(
                    content=ft.Column(
                        [ft.Icon(ft.Icons.INBOX, size=40,
                                 color=ft.Colors.GREY_400),
                         ft.Text("还没有导入模块", size=14,
                                 color=ft.Colors.GREY_500),
                         ft.Text("请前往「导入配置」手动导入，或把 .toml 放到工具同级目录后重启。",
                                 size=12, color=ft.Colors.GREY_500)],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6),
                    padding=40))
        else:
            for i, info in enumerate(self.infos):
                card, checkbox, badge_box, detail_text = make_card(info)
                checkbox.on_change = self._on_check
                self.widgets[i] = (checkbox, badge_box, detail_text)
                self.module_list.controls.append(card)
        self._update_sel()
        page.update()

    def reload(self):
        """重读模块 + 重探状态（导入后 / 切回模块页时调用）。"""
        self.base_field.value = services.get_settings()["target_base_dir"] or ""
        self.render_list()
        self.probe()

    # ---------------------------------------------------------------- 状态探测
    def probe(self):
        page, infos, widgets = self.page, self.infos, self.widgets
        if not infos:
            page.update()
            return

        def run():
            results = services.probe_all(self.base_field.value or "", infos)
            for i, info in enumerate(infos):
                if i not in widgets:
                    continue
                badge_box, detail_text = widgets[i][1], widgets[i][2]
                st = results.get(info.id)
                badge_box.content = status_badge(st.status) if st else status_badge("missing")
                detail_text.value = st.detail if st else "未知"
            page.update()

        page.run_thread(run)

    # ---------------------------------------------------------------- 勾选
    def selected_infos(self):
        return [self.infos[i] for i, cb in self.widgets.items()
                if cb.value and i < len(self.infos)]

    def _set_all(self, val):
        for cb, _, _ in self.widgets.values():
            cb.value = val
        self._update_sel()

    def _on_check(self, e):
        self._update_sel()

    def _update_sel(self):
        n = sum(1 for cb, _, _ in self.widgets.values() if cb.value)
        self.sel_count.value = f"已选 {n}"
        self.apply_btn.disabled = n == 0
        self.page.update()

    # ---------------------------------------------------------------- 基准目录
    async def _pick_base(self, e):
        """点[浏览]：弹 Windows 原生目录选择框，选中后回填输入框并重新探测。"""
        try:
            path = await self.file_picker.get_directory_path(
                dialog_title="选择目标文件基准目录",
                initial_directory=self.base_field.value or None)
        except Exception:
            return
        if not path:
            return
        self.base_field.value = path
        self.page.update()
        self._save_base(e)

    def _save_base(self, e):
        services.save_settings({"target_base_dir": self.base_field.value or ""})
        self.page.show_dialog(ft.SnackBar(ft.Text("基准目录已保存，正在刷新状态…")))
        self.probe()
        if self.on_changed:
            self.on_changed()

    # ---------------------------------------------------------------- 应用
    def _apply(self, e):
        sel = self.selected_infos()
        if not sel:
            return
        st = services.get_settings()
        self.apply_btn.disabled = True
        self.page.update()

        def run():
            outcomes = services.apply_many(
                self.base_field.value or "", sel,
                st["backup"], st["backup_ext"])
            self.report_box.controls.clear()
            self.report_box.controls.extend(report_view(o) for o in outcomes)
            done = sum(1 for o in outcomes if o.ok)
            ok = done == len(outcomes)
            self.page.show_dialog(ft.SnackBar(
                ft.Text(f"完成：{done}/{len(outcomes)} 个模块成功" if ok
                        else f"完成，但有失败（{done}/{len(outcomes)}）"),
                bgcolor=ft.Colors.GREEN_700 if ok else ft.Colors.RED_700))
            self.report_box.visible = True
            self.apply_btn.disabled = False
            self.probe()          # 应用后重探状态
            self.page.update()

        self.page.run_thread(run)