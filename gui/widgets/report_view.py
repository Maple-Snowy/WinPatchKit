"""应用结果展示：把一条 ApplyOutcome 渲染成可折叠的 ExpansionTile。

B4：默认折叠，只露出「状态图标 + 模块id + 摘要」标题行；点开才看逐条明细，
避免多模块批量应用时结果区把整页撑高。失败项默认展开。
"""
import flet as ft


def _line_color(ln: str):
    if ln.startswith("FAIL"):
        return ft.Colors.RED_700
    if ln.startswith("OK"):
        return ft.Colors.GREEN_700
    if ln.startswith("SKIP"):
        return ft.Colors.GREY_600
    return ft.Colors.ON_SURFACE


def report_view(outcome) -> ft.ExpansionTile:
    icon = ft.Icons.CHECK_CIRCLE if outcome.ok else ft.Icons.ERROR
    color = ft.Colors.GREEN_600 if outcome.ok else ft.Colors.RED_600

    lines = [ft.Text(ln, size=12, font_family="monospace", color=_line_color(ln))
             for ln in outcome.lines]
    err = [ft.Text(outcome.error, size=12, color=ft.Colors.RED_700)] if outcome.error else []

    return ft.ExpansionTile(
        leading=ft.Icon(icon, color=color),
        title=ft.Text(outcome.module_id, weight=ft.FontWeight.BOLD, size=14),
        subtitle=ft.Text(outcome.summary, size=12, color=ft.Colors.GREY_600),
        trailing=None,
        controls_padding=ft.Padding(12, 4, 12, 12),
        tile_padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        # 失败/有错误默认展开，成功默认折叠（省空间）。
        expanded=not outcome.ok or bool(outcome.error),
        controls=ft.Column([ft.Divider(height=6), *err, *lines], spacing=4))