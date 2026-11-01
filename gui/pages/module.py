"""模块页：模块列表 + 筛选/搜索 + 勾选 + 详情/删除/恢复/导出 + 批量应用。

布局（从上到下，主体列表区内部滚动，B6）：
   1) 状态计数摘要（D3）
   2) 筛选 Chip 组（A2 七态）+ 搜索框（A7）+ 打开目录（A5）
   3) 工具条（左=选择类 / 右=操作类，B2；次按钮 tonal，C5）
   4) 模块卡片列表（内滚动；hover 抬升 C1；状态图标 C3；删除 A4）
   5) 应用 / 预览结果区（可折叠 ExpansionTile，B4）

快捷键（D4）：Ctrl+R 刷新状态。
"""
import asyncio
import flet as ft

from .. import services
from ..widgets.module_card import make_card
from ..widgets.report_view import report_view
from ..widgets.status_badge import status_badge


# 筛选 Chip：key -> 文案（顺序即展示顺序；"all" 恒在最前）
FILTERS = [
    ("all", "全部"),
    ("ready", "可应用"),
    ("patched", "已打补丁"),
    ("missing", "目标缺失"),
    ("failed", "无法应用"),
    ("partial", "部分"),
    ("parse_error", "配置错误"),
]


class ModulePage:
    def __init__(self, page: ft.Page, on_changed, file_picker: ft.FilePicker):
        self.page = page
        self.on_changed = on_changed        # 设置变更 / 数据刷新后通知 app
        self.file_picker = file_picker      # 目录/文件选择（复用 app 的 FilePicker 实例）
        self.infos = []
        self.widgets = {}                   # index -> (checkbox, badge_box, detail_text, icon_box)
        self.cards = {}                     # index -> 外层 GestureDetector（用于筛选显隐）
        self.statuses = {}                  # index -> 状态字符串（探测后回填）
        self.filter_status = "all"
        self.search = ""
        self.content = self._build()
        # D4 快捷键（app 未占用 on_key_down，安全挂载）
        page.on_key_down = self._on_key

    # ---------------------------------------------------------------- 构建
    def _build(self) -> ft.Control:
        # 1) 状态计数摘要（D3）
        self.summary_text = ft.Text("共 0 个模块", size=12, color=ft.Colors.GREY_500)

        # 3) 筛选 Chip 组 + 搜索框 + 打开目录
        self.chips = {}
        for key, label in FILTERS:
            chip = ft.Chip(label=label, selected=(key == "all"),
                           on_select=lambda e, k=key: self._on_filter(k))
            self.chips[key] = chip
        self.search_field = ft.TextField(
            hint_text="搜索模块名 / id / 目标文件…",
            prefix_icon=ft.Icons.SEARCH, suffix_icon=ft.Icons.SEARCH_OFF,
            on_change=self._on_search)
        open_dir_btn = ft.IconButton(
            ft.Icons.FOLDER_OPEN, tooltip="打开 configs 目录（A5）",
            on_click=lambda e: services.open_configs_dir())
        filter_card = ft.Container(
            content=ft.Column(
                [ft.Row(list(self.chips.values()), wrap=True, spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER),
                 ft.Container(height=8),
                 ft.Row([ft.Container(self.search_field, expand=True),
                         ft.Container(width=4), open_dir_btn],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER)],
                spacing=0),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=14, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)

        # 4) 工具条（B2 分组：左选择类 / 右操作类；C5 次按钮 tonal）
        self.sel_count = ft.Text("已选 0", size=13, color=ft.Colors.GREY_600)
        select_ready_btn = ft.TextButton(
            ft.Row([ft.Icon(ft.Icons.CHECKLIST_OUTLINED), ft.Text("全选可应用")],
                   alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            on_click=lambda e: self._select_ready())          # A3
        clear_btn = ft.TextButton("取消", on_click=lambda e: self._set_all(False))
        self.apply_btn = ft.FilledButton(
            ft.Row([ft.Icon(ft.Icons.BUILD), ft.Text("应用补丁")],
                   alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            disabled=True)
        self.apply_btn.on_click = self._apply
        self.preview_btn = ft.FilledTonalButton(
            ft.Row([ft.Icon(ft.Icons.PREVIEW_OUTLINED), ft.Text("预览")],
                   alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            disabled=True, on_click=lambda e: self._preview())  # A8
        refresh_btn = ft.IconButton(ft.Icons.REFRESH, tooltip="刷新状态",
                                    on_click=lambda e: self.probe())
        export_btn = ft.IconButton(ft.Icons.UPLOAD_FILE,
                                   tooltip="导出选中配置（A9）",
                                   on_click=lambda e: self._export())
        restore_all_btn = ft.IconButton(ft.Icons.RESTORE,
                                        tooltip="一键恢复所有目标文件（用备份覆盖，A6）",
                                        on_click=lambda e: self._restore_all())
        import_btn = ft.FilledTonalButton(
            ft.Row([ft.Icon(ft.Icons.FILE_DOWNLOAD), ft.Text("导入")],
                   alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            on_click=lambda e: self._show_import_dialog())
        self.tool_row = ft.Row(
            [select_ready_btn, clear_btn, self.sel_count,
             ft.Container(expand=True),
             refresh_btn, self.preview_btn, export_btn, restore_all_btn,
             import_btn, self.apply_btn],
            vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # 5) 模块列表（内滚动容器；结果区也放这里随滚，B4/B6）
        self.report_title = ft.Text("应用结果", size=14, weight=ft.FontWeight.BOLD)
        self.report_box = ft.Column([self.report_title], spacing=8, visible=False)
        self.module_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

        body = ft.Column([self.module_list, self.report_box], spacing=8,
                         expand=True, scroll=ft.ScrollMode.AUTO)

        return ft.Column(
            [self.summary_text, ft.Container(height=8),
             filter_card, ft.Container(height=10),
             self.tool_row, ft.Container(height=10),
             ft.Container(body, expand=True)],
            spacing=0, expand=True)

    # ---------------------------------------------------------------- 数据刷新
    def render_list(self):
        self.infos = services.list_modules()
        self.widgets = {}
        self.cards = {}
        self.statuses = {}
        self.module_list.controls.clear()
        page = self.page
        if not self.infos:
            # B5 空态 + CTA
            self.module_list.controls.append(
                ft.Container(
                    content=ft.Column(
                        [ft.Icon(ft.Icons.INBOX, size=44, color=ft.Colors.GREY_400),
                         ft.Text("还没有导入模块", size=14, color=ft.Colors.GREY_500),
                         ft.Text("导入 .toml 配置后即可在这里管理、探测与应用。",
                                 size=12, color=ft.Colors.GREY_500),
                         ft.Container(height=8),
                         ft.FilledTonalButton(
                             ft.Row([ft.Icon(ft.Icons.FILE_DOWNLOAD),
                                     ft.Text("导入模块")],
                                    alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                             on_click=lambda e: self._show_import_dialog())],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6),
                    padding=40))
        else:
            for i, info in enumerate(self.infos):
                gd, checkbox, badge_box, detail_text, icon_box = make_card(
                    info,
                    on_delete=lambda e, ii=info: self._confirm_delete(ii),
                    on_detail=lambda e, ii=info: self._show_detail(ii))  # A1
                checkbox.on_change = self._on_check
                self.widgets[i] = (checkbox, badge_box, detail_text, icon_box)
                self.cards[i] = gd
                self.statuses[i] = "pending"
                self.module_list.controls.append(gd)
        self._update_summary()
        self._update_sel()
        page.update()

    def reload(self):
        """重读模块 + 重探状态（导入后 / 切回模块页时调用）。"""
        self.filter_status = "all"
        self.search = ""
        self.search_field.value = ""
        for k, chip in self.chips.items():
            chip.selected = (k == "all")
        self.render_list()
        self.probe()

    # ---------------------------------------------------------------- 状态探测
    def probe(self):
        page, infos, widgets = self.page, self.infos, self.widgets
        if not infos:
            page.update()
            return

        def run():
            results = services.probe_all(self._base(), infos)
            for i, info in enumerate(infos):
                if i not in widgets:
                    continue
                _cb, badge_box, detail_text, icon_box = widgets[i]
                st = results.get(info.id)
                status = st.status if st else "missing"
                self.statuses[i] = status
                # badge_box.content 是 Row([弹性块, badge, 弹性块])，只替换中间
                # 的 badge 子项，保留居中结构（不能整体替换 content，否则居中丢失）。
                badge_box.content.controls[1] = status_badge(status)
                detail_text.value = st.detail if st else "未知"
                from ..widgets.module_card import status_icon
                icon_box.content = status_icon(status)
            self._update_summary()
            self._apply_filter()
            page.update()

        page.run_thread(run)

    # ---------------------------------------------------------------- 筛选 / 搜索
    def _on_filter(self, key):
        self.filter_status = key
        for k, chip in self.chips.items():
            chip.selected = (k == key)
        self._apply_filter()

    def _on_search(self, e):
        self.search = (e.control.value or "").strip()
        self._apply_filter()

    def _apply_filter(self):
        q = self.search.lower()
        for i in range(len(self.infos)):
            gd = self.cards.get(i)
            if gd is None:
                continue
            if self.filter_status != "all" and self.statuses.get(i) != self.filter_status:
                gd.visible = False
                continue
            if q:
                info = self.infos[i]
                hay = f"{info.name} {info.id} {info.target} {info.parse_error}".lower()
                if q not in hay:
                    gd.visible = False
                    continue
            gd.visible = True
        self.page.update()

    def _update_summary(self):
        total = len(self.infos)
        c = {s: 0 for s in ("ready", "patched", "missing", "partial",
                            "failed", "parse_error")}
        for s in self.statuses.values():
            if s in c:
                c[s] += 1
        parts = [f"共 {total}"]
        if c["ready"]:
            parts.append(f"可应用 {c['ready']}")
        if c["patched"]:
            parts.append(f"已打补丁 {c['patched']}")
        if c["missing"]:
            parts.append(f"缺失 {c['missing']}")
        if c["partial"]:
            parts.append(f"部分 {c['partial']}")
        if c["failed"]:
            parts.append(f"失败 {c['failed']}")
        if c["parse_error"]:
            parts.append(f"配置错误 {c['parse_error']}")
        self.summary_text.value = "  ·  ".join(parts)

    # ---------------------------------------------------------------- 导入
    def _show_import_dialog(self):
        pick_btn = ft.TextButton(
            ft.Row([ft.Icon(ft.Icons.FOLDER_OPEN), ft.Text("选择 .toml 文件")],
                   alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            on_click=self._pick)
        auto_btn = ft.TextButton(
            ft.Row([ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED),
                    ft.Text("便捷导入（扫描工具/设置目录）")],
                   alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            on_click=self._auto)
        dlg = ft.AlertDialog(
            title=ft.Text("导入模块配置"),
            content=ft.Column(
                [ft.Text(
                     "· 选文件：挑选一个或多个 .toml，复制进 configs/\n"
                     "· 便捷导入：扫描工具同级目录 / 便捷导入目录\n"
                     "· 以模块ID判重：同 id 已存在则覆盖，否则新增",
                     size=13, color=ft.Colors.GREY_400),
                 ft.Container(height=10),
                 ft.Row([pick_btn, auto_btn], spacing=12, wrap=True)],
                spacing=0))
        self.page.show_dialog(dlg)

    def _pop(self):
        try:
            self.page.pop_dialog()
        except Exception:
            pass

    async def _pick(self, e):
        self._pop()
        try:
            files = await self.file_picker.pick_files(
                allow_multiple=True, dialog_title="选择模块配置",
                allowed_extensions=["toml"])
        except Exception:
            return
        if not files:
            return
        done, failed = services.import_files([f.path for f in files])
        self._finish_import(done, failed)

    async def _auto(self, e):
        self._pop()
        try:
            names = await asyncio.to_thread(services.auto_import)
            done = [(n, "已搬入 configs/") for n in names]
            failed = []
        except Exception as ex:
            done, failed = [], [("便捷导入", str(ex))]
        if not done:
            done = [("（无新配置）", "目标目录里没有可导入的 .toml")]
        self._finish_import(done, failed)

    def _finish_import(self, done, failed):
        n_ok = sum(1 for d in done if d[0] != "（无新配置）")
        if failed:
            msg = f"导入完成，{n_ok} 成功 / {len(failed)} 失败"
        else:
            msg = f"已导入 {n_ok} 个模块"
        self.page.show_dialog(ft.SnackBar(ft.Text(msg)))
        self.reload()
        if self.on_changed:
            self.on_changed()

    # ---------------------------------------------------------------- 勾选
    def selected_infos(self):
        return [self.infos[i] for i, w in self.widgets.items()
                if w[0].value and i < len(self.infos)]

    def _set_all(self, val):
        for cb, _bb, _dt, _ib in self.widgets.values():
            cb.value = val
        self._update_sel()

    def _select_ready(self):
        """A3：只勾选状态为「可应用」的模块。"""
        for i, (cb, _bb, _dt, _ib) in self.widgets.items():
            cb.value = (self.statuses.get(i) == "ready")
        self._update_sel()

    def _on_check(self, e):
        self._update_sel()

    def _update_sel(self):
        n = sum(1 for w in self.widgets.values() if w[0].value)
        self.sel_count.value = f"已选 {n}"
        self.apply_btn.disabled = n == 0
        self.preview_btn.disabled = n == 0
        self.page.update()

    # ---------------------------------------------------------------- 基准目录
    def _base(self) -> str:
        """目标文件基准目录：从 settings.target_base_dir 读取（无 GUI 入口，
        由底层 settings 写入，未来新方案另行赋值）。"""
        try:
            return (services.get_settings().get("target_base_dir") or "").strip()
        except Exception:
            return ""

    # ---------------------------------------------------------------- 详情弹层（A1 + D1 + A6 按模块）
    def _show_detail(self, info):
        page = self.page
        detail_body = ft.Column(
            [ft.Row([ft.ProgressRing(width=22, height=22)]),
             ft.Container(height=8),
             ft.Text("正在探测 patch 点…", size=13, color=ft.Colors.GREY_500)],
            spacing=0)
        dlg = ft.AlertDialog(
            title=ft.Text(info.name or info.id),
            content=ft.Container(content=detail_body, width=460, padding=10))
        page.show_dialog(dlg)

        def run():
            d = services.get_module_detail(self._base(), info)
            base = ft.Row(
                [status_badge(d.status), ft.Container(width=10),
                 ft.Text(f"id={d.module_id}   ·   v{d.version or '-'}",
                         size=12, color=ft.Colors.GREY_600)],
                vertical_alignment=ft.CrossAxisAlignment.CENTER)
            tgt_label = ft.Text("目标文件", size=11, color=ft.Colors.GREY_500)
            tgt_path = ft.Text(d.target or "（空）", size=13,
                               font_family="monospace", selectable=True)
            tgt_state = ft.Text("存在" if d.target_exists else "不存在",
                                size=12,
                                color=ft.Colors.GREEN_600 if d.target_exists
                                else ft.Colors.RED_600)
            patch_tiles = self._patch_rows(d)
            patches_tile = ft.ExpansionTile(
                leading=ft.Icon(ft.Icons.DESCRIPTION, size=20,
                                color=ft.Colors.GREY_500),
                title=ft.Text(f"{len(d.patches)} 个 patch 点",
                              weight=ft.FontWeight.BOLD, size=13),
                expanded=True,
                controls=ft.Column(patch_tiles, spacing=6))
            restore_btn = ft.FilledTonalButton(
                ft.Row([ft.Icon(ft.Icons.RESTORE_FROM_TRASH),
                        ft.Text("用备份恢复此模块目标文件")],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                on_click=lambda e: self._restore_one(info))
            detail_body.controls = [
                base, ft.Container(height=12),
                tgt_label, ft.Container(height=2), tgt_path,
                ft.Row([tgt_state], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=12),
                patches_tile, ft.Container(height=10),
                ft.Row([restore_btn], alignment=ft.MainAxisAlignment.END)]
            page.update()

        page.run_thread(run)

    def _patch_rows(self, d):
        rows = []
        for p in d.patches:
            if p.status == "ok":
                icon, color = ft.Icons.CHECK, ft.Colors.GREEN_600
            elif p.status == "skip":
                icon, color = ft.Icons.REMOVE, ft.Colors.GREY_500
            else:
                icon, color = ft.Icons.ERROR, ft.Colors.RED_600
            off = f"@0x{p.offset:X}" if p.offset >= 0 else "定位失败"
            rows.append(ft.Row(
                [ft.Icon(icon, size=16, color=color), ft.Container(width=6),
                 ft.Column([ft.Text(p.id, size=12, weight=ft.FontWeight.BOLD,
                                    font_family="monospace"),
                            ft.Text(p.message, size=11, color=ft.Colors.GREY_500)],
                           spacing=2, expand=True),
                 ft.Text(off, size=11, font_family="monospace",
                         color=ft.Colors.GREY_500)],
                vertical_alignment=ft.CrossAxisAlignment.CENTER))
        if not rows:
            rows = [ft.Text("（无法探测 patch 点）", size=12,
                            color=ft.Colors.GREY_500)]
        return rows

    def _restore_one(self, info):
        st = services.get_settings()
        self._pop()
        msg = services.restore_backup(self._base(), info,
                                      st["backup_ext"])
        self.page.show_dialog(ft.SnackBar(ft.Text(msg)))
        self.probe()

    def _restore_all(self):
        """A6 一键全恢复：用各自备份覆盖回所有可解析模块的目标文件。"""
        infos = [i for i in self.infos if not i.parse_error]
        if not infos:
            self.page.show_dialog(ft.SnackBar(ft.Text("没有可恢复的模块")))
            return
        st = services.get_settings()

        def run():
            okn = 0
            for i in infos:
                msg = services.restore_backup(self._base(), i,
                                              st["backup_ext"])
                if msg.startswith("已恢复"):
                    okn += 1
            self.page.show_dialog(ft.SnackBar(
                ft.Text(f"恢复完成：{okn}/{len(infos)} 个目标已还原")))
            self.probe()

        self.page.run_thread(run)

    # ---------------------------------------------------------------- 删除（A4 软删除）
    def _confirm_delete(self, info):
        page = self.page
        perm_box = ft.Checkbox(value=False)
        perm_row = ft.Row(
            [perm_box,
             ft.Text("彻底删除（不进回收站，不可恢复）", size=13)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER)
        dlg = ft.AlertDialog(
            title=ft.Text("删除模块？"),
            content=ft.Column(
                [ft.Text(f"「{info.name or info.id}」的配置文件将被移除。", size=14),
                 ft.Container(height=6),
                 ft.Text("已备份的原始文件不受影响（保存在 backups/）。",
                         size=12, color=ft.Colors.GREY_500),
                 ft.Container(height=12), perm_row],
                spacing=0),
            actions=[
                ft.TextButton("取消", on_click=self._pop),
                ft.FilledButton(
                    "删除",
                    on_click=lambda e: self._do_delete(info, perm_box.value))],
            actions_alignment=ft.MainAxisAlignment.END)
        page.show_dialog(dlg)

    def _do_delete(self, info, permanent: bool):
        self._pop()
        try:
            msg = services.delete_module(info.file, permanent=permanent)
        except Exception as ex:
            msg = f"删除失败：{ex}"
        self.page.show_dialog(ft.SnackBar(ft.Text(msg)))
        self.reload()
        if self.on_changed:
            self.on_changed()

    # ---------------------------------------------------------------- 导出（A9）
    async def _export(self, e):
        sel = self.selected_infos()
        if not sel:
            self.page.show_dialog(ft.SnackBar(ft.Text("请先勾选要导出的模块")))
            return
        try:
            path = await self.file_picker.get_directory_path(
                dialog_title="选择导出目录")
        except Exception:
            return
        if not path:
            return
        files = [i.file for i in sel]

        def run():
            try:
                res = services.export_selected(files, path)
                self.page.show_dialog(ft.SnackBar(
                    ft.Text(f"已导出 {len(res)} 个配置到 {path}")))
            except Exception as ex:
                self.page.show_dialog(ft.SnackBar(ft.Text(f"导出失败：{ex}")))

        self.page.run_thread(run)

    # ---------------------------------------------------------------- 预览（A8 dry-run）
    def _preview(self, e):
        sel = self.selected_infos()
        if not sel:
            return
        self._set_report_title("预览（dry-run，不会写入磁盘）")

        def run():
            outs = services.preview_many(self._base(), sel)
            self._render_report(outs)
            self.page.update()

        self.page.run_thread(run)

    # ---------------------------------------------------------------- 应用（C4 进度态）
    def _apply(self, e):
        sel = self.selected_infos()
        if not sel:
            return
        st = services.get_settings()
        self._set_report_title("应用结果")
        # C4 进度态：按钮内容换成转圈 + 文案
        self.apply_btn.content = ft.Row(
            [ft.ProgressRing(width=16, height=16), ft.Text("应用中…")],
            alignment=ft.MainAxisAlignment.CENTER, spacing=8)
        self.apply_btn.disabled = True
        self.preview_btn.disabled = True
        self.page.update()

        def run():
            outcomes = services.apply_many(
                self._base(), sel, st["backup"], st["backup_ext"])
            self._render_report(outcomes)
            done = sum(1 for o in outcomes if o.ok)
            ok = done == len(outcomes)
            self.page.show_dialog(ft.SnackBar(
                ft.Text(f"完成：{done}/{len(outcomes)} 个模块成功" if ok
                        else f"完成，但有失败（{done}/{len(outcomes)}）"),
                bgcolor=ft.Colors.GREEN_700 if ok else ft.Colors.RED_700))
            self.apply_btn.content = ft.Row(
                [ft.Icon(ft.Icons.BUILD), ft.Text("应用补丁")],
                alignment=ft.MainAxisAlignment.CENTER, spacing=8)
            self._update_sel()
            self.probe()          # 应用后重探状态
            self.page.update()

        self.page.run_thread(run)

    # ---------------------------------------------------------------- 结果区
    def _set_report_title(self, t):
        self.report_title.value = t

    def _render_report(self, outcomes):
        self.report_box.controls = [self.report_title]
        self.report_box.controls.extend(report_view(o) for o in outcomes)
        self.report_box.visible = True

    # ---------------------------------------------------------------- 快捷键（D4）
    def _on_key(self, e):
        if e.ctrl and e.key and e.key.lower() == "r":
            self.probe()