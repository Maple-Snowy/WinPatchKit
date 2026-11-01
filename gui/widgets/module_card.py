"""模块卡片：展示单个模块（状态图标 + 中文功能名 + 目标 + id/version
+ 状态徽章 + 明细 + 删除按钮），hover 时底色微抬升。

返回 (card, checkbox, badge_box, detail_text, icon_box)：
  - card:        整卡（GestureDetector 包裹，带 hover 变色）
  - checkbox:    勾选框
  - badge_box:   状态徽章容器（探测后更新 .content）
  - detail_text: 状态明细文案（探测后更新 .value）
  - icon_box:    标题前的状态图标容器（探测后更新 .content）
"""
import flet as ft
import os

from .status_badge import status_badge


# 状态 -> 标题前图标（C3）
_STATUS_ICON = {
    "pending":     (ft.Icons.HOURGLASS_TOP, ft.Colors.GREY_500),
    "missing":     (ft.Icons.CANCEL_OUTLINED, ft.Colors.AMBER_700),
    "ready":       (ft.Icons.DONE_OUTLINED, ft.Colors.BLUE_600),
    "patched":     (ft.Icons.CHECK_CIRCLE, ft.Colors.GREEN_600),
    "partial":     (ft.Icons.WARNING, ft.Colors.ORANGE_600),
    "failed":      (ft.Icons.ERROR_OUTLINE, ft.Colors.RED_600),
    "parse_error": (ft.Icons.CODE_OFF, ft.Colors.GREY_600),
}


def status_icon(status: str) -> ft.Icon:
    icon, color = _STATUS_ICON.get(status, (ft.Icons.HOURGLASS_TOP, ft.Colors.GREY_500))
    return ft.Icon(icon, size=18, color=color)


def make_card(info, on_delete, on_detail):
    """构建一个模块卡片。

    on_delete: 点击删除按钮的回调；on_detail: 点击卡片主体（空白/文字区）的回调
    （打开详情弹层）。点 checkbox / 删除按钮不会触发 on_detail。
    """
    title = info.name or info.id
    if info.parse_error:
        line1 = f"配置错误: {info.parse_error}"
        line1_color = ft.Colors.RED_700
        line2 = None
    else:
        line1 = os.path.basename(info.target) or "-"
        line1_color = ft.Colors.GREY_600
        line2 = f"id={info.id}   ·   v{info.version or '-'}"

    checkbox = ft.Checkbox(value=False, disabled=bool(info.parse_error))
    badge_box = ft.Container(content=status_badge("pending"), width=92)
    icon_box = ft.Container(content=status_icon("pending"), width=22)
    detail_text = ft.Text("检测中…", size=11, color=ft.Colors.GREY_500,
                          no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
    delete_btn = ft.IconButton(ft.Icons.DELETE_OUTLINED, icon_size=18,
                               tooltip="删除模块", icon_color=ft.Colors.GREY_500,
                               on_click=on_delete)

    sub_col = ft.Column(
        [ft.Text(title, weight=ft.FontWeight.BOLD, size=15, no_wrap=True,
                 overflow=ft.TextOverflow.ELLIPSIS),
         ft.Text(line1, size=12, color=line1_color, no_wrap=True,
                 overflow=ft.TextOverflow.ELLIPSIS)] +
        ([ft.Text(line2, size=11, color=ft.Colors.GREY_500, no_wrap=True,
                  overflow=ft.TextOverflow.ELLIPSIS)] if line2 else []) +
        [detail_text],
        spacing=3, expand=True)

    inner = ft.Container(
        content=ft.Row(
            [checkbox,
             ft.Container(width=4),
             icon_box,
             ft.Container(width=6),
             sub_col,
             ft.Container(width=10),
             badge_box,
             delete_btn],
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)

    # C1 hover 反馈：进 -> 抬升一档表面色，出 -> 还原（GestureDetector 成对事件）；
    # 点卡片主体 -> 打开详情（A1）。checkbox / 删除按钮各自独立消费点击。
    gd = ft.GestureDetector(
        content=inner,
        on_tap=on_detail,
        on_enter=lambda e: setattr(inner, "bgcolor", ft.Colors.SURFACE_CONTAINER),
        on_exit=lambda e: setattr(inner, "bgcolor", ft.Colors.SURFACE_CONTAINER_LOW))

    return gd, checkbox, badge_box, detail_text, icon_box
