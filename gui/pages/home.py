"""起始页（主页）：左「系统信息」/ 右「模块概览」双卡片仪表盘。

两张卡片以窗口中央为界一左一右平分宽度（各 expand=True，随窗口拉伸自适应）。
左卡片：设备与系统信息
  - CPU 型号 / 核心数 / 内存
  - Windows 版本 + build 号
  - 是否管理员 / Python 版本
右卡片：模块概览
  - 已导入 / 可应用 / 已打补丁 / 目标缺失 统计（后台探测后刷新）
  - 「管理模块」「导入新模块」两个快捷入口（跳对应 tab）
"""
from __future__ import annotations

import ctypes
import os
import platform
import sys

import flet as ft

from .. import services


# ---------------------------------------------------------------- 信息采集

def _get_windows_info() -> dict:
    """通过 winreg 读取 Windows 版本信息。非 Windows 返回空值。"""
    info = {"product": "", "build": "", "release_id": ""}
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        try:
            info["product"] = winreg.QueryValueEx(key, "ProductName")[0]
        except OSError:
            pass
        try:
            info["build"] = winreg.QueryValueEx(key, "CurrentBuildNumber")[0]
        except OSError:
            pass
        try:
            info["release_id"] = winreg.QueryValueEx(key, "DisplayVersion")[0]
        except OSError:
            pass
        finally:
            winreg.CloseKey(key)
    except (ImportError, OSError):
        pass
    return info


def _get_memory_info() -> tuple:
    """返回 (total_gb, available_gb)，非 Windows 返回 (0, 0)。"""
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        total_gb = stat.ullTotalPhys / (1024 ** 3)
        avail_gb = stat.ullAvailPhys / (1024 ** 3)
        return total_gb, avail_gb
    except Exception:
        return 0.0, 0.0


def _get_cpu_name() -> str:
    """CPU 型号，尽力获取。"""
    p = platform.processor()
    if p:
        return p
    try:
        import subprocess
        out = subprocess.check_output(
            ["wmic", "cpu", "get", "name"],
            stderr=subprocess.DEVNULL, timeout=5,
            text=True)
        lines = [l.strip() for l in out.splitlines() if l.strip() and l.strip() != "Name"]
        if lines:
            return lines[0]
    except Exception:
        pass
    return "未知"


def _is_admin() -> bool:
    """是否以管理员身份运行。"""
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            pass
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def collect_system_info() -> list:
    """采集所有系统信息，返回 [(标签, 值), ...] 列表。"""
    win = _get_windows_info()
    cpu = _get_cpu_name()
    cores = os.cpu_count() or 0
    mem_total, mem_avail = _get_memory_info()
    admin = _is_admin()

    items = [
        ("CPU", cpu),
        ("核心数", str(cores)),
        ("内存", f"{mem_total:.1f} GB（可用 {mem_avail:.1f} GB）" if mem_total else "未知"),
    ]
    if win["product"]:
        ver_parts = []
        if win["release_id"]:
            ver_parts.append(win["release_id"])
        if win["build"]:
            ver_parts.append(f"build {win['build']}")
        ver_str = "  ".join(ver_parts)
        items.append(("Windows 版本", f"{win['product']}  {ver_str}" if ver_str
                      else win["product"]))
    else:
        items.append(("系统", f"{platform.system()} {platform.version()} {platform.release()}"))
    items.append(("运行权限", "管理员" if admin else "普通用户"))
    items.append(("Python", sys.version.split()[0]))
    return items


# ---------------------------------------------------------------- 页面

