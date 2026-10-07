"""
One CHRONUS server per data folder.

Two server processes on the same ChromaDB (a second `python run_server.py`,
or uvicorn --workers 2) corrupt it: with two workers a deleted private
document was still quoted 5 times, and the database index errored ("Nothing
found on disk"). The server takes an exclusive lock on <chroma_db>.lock when
it starts and refuses to start if another process holds it. The operating
system releases the lock when the process ends, even if it crashes.
backup.py uses the same lock to refuse working on live data.
"""

from __future__ import annotations

import os
from pathlib import Path


class AlreadyRunning(RuntimeError):
    pass


def lock_path(chroma_path: str | os.PathLike) -> Path:
    path = Path(chroma_path)
    return path.with_name(path.name + ".lock")


class InstanceLock:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._handle = None

    def acquire(self) -> "InstanceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise AlreadyRunning(
                f"Another CHRONUS server is already using this data ({self.path.with_suffix('')}). "
                "Stop it first: two servers on one database corrupt it."
            ) from None
        self._handle = handle
        return self

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "InstanceLock":
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()
