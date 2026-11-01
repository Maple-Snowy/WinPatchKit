"""模块卡片：展示单个模块（中文功能名 + 目标 + id/version + 状态徽章）。"""
import flet as ft
import os

from .status_badge import status_badge


def make_card(info):
    """构建一个模块卡片。

    返回 (card, checkbox, badge_box, detail_text)。
    调用方负责：绑定 checkbox.on_change；探测完成后更新 badge_box.content
    与 detail_text.value。
    """
    title = info.name or info.id
    if info.parse_error:
        sub = f"配置错误: {info.parse_error}"
        sub_color = ft.Colors.RED_700
    else:
        ver = info.version or "-"
        sub = f"{os.path.basename(info.target)}   ·   id={info.id}   ·   v{ver}"
        sub_color = ft.Colors.GREY_600

    checkbox = ft.Checkbox(value=False, disabled=bool(info.parse_error))
    badge_box = ft.Container(content=status_badge("pending"), width=80)
    detail_text = ft.Text("检测中…", size=11, color=ft.Colors.GREY_500, no_wrap=True)

    card = ft.Container(
        content=ft.Row(
            [checkbox,
             ft.Column(
                 [ft.Text(title, weight=ft.FontWeight.BOLD, size=15),
                  ft.Text(sub, size=12, color=sub_color, no_wrap=True,
                          overflow=ft.TextOverflow.ELLIPSIS)],
                 spacing=3, expand=True),
             badge_box,
             ft.Container(width=8),
             detail_text],
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border_radius=10,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )
    return card, checkbox, badge_box, detail_text
