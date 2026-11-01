"""应用结果展示：把一条 ApplyOutcome 渲染成带头 + 逐条明细的卡片。"""
import flet as ft


def _line_color(ln: str):
    if ln.startswith("FAIL"):
        return ft.Colors.RED_700
    if ln.startswith("OK"):
        return ft.Colors.GREEN_700
    if ln.startswith("SKIP"):
        return ft.Colors.GREY_600
    return ft.Colors.ON_SURFACE


def report_view(outcome) -> ft.Container:
    icon = ft.Icons.CHECK_CIRCLE if outcome.ok else ft.Icons.ERROR
    color = ft.Colors.GREEN_600 if outcome.ok else ft.Colors.RED_600
    header = ft.Row(
        [ft.Icon(icon, color=color),
         ft.Text(outcome.module_id, weight=ft.FontWeight.BOLD, size=15),
         ft.Container(width=10),
         ft.Text(outcome.summary, color=ft.Colors.GREY_600, size=13)],
        vertical_alignment=ft.CrossAxisAlignment.CENTER)
    err_lines = [ft.Text(outcome.error, color=ft.Colors.RED_700, size=12)] if outcome.error else []
    lines = [ft.Text(ln, size=12, font_family="monospace", color=_line_color(ln))
             for ln in outcome.lines]
    return ft.Container(
        content=ft.Column([header, ft.Divider(height=8), *err_lines, *lines], spacing=4),
        padding=12, border_radius=10,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
