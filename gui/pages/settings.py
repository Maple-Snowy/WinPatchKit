"""设置页：双列布局（左=基本设置 / 右=个性化），顶部标题+底部保存按钮跨整行。

所有设置持久化到数据目录/settings.json（走 app.Settings），修改即保存。
个性化区全部使用 Flet 原生控件（Dropdown / Switch / TextField / 可点击色块），
保存后立即应用（重建页面主题 + 重刷 DWM 标题栏）。
"""
import re
import flet as ft

from .. import services, theme, sys_theme, titlebar

# 预设种子色（顺序即展示顺序；最后一个色块后接"自定义"取色输入）
PRESET_SEEDS = [
    ("#2E8B57", "海绿"),
    ("#1E88E5", "天蓝"),
    ("#5E35B1", "紫"),
    ("#E53935", "红"),
    ("#FB8C00", "橙"),
    ("#00897B", "青"),
    ("#8E24AA", "洋红"),
    ("#6D4C41", "棕"),
]

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def _normalize_hex(v: str):
    """把用户输入规整为 '#RRGGBB'（大写）；非法返回 None。"""
    m = _HEX_RE.match((v or "").strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.upper()


class SettingsPage:
    def __init__(self, page: ft.Page, on_changed):
        self.page = page
        self.on_changed = on_changed
        self._fields = {}
        self._seed_selected = theme.SEED_COLOR
        self._chip_boxes = []   # [(color_box, hex), ...] 供选中态高亮
        self.content = self._build()

    # ---------------- 构建 ----------------
    def _build(self) -> ft.Control:
        st = services.get_settings()

        def text_field(key, label, hint):
            f = ft.TextField(label=label, value=st.get(key) or "", hint_text=hint)
            self._fields[key] = f
            return f

        # ---- 左列：基本设置 ----
        self.backup_switch = ft.Switch(label="应用补丁前备份原始文件",
                                       label_position=ft.LabelPosition.LEFT,
                                       value=bool(st.get("backup", True)))
        self.backup_ext = text_field("backup_ext", "备份后缀", ".bak")

        left_col = ft.Column(
            [
                ft.Text("基本设置", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=6),
                text_field("target_base_dir", "目标文件基准目录",
                           "模块 target 相对路径的解析基准（如 OsEasy 安装目录）"),
                text_field("auto_import_dir", "便捷导入目录",
                           "启动时自动把该目录里的 .toml 搬入并加载（留空=工具所在目录）"),
                self.backup_switch,
                self.backup_ext,
            ],
            spacing=10,
            expand=True,
        )

        # ---- 右列：个性化 ----
        self.mode_dropdown = ft.Dropdown(
            label="主题模式",
            options=[
                ft.DropdownOption(key="system", text="跟随系统"),
                ft.DropdownOption(key="light", text="浅色"),
                ft.DropdownOption(key="dark", text="深色"),
            ],
            value=st.get("theme_mode") or "dark",
            on_select=lambda e: self._save(),
        )

        self.follow_switch = ft.Switch(
            label="主题色跟随系统（读取 Windows 强调色）",
            label_position=ft.LabelPosition.LEFT,
            value=bool(st.get("theme_follow_system", False)),
            on_change=lambda e: self._save(),
        )
        current = st.get("theme_seed") or theme.SEED_COLOR
        self._seed_selected = current

        chips = []
        for hexc, name in PRESET_SEEDS:
            box = ft.Container(
                width=40, height=40, bgcolor=hexc, border_radius=8,
                border=ft.Border.all(
                    3, ft.Colors.ON_SURFACE if hexc == current
                    else ft.Colors.TRANSPARENT))
            self._chip_boxes.append((box, hexc))
            chips.append(ft.Container(
                content=ft.Column([box, ft.Text(name, size=11)],
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                  spacing=4),
                padding=8, border_radius=12,
                on_click=lambda e, h=hexc: self._pick_seed(h)))

        # 自定义取色：原生 HEX 输入框（Flet 1.0.5 无可视化取色盘，用 TextField 输 #RRGGBB）
        self.custom_seed = ft.TextField(
            label="自定义 (#RRGGBB)", value=current, width=150,
            on_submit=lambda e: self._pick_hex())
        chips.append(self.custom_seed)

        # 开关打开(跟随系统)时折叠隐藏自定义区；关闭时展示
        self.seed_grid = ft.Container(
            content=ft.Row(chips, wrap=True, spacing=8, run_spacing=8,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=14,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            visible=not self.follow_switch.value,
        )

        right_col = ft.Column(
            [
                ft.Text("个性化", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=6),
                self.mode_dropdown,
                self.follow_switch,
                self.seed_grid,
            ],
            spacing=10,
            expand=True,
        )

        # 文本框 / 备份开关：提交即保存
        self.backup_switch.on_change = lambda e: self._save()
        for f in self._fields.values():
            f.on_submit = lambda e: self._save()

        save_btn = ft.FilledButton("保存设置", on_click=lambda e: self._save())

        # ---- 组装：顶部标题 + 双列主体（各 expand 平分宽度） + 底部保存按钮 ----
        body = ft.Row(
            [left_col, ft.Container(width=24), right_col],
            vertical_alignment=ft.CrossAxisAlignment.START,
            expand=True,
        )
        # 页面标题「设置」由顶部 AppBar 承担（MD3 风格），内容区不再重复。
        return ft.Column(
            [
                body,
                ft.Container(height=10),
                ft.Row([save_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(height=10),
            ],
            scroll=ft.ScrollMode.AUTO, expand=True)

    # ---------------- 交互 ----------------
    def _pick_seed(self, hexc: str):
        """点击预设色块：选中并保存应用。"""
        self._seed_selected = hexc
        self.custom_seed.value = hexc
        self._mark_chips()
        self._save()

    def _pick_hex(self):
        """自定义 HEX 输入（回车提交）：合法则选中并保存应用。"""
        n = _normalize_hex(self.custom_seed.value)
        if n:
            self._seed_selected = n
            self._mark_chips()
        self._save()

    def _mark_chips(self):
        low = self._seed_selected.lower()
        for box, h in self._chip_boxes:
            box.border = ft.Border.all(
                3, ft.Colors.ON_SURFACE if h.lower() == low
                else ft.Colors.TRANSPARENT)

    # ---------------- 保存 + 即时应用 ----------------
    def _save(self):
        data = {
            "target_base_dir": self._fields["target_base_dir"].value or "",
            "auto_import_dir": self._fields["auto_import_dir"].value or None,
            "backup": bool(self.backup_switch.value),
            "backup_ext": self._fields["backup_ext"].value or ".bak",
            "theme_mode": self.mode_dropdown.value or "dark",
            "theme_follow_system": bool(self.follow_switch.value),
            "theme_seed": self._seed_selected or theme.SEED_COLOR,
        }
        services.save_settings(data)
        self._apply_theme(data)
        self.page.show_dialog(ft.SnackBar(ft.Text("设置已保存")))
        if self.on_changed:
            self.on_changed()

    def _apply_theme(self, st: dict):
        """保存后立即应用主题：重建页面主题 + 主题模式 + 重刷标题栏。"""
        seed, dark = sys_theme.resolve(st)
        self.page.theme = theme.build_page_theme(seed)
        self.page.theme_mode = theme.theme_mode_enum(st.get("theme_mode") or "dark")
        self.seed_grid.visible = not bool(self.follow_switch.value)
        self.page.update()

        def _tb():
            titlebar.apply_titlebar(self.page.title, dark, seed)
        self.page.run_thread(_tb)