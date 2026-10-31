"""进程启动入口（单一职责：可选自动关闭 + ft.run）。"""
from __future__ import annotations

import os

import flet as ft

from .bootstrap import main

# CI/自动化：设此环境变量为秒数，窗口打开该时长后进程自动退出
AUTO_CLOSE_ENV = "WINPATCHKIT_GUI_AUTO_CLOSE_AFTER"


def run() -> None:
    """阻塞式启动 GUI（由 `python main.py` 无参数或 `python main.py gui` 调用）。"""
    delay = os.environ.get(AUTO_CLOSE_ENV, "").strip()
    if delay:
        def _auto_close():
            import time
            time.sleep(float(delay))
            os._exit(0)
        import threading
        threading.Thread(target=_auto_close, daemon=True).start()
    ft.run(main)