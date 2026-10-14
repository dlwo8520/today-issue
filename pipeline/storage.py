from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Edition


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, path)
        except PermissionError:
            if os.name != "nt" or not path.exists():
                raise
            # Windows ReplaceFile preserves the destination ACL while replacing
            # its contents atomically; MoveFileEx can fail on inherited ACLs.
            import ctypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            replace = kernel.ReplaceFileW
            replace.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
            replace.restype = ctypes.c_int
            if not replace(str(path.resolve()), str(Path(temporary).resolve()), None, 2, None, None):
                raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_edition(path: Path, edition: Edition) -> None:
    # Validate again immediately before publishing, including model_copy callers.
    checked = Edition.model_validate(edition.model_dump(mode="json"))
    atomic_json(path, checked.model_dump(mode="json"))


@contextmanager
def pipeline_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)