class HomePage:
    """起始页：左系统信息 / 右模块概览双卡片。模块概览支持刷新。"""

    def __init__(self, page: ft.Page, on_changed=None, on_goto=None):
        self.page = page
        self.on_changed = on_changed   # 预留
        self.on_goto = on_goto         # (index) -> 跳到对应 tab（entry 注入）
        self.infos = []
        self.stat_total = ft.Text("0", size=20, weight=ft.FontWeight.BOLD)
        self.stat_ready = ft.Text("0", size=20, weight=ft.FontWeight.BOLD,
                                  color=ft.Colors.BLUE_600)
        self.stat_patched = ft.Text("0", size=20, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREEN_600)
        self.stat_missing = ft.Text("0", size=20, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.AMBER_700)
        self.content = self._build()

    # ---- 左卡片：系统信息（静态）----
    def _build_system_card(self) -> ft.Control:
        items = collect_system_info()
        tiles = [
            ft.ListTile(
                title=ft.Text(value, size=14),
                leading=ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.GREY_400,
                                size=20),
                subtitle=ft.Text(label, size=12, color=ft.Colors.GREY_600),
            )
            for label, value in items
        ]
        return ft.Card(
            content=ft.Column(
                [ft.ListTile(
                     leading=ft.Icon(ft.Icons.MONITOR, size=26,
                                     color=ft.Colors.PRIMARY),
                     title=ft.Text("系统信息", size=18,
                                   weight=ft.FontWeight.BOLD)),
                  ft.Divider(height=8),
                  ft.Column(tiles, spacing=0, scroll=ft.ScrollMode.AUTO)],
                spacing=0),
            expand=True)

    # ---- 右卡片：模块概览（可刷新）----
    def _build_module_card(self) -> ft.Control:
        def stat_cell(text: ft.Text, label: str) -> ft.Control:
            return ft.Container(
                content=ft.Column(
                    [text, ft.Text(label, size=12, color=ft.Colors.GREY_600)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2),
                expand=True, padding=ft.Padding.symmetric(vertical=4))

        # 两个填充圆角按钮（ft.Button）并排，各 expand=True 平分卡片宽度
        manage_btn = ft.Button(
            ft.Row([ft.Icon(ft.Icons.LIST_ALT), ft.Text("  管理模块")],
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True, on_click=lambda e: self._goto(1))
        import_btn = ft.Button(
            ft.Row([ft.Icon(ft.Icons.DRIVE_FILE_MOVE), ft.Text("  导入新模块")],
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True, on_click=lambda e: self._goto(2))

        return ft.Card(
            content=ft.Column(
                [ft.ListTile(
                     leading=ft.Icon(ft.Icons.INVENTORY_2, size=26,
                                     color=ft.Colors.PRIMARY),
                     title=ft.Text("模块概览", size=18,
                                   weight=ft.FontWeight.BOLD)),
                  ft.Divider(height=8),
                  ft.Row(
                      [stat_cell(self.stat_total, "已导入"),
                       stat_cell(self.stat_ready, "可应用"),
                       stat_cell(self.stat_patched, "已打补丁"),
                       stat_cell(self.stat_missing, "目标缺失")],
                      vertical_alignment=ft.CrossAxisAlignment.CENTER),
                  ft.Divider(height=10),
                  ft.Row([manage_btn,
                          ft.Container(width=12),
                          import_btn])],
                spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True)

    def _build(self) -> ft.Control:
        # 两张卡片各 expand=True，Row 平分宽度 → 以窗口中央为界一左一右，
        # 随窗口拉伸自适应；中间只留 20px 缝隙，不画分割线。
        row = ft.Row(
            [self._build_system_card(),
             ft.Container(width=20),   # 中缝
             self._build_module_card()],
            vertical_alignment=ft.CrossAxisAlignment.START,
            expand=True)
        # 外层可滚动 Column：双卡内容过高（小窗口）时整行可滚。
        return ft.Column([row], spacing=0,
                         scroll=ft.ScrollMode.AUTO, expand=True)

    # ---- 数据刷新（切回主页时由 entry 调用）----
    def reload(self):
        self.infos = services.list_modules()
        self.stat_total.value = str(len(self.infos))
        self.page.update()
        self._probe()

    def _probe(self):
        if not self.infos:
            return

        def run():
            base = services.get_settings()["target_base_dir"] or ""
            results = services.probe_all(base, self.infos)
            ready = patched = missing = 0
            for info in self.infos:
                st = results.get(info.id)
                if not st:
                    missing += 1
                    continue
                if st.status == "ready":
                    ready += 1
                elif st.status == "patched":
                    patched += 1
                elif st.status in ("missing", "failed", "partial"):
                    missing += 1
            self.stat_ready.value = str(ready)
            self.stat_patched.value = str(patched)
            self.stat_missing.value = str(missing)
            self.page.update()

        self.page.run_thread(run)

    # ---- tab 跳转 ----
    def _goto(self, index: int):
        if self.on_goto:
            self.on_goto(index)