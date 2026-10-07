"""
Back up and restore CHRONUS data: the memory database (chroma_db/), custom
models (personas/: family documents, voice samples) and the Q&A, feedback
and audit logs. Nothing else here can be rebuilt if it's lost.

    python backup.py create              -> backups/chronus-<date>.zip
    python backup.py list
    python backup.py restore backups/chronus-<date>.zip

Stop the server first: the database must not change while it's copied, and
both commands refuse while a server holds the data lock
(services/instance_lock.py). Restore never deletes: the current data is
moved to backups/before-restore-<date>/ first. .env (your keys) is not
included; keep it somewhere safe yourself. Backups hold private data and are
created readable only by you.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import config  # noqa: E402
from services import instance_lock, private_files  # noqa: E402

BACKUP_DIR = ROOT / "backups"


def data_paths() -> dict[str, Path]:
    """Name inside the backup -> where it lives."""
    return {
        "chroma_db": Path(config.CHROMA_PATH),
        "personas": ROOT / "personas",
        "qa_log.jsonl": ROOT / "qa_log.jsonl",
        "feedback.jsonl": ROOT / "feedback.jsonl",
        "audit_log.jsonl": ROOT / "audit_log.jsonl",
    }


def _lock(paths: dict[str, Path]) -> instance_lock.InstanceLock:
    return instance_lock.InstanceLock(instance_lock.lock_path(paths["chroma_db"]))


def create(out_dir: Path = BACKUP_DIR, paths: dict[str, Path] | None = None) -> Path:
    paths = paths or data_paths()
    private_files.restrict_new_files()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"chronus-{datetime.now():%Y%m%d-%H%M%S}.zip"
    with _lock(paths):  # refuses while a server is running on this data
        contents = []
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, path in paths.items():
                if not path.exists():
                    continue
                files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
                for file in files:
                    if file.name.endswith(".lock"):
                        continue
                    arcname = name if file == path else f"{name}/{file.relative_to(path).as_posix()}"
                    zf.write(file, arcname)
                contents.append(name)
            zf.writestr("manifest.json", json.dumps({"created_at": datetime.now().isoformat(timespec="seconds"),
                                                     "contents": contents}, indent=2))
    private_files.tighten([target])
    return target


def _safe_members(zf: zipfile.ZipFile, names: set[str]) -> list[zipfile.ZipInfo]:
    """Every member, refusing paths that would land outside the data folders."""
    members = []
    for info in zf.infolist():
        name = info.filename
        if name == "manifest.json":
            continue
        top = name.split("/", 1)[0]
        if name.startswith(("/", "\\")) or ".." in Path(name).parts or ":" in name or top not in names:
            raise ValueError(f"Unsafe or unknown path in backup: {name!r}")
        members.append(info)
    return members


def restore(archive: Path, paths: dict[str, Path] | None = None, aside_dir: Path = BACKUP_DIR) -> Path:
    """Restore *archive*; returns the folder where the replaced data was kept."""
    paths = paths or data_paths()
    with zipfile.ZipFile(archive) as zf:
        if "manifest.json" not in zf.namelist():
            raise ValueError(f"{archive} is not a CHRONUS backup (no manifest.json)")
        members = _safe_members(zf, set(paths))
        with _lock(paths):
            aside = aside_dir / f"before-restore-{datetime.now():%Y%m%d-%H%M%S}"
            aside.mkdir(parents=True)
            for name, path in paths.items():
                if path.exists():
                    shutil.move(str(path), str(aside / name))
            for info in members:
                name, _, rest = info.filename.partition("/")
                dest = paths[name] / rest if rest else paths[name]
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
    private_files.tighten([p for p in paths.values() if p.exists()])
    return aside


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up or restore CHRONUS data")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create")
    sub.add_parser("list")
    restore_cmd = sub.add_parser("restore")
    restore_cmd.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "create":
            target = create()
            print(f"Backup written to {target} ({target.stat().st_size / 1e6:.1f} MB). .env is not included.")
        elif args.command == "list":
            for zip_path in sorted(BACKUP_DIR.glob("chronus-*.zip")):
                print(f"{zip_path.name}  {zip_path.stat().st_size / 1e6:.1f} MB")
        else:
            aside = restore(args.archive)
            print(f"Restored {args.archive}. The data it replaced is kept in {aside}.")
    except instance_lock.AlreadyRunning as e:
        sys.exit(f"{e}")
    except (ValueError, zipfile.BadZipFile, FileNotFoundError) as e:
        sys.exit(f"Can't {args.command}: {e}")


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
