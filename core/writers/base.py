"""写入策略基类。

每个写入器只需：
1. 继承 Writer，设置 type 常量
2. 实现 encode(ctx) -> bytes（返回要写入定位点处的字节串）
3. 文件顶部 @register

契约：encode 只负责"算出要写的字节"，不决定写到哪（那是定位器的事），
也不直接写文件（那是 applier 的事）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..context import Context


class WriterError(Exception):
    """写入策略配置错误的通用异常。"""


class Writer(ABC):
    type: str = ""

    @abstractmethod
    def encode(self, ctx: Context) -> bytes:
        """返回要写入的字节串。"""
        raise NotImplementedError