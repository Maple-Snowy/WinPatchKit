"""CI 逐页截图驱动（独立职责模块）。

仅在 CI 环境（设了 WINPATCHKIT_GUI_SCREENSHOT_DIR）激活，本地无此变量则空跑。
握手协议（该目录内文件）：
   _cmd    CI 写入，内容为 tab 索引（0/1/2）
   _ack    驱动切页并渲染后写入，内容为索引；CI 轮询到它才截屏
   _stop   CI 写入后驱动退出
切页用 page.run_task（事件循环内），保证 page.update() 合法。
"""
from __future__ import annotations

import os


def _park_cursor() -> None:
    """截图前把光标移到屏幕角落，避免悬停在带 tooltip 的控件上（CI 偶发 tooltip 入镜）。
    仅 Windows；异常静默。"""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.user32.SetCursorPos(1, 1)
    except Exception:
        pass


def start_screenshot_driver(page, switch_to) -> None:
    """挂 CI 截图驱动到 page 事件循环。未设环境变量时立即返回（零影响）。"""
    shot_dir = os.environ.get("WINPATCHKIT_GUI_SCREENSHOT_DIR", "").strip()
    if not shot_dir:
        return

    async def _loop():
        import asyncio
        os.makedirs(shot_dir, exist_ok=True)
        cmd_f  = os.path.join(shot_dir, "_cmd")
        ack_f  = os.path.join(shot_dir, "_ack")
        stop_f = os.path.join(shot_dir, "_stop")
        while True:
            if os.path.exists(stop_f):
                break
            if os.path.exists(cmd_f):
                idx = 0
                try:
                    with open(cmd_f, "r", encoding="utf-8") as f:
                        idx = int(f.read().strip())
                except Exception:
                    pass
                for p in (cmd_f, ack_f):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                try:
                    switch_to(idx)
                except Exception:
                    pass
                await asyncio.sleep(1.2)   # 等切换 + 内容渲染稳定
                _park_cursor()             # 把光标移出控件，避免 tooltip 入镜
                await asyncio.sleep(0.4)   # 等 tooltip 淡出 + 光标归位
                try:
                    with open(ack_f, "w", encoding="utf-8") as f:
                        f.write(str(idx))
                except OSError:
                    pass
            else:
                await asyncio.sleep(0.2)

    page.run_task(_loop)
