"""主题与界面文案常量。

界面面向最终用户，文案以中文为主；专有名词（DLL/PE/锚点/偏移/ID 等）保留原样。
模块的展示名（name）直接读取配置，中英文均可，GUI 不做任何语言假设。
"""
import flet as ft

APP_TITLE = "WinPatchKit"
APP_SUBTITLE = "Windows 二进制 Patch 工具"

# Material 3 种子色：Flet 自动从它推导整套配色（不手写配色逻辑）。
# #2E8B57 海绿；深色 surface ≈ #0F1511（titlebar 精确标题栏同色）。
SEED_COLOR = "#2E8B57"


def build_page_theme() -> ft.Theme:
    """据种子色构建页面主题（M3 自动推导配色）。"""
    return ft.Theme(color_scheme_seed=SEED_COLOR)

# 状态 -> 中文标签
STATUS_LABEL = {
    "pending": "检测中",
    "missing": "目标缺失",
    "ready": "可应用",
    "patched": "已打补丁",
    "partial": "部分失败",
    "failed": "无法应用",
    "parse_error": "配置错误",
}

# 状态 -> 徽章配色
STATUS_COLOR = {
    "pending": ft.Colors.GREY_400,
    "missing": ft.Colors.AMBER_700,
    "ready": ft.Colors.BLUE_600,
    "patched": ft.Colors.GREEN_600,
    "partial": ft.Colors.ORANGE_600,
    "failed": ft.Colors.RED_600,
    "parse_error": ft.Colors.GREY_600,
}
