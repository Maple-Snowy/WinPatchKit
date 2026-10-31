"""导入页：手动导入 .toml + 便捷导入。

导入以模块ID判重（同 id 已存在则覆盖），逻辑全部复用 app.modules，
本页只负责触发与结果展示。

Flet 1.0 约定：
- FilePicker 是 service，构造即注册，直接持有实例即可（无需加 page.overlay）。
- pick_files() 是 awaitable，直接返回 FilePickerFile 列表（每项含 .path / .name）。
- 阻塞的文件搬移用 asyncio.to_thread 卸载，避免卡住事件循环。
"""
import asyncio
import flet as ft

from .. import services


class ImportPage:
    def __init__(self, page: ft.Page, on_changed, file_picker: ft.FilePicker):
        self.page = page
        self.on_changed = on_changed
        self.file_picker = file_picker
        self.result_box = ft.Column(spacing=6)
        self.content = self._build()

    def _build(self) -> ft.Control:
        pick_btn = ft.Button(
            ft.Row([ft.Icon(ft.Icons.FOLDER_OPEN), ft.Text("  选择 .toml 文件导入")]),
            on_click=self._pick)
        auto_btn = ft.Button(
            ft.Row([ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED),
                    ft.Text("  便捷导入（扫描工具/设置目录）")]),
            on_click=self._auto)

        tip = ft.Text(
            "· 手动导入：挑选一个或多个 .toml，复制进数据目录/configs/\n"
            "· 以模块ID判重：同 id 已存在则覆盖（可更换文件名），否则新增\n"
            "· 便捷导入：把 .toml 放到工具同级目录（或设置的便捷导入目录）后点此按钮",
            size=12, color=ft.Colors.GREY_600)

        return ft.Column(
            [
                ft.Text("导入配置", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=8),
                tip,
                ft.Container(height=12),
                ft.Row([pick_btn, auto_btn], spacing=10, wrap=True),
                ft.Container(height=14),
                self.result_box,
                ft.Container(height=20),
            ],
            scroll=ft.ScrollMode.AUTO, expand=True)

    async def _pick(self, e):
        try:
            files = await self.file_picker.pick_files(
                allow_multiple=True,
                dialog_title="选择模块配置",
                allowed_extensions=["toml"])
        except Exception:
            return
        if not files:
            return
        done, failed = services.import_files([f.path for f in files])
        self._show_results(done, failed)
        self._notify()

    async def _auto(self, e):
        try:
            names = await asyncio.to_thread(services.auto_import)
            done = [(n, "已搬入 configs/") for n in names]
            failed = []
        except Exception as ex:
            done, failed = [], [("便捷导入", str(ex))]
        if not done:
            self._show_results([("（无新配置）", "目标目录里没有可导入的 .toml")], [])
        else:
            self._show_results(done, failed)
        self._notify()

    def _show_results(self, done, failed):
        self.result_box.controls.clear()
        if done:
            self.result_box.controls.append(ft.Text("已导入：",
                size=13, weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREEN_700))
            for name, _desc in done:
                self.result_box.controls.append(
                    ft.Text(f"  ✓ {name}", size=12))
        if failed:
            self.result_box.controls.append(ft.Text("失败：",
                size=13, weight=ft.FontWeight.BOLD,
                color=ft.Colors.RED_700))
            for name, msg in failed:
                self.result_box.controls.append(
                    ft.Text(f"  ✗ {name}：{msg}", size=12,
                            color=ft.Colors.RED_700))

    def _notify(self):
        self.page.show_dialog(ft.SnackBar(ft.Text("模块已更新")))
        if self.on_changed:
            self.on_changed()