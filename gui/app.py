"""GUI 入口（gui/app.py）：纯导入 / 转发，不含任何实现逻辑。

对外只暴露：
    from gui.app import run    # 启动 GUI（main.py 调用）
    from gui.app import main   # ft.run 的 page 回调（一般不直接用）

各职责分门别类在独立子文件，每个只负责一项：
    window.py         窗口初始化（标题/主题/尺寸）
    theme.py          主题定义（种子色 + build_page_theme）+ 文案常量
    theme_switch.py   明暗主题切换
    appbar.py         顶部 AppBar
    navigation.py     底部导航栏（NAV_ITEMS 数据驱动）
    titlebar.py       Win32/DWM 标题栏适配
    pages_view.py     页面实例化 + tab 切换控制
    screenshot.py     CI 逐页截图驱动
    bootstrap.py      装配编排（组装以上各模块）
    boot.py           进程启动（可选自动关闭 + ft.run）

启动方式：
    python main.py gui     （main.py 里 from gui.app import run）
"""
from .boot import run          # noqa: F401  (启动入口)
from .bootstrap import main    # noqa: F401  (装配回调)