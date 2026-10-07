"""
Private data stays private on a shared machine.

Custom models (family documents, voice samples), the memory database, the
Q&A, feedback and audit logs and .env must be readable only by the account
running the server; they used to be created readable by every account. The
server sets a 077 umask, so everything it creates is owner-only, and
tightens what already exists when it starts.

POSIX only: on Windows these files sit in the user's profile, whose access
control already keeps other accounts out (chmod there only toggles
read-only).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Iterable

PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700


def restrict_new_files() -> None:
    """Files and folders this process creates from now on are owner-only."""
    if os.name == "posix":
        os.umask(0o077)


def tighten(paths: Iterable[Path]) -> int:
    """Make existing files and folders under *paths* owner-only; returns how many changed."""
    if os.name != "posix":
        return 0
    changed = 0
    for root in map(Path, paths):
        if not root.exists():
            continue
        for item in [root, *(root.rglob("*") if root.is_dir() else [])]:
            if item.is_symlink():
                continue
            if stat.S_IMODE(item.stat().st_mode) & 0o077:
                item.chmod(PRIVATE_DIR_MODE if item.is_dir() else PRIVATE_FILE_MODE)
                changed += 1
    return changed
