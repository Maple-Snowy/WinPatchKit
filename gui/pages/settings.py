"""设置页：目标基准目录 / 便捷导入目录 / 备份开关 / 备份后缀。

所有设置持久化到数据目录/settings.json（走 app.Settings），
修改即保存，不依赖额外的"保存"按钮。
"""
import flet as ft

from .. import services


class SettingsPage:
    def __init__(self, page: ft.Page, on_changed):
        self.page = page
        self.on_changed = on_changed
        self._fields = {}
        self.content = self._build()

    def _build(self) -> ft.Control:
        st = services.get_settings()

        def text_field(key, label, hint):
            f = ft.TextField(label=label, value=st.get(key) or "", hint_text=hint)
            self._fields[key] = f
            return f

        self.backup_switch = ft.Switch(label="应用补丁前备份原始文件",
                                       value=bool(st.get("backup", True)))
        self.backup_ext = text_field("backup_ext", "备份后缀", ".bak")

        def save_all(e=None):
            services.save_settings({
                "target_base_dir": self._fields["target_base_dir"].value or "",
                "auto_import_dir": self._fields["auto_import_dir"].value or None,
                "backup": bool(self.backup_switch.value),
                "backup_ext": self._fields["backup_ext"].value or ".bak",
            })
            self.page.show_dialog(ft.SnackBar(ft.Text("设置已保存")))
            if self.on_changed:
                self.on_changed()

        self.backup_switch.on_change = lambda e: save_all()
        for f in self._fields.values():
            f.on_submit = lambda e: save_all()

        save_btn = ft.Button("保存设置", on_click=save_all)

        return ft.Column(
            [
                ft.Text("设置", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=8),
                ft.Text("修改会自动保存到 数据目录/settings.json",
                        size=12, color=ft.Colors.GREY_500),
                ft.Container(height=10),
                text_field("target_base_dir", "目标文件基准目录",
                           "模块 target 相对路径的解析基准（如 OsEasy 安装目录）"),
                text_field("auto_import_dir", "便捷导入目录",
                           "启动时自动把该目录里的 .toml 搬入并加载（留空=工具所在目录）"),
                self.backup_switch,
                self.backup_ext,
                ft.Container(height=10),
                save_btn,
                ft.Container(height=20),
            ],
            scroll=ft.ScrollMode.AUTO, expand=True)