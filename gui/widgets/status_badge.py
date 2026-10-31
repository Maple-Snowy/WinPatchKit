"""状态徽章：把一个模块状态渲染成带颜色的中文小圆角标签。"""
import flet as ft

from .. import theme


def status_badge(status: str) -> ft.Container:
    label = theme.STATUS_LABEL.get(status, status)
    color = theme.STATUS_COLOR.get(status, ft.Colors.GREY)
    return ft.Container(
        content=ft.Text(label, size=12, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE, no_wrap=True),
        bgcolor=color,
        border_radius=11,
        padding=ft.Padding.symmetric(horizontal=9, vertical=3),
    )
