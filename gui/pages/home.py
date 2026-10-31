"""起始页（主页）：纯展示设备与系统信息，不提供交互操作。

展示内容：
  - CPU 型号 / 核心数
  - 内存总量 / 可用
  - Windows 版本（如 Windows 10 专业版）
  - Windows 小版本号（build xxxx）
  - 是否以管理员身份运行
"""
from __future__ import annotations

import ctypes
import os
import platform
import sys

import flet as ft


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
    """起始页：纯展示，无交互。"""

    def __init__(self, page: ft.Page, on_changed=None):
        self.page = page
        self.content = self._build()

    def _build(self) -> ft.Control:
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

        card = ft.Card(
            content=ft.Column(
                [ft.ListTile(
                     leading=ft.Icon(ft.Icons.DESKTOP_WINDOWS, size=26,
                                     color=ft.Colors.PRIMARY),
                     title=ft.Text("系统信息", size=18,
                                   weight=ft.FontWeight.BOLD)),
                 ft.Divider(height=8),
                 ft.Column(tiles, spacing=0)],
                spacing=0),
            width=480)

        return ft.Column(
            [ft.Container(card, alignment=ft.Alignment.CENTER,
                          margin=ft.Margin.symmetric(horizontal=16, vertical=20)),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO, expand=True)