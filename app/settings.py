"""工具设置：持久化到数据目录/settings.json。

设置项（均为"主程序"层面的决策，不写进模块配置）：
  auto_import_dir : 便捷导入目录（None 则默认=工具所在目录）。启动时把其中
                    的 .toml 自动搬进 configs/ 并加载。
  target_base_dir : 目标文件基准目录。模块 target 为相对路径时相对它解析
                    （通常填 OsEasy 安装目录）。
  backup          : 是否默认启用备份（默认 True）。
  backup_ext      : 备份后缀（默认 ".bak"）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from . import datadir

DEFAULTS = {
    "auto_import_dir": None,
    "target_base_dir": "",
    "backup": True,
    "backup_ext": ".bak",
}


class Settings:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or (datadir.ensure_data_dir() / "settings.json")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        s = cls(path)
        data = {}
        if s.path.exists():
            try:
                data = json.loads(s.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        s._data = {**DEFAULTS, **data}
        return s

    def _get(self, key: str):
        return self._data.get(key, DEFAULTS.get(key))

    # 便捷属性
    @property
    def auto_import_dir(self) -> Optional[str]:
        return self._get("auto_import_dir")

    @property
    def target_base_dir(self) -> str:
        return self._get("target_base_dir") or ""

    @property
    def backup(self) -> bool:
        return bool(self._get("backup"))

    @property
    def backup_ext(self) -> str:
        return self._get("backup_ext") or ".bak"

    def set(self, key: str, value) -> None:
        if key in DEFAULTS:
            self._data[key] = value
        else:
            self._data[key] = value  # 允许自定义键

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def as_dict(self) -> dict:
        return dict(self._data)