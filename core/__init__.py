"""WinPatchKit 内核。"""
from .spec import ModuleSpec, PatchSpec, Where, Write
from .applier import run, load_target, ApplyReport, PatchResult, PatchError

__all__ = [
    "ModuleSpec", "PatchSpec", "Where", "Write",
    "run", "load_target", "ApplyReport", "PatchResult", "PatchError",
]