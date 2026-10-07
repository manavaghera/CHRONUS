"""One server per data folder (services/instance_lock.py) and backup.py."""

import json
import subprocess
import sys
import zipfile

import pytest

import backup
from services import instance_lock


def test_a_second_server_refuses_to_start(tmp_path):
    path = instance_lock.lock_path(tmp_path / "chroma_db")
    with instance_lock.InstanceLock(path):
        # a real second process, as with `uvicorn --workers 2` or two run_server.py
        code = ("import sys; from services import instance_lock as l\n"
                f"try:\n    l.InstanceLock(l.Path({str(path)!r})).acquire()\nexcept l.AlreadyRunning:\n    sys.exit(3)")
        assert subprocess.run([sys.executable, "-c", code], cwd=backup.ROOT, timeout=120).returncode == 3
    # released when the first one stops
    instance_lock.InstanceLock(path).acquire().release()


@pytest.fixture
def data(tmp_path):
    paths = {"chroma_db": tmp_path / "data" / "chroma_db", "personas": tmp_path / "data" / "personas",
             "qa_log.jsonl": tmp_path / "data" / "qa_log.jsonl", "feedback.jsonl": tmp_path / "data" / "feedback.jsonl",
             "audit_log.jsonl": tmp_path / "data" / "audit_log.jsonl"}
    (paths["chroma_db"] / "seg").mkdir(parents=True)
    (paths["chroma_db"] / "chroma.sqlite3").write_bytes(b"db v1")
    (paths["chroma_db"] / "seg" / "index.bin").write_bytes(b"\x00\x01")
    (paths["personas"] / "amma" / "uploads").mkdir(parents=True)
    (paths["personas"] / "amma" / "uploads" / "letter.txt").write_text("Dear Ravi", encoding="utf-8")
    paths["qa_log.jsonl"].write_text('{"id": "a"}\n', encoding="utf-8")
    return paths


def test_backup_and_restore_round_trip(tmp_path, data):
    archive = backup.create(tmp_path / "backups", data)
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert {"chroma_db/chroma.sqlite3", "chroma_db/seg/index.bin", "personas/amma/uploads/letter.txt",
                "qa_log.jsonl", "manifest.json"} <= names
        assert not any(".env" in n for n in names)
        assert json.loads(zf.read("manifest.json"))["contents"] == ["chroma_db", "personas", "qa_log.jsonl"]
    # later changes...
    (data["chroma_db"] / "chroma.sqlite3").write_bytes(b"db v2 (broken)")
    (data["personas"] / "amma" / "uploads" / "letter.txt").unlink()
    aside = backup.restore(archive, data, tmp_path / "backups")
    assert (data["chroma_db"] / "chroma.sqlite3").read_bytes() == b"db v1"
    assert (data["personas"] / "amma" / "uploads" / "letter.txt").read_text(encoding="utf-8") == "Dear Ravi"
    assert (aside / "chroma_db" / "chroma.sqlite3").read_bytes() == b"db v2 (broken)"  # nothing deleted


def test_restore_refuses_unsafe_archives(tmp_path, data):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("manifest.json", "{}")
        zf.writestr("personas/../../outside.txt", "x")
    with pytest.raises(ValueError, match="Unsafe"):
        backup.restore(evil, data, tmp_path / "backups")
    assert not (tmp_path / "outside.txt").exists() and (data["chroma_db"] / "chroma.sqlite3").exists()


def test_nothing_runs_while_a_server_holds_the_data(tmp_path, data):
    with instance_lock.InstanceLock(instance_lock.lock_path(data["chroma_db"])):
        with pytest.raises(instance_lock.AlreadyRunning):
            backup.create(tmp_path / "backups", data)
