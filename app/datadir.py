"""WinPatchKit 应用层。

本包是"主程序"逻辑：数据目录、工具设置、模块配置导入/加载。
它依赖 core（OS 无关的 patch 引擎），core 不反向依赖本包。

数据目录（持久化）：
  Windows : %APPDATA%/WinPatchKit
  其它    : ~/.config/WinPatchKit  或  XDG_CONFIG_HOME/WinPatchKit
子目录：
  settings.json   工具设置
  configs/        导入的模块配置（.toml）
  backups/        备份的原始文件
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "WinPatchKit"


def appdata_dir() -> Path:
    """返回数据目录（不创建），跨平台。"""
    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / APP_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_NAME


def ensure_data_dir() -> Path:
    """确保数据目录及子目录存在，返回数据目录 Path。"""
    root = appdata_dir()
    (root / "configs").mkdir(parents=True, exist_ok=True)
    (root / "backups").mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


def configs_dir() -> Path:
    """模块配置目录（数据目录/configs），自动创建。"""
    d = ensure_data_dir() / "configs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backups_dir() -> Path:
    """备份目录（数据目录/backups），自动创建。"""
    d = ensure_data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def trash_dir() -> Path:
    """回收站目录（数据目录/trash），软删除的配置暂存于此，自动创建。"""
    d = ensure_data_dir() / "trash"
    d.mkdir(parents=True, exist_ok=True)
    return d