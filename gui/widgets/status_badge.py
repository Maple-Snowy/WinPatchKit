"""状态徽章：把一个模块状态渲染成 MD3 outline 风格的小圆角标签。

outline 风格（用户拍板）：透明底 + 状态色描边 + 状态色文字，
比之前的实底白字更轻、更贴 MD3，深浅色下都不显重。
"""
import flet as ft

from .. import theme


def status_badge(status: str) -> ft.Container:
    label = theme.STATUS_LABEL.get(status, status)
    color = theme.STATUS_COLOR.get(status, ft.Colors.GREY)
    return ft.Container(
        content=ft.Text(label, size=12, weight=ft.FontWeight.BOLD,
                        color=color, no_wrap=True),
        border=ft.Border.all(1, color),
        border_radius=11,
        padding=ft.Padding.symmetric(horizontal=9, vertical=3),
        alignment="CENTER",  # 定宽容器内文字居中（长文案如「目标缺失」不再偏左）
    )
