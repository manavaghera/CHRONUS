"""Check that this machine can run CHRONUS: python doctor.py

Replaces the old one-off debug scripts (test_full.py, test_st.py...). Each
check prints OK / WARN / FAIL with what to do about it; nothing is changed.
"""

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

failures = 0


def report(status: str, what: str, hint: str = "") -> None:
    global failures
    failures += status == "FAIL"
    print(f"[{status:4}] {what}" + (f"\n       -> {hint}" if hint else ""))


def check_import(module: str, hint: str, required: bool = True) -> bool:
    try:
        importlib.import_module(module)
        report("OK", f"import {module}")
        return True
    except Exception as e:  # ImportError, or a native crash surfaced as an error
        report("FAIL" if required else "WARN", f"import {module}: {type(e).__name__}: {e}", hint)
        return False


print(f"Python {sys.version.split()[0]} at {sys.executable}")
if sys.version_info < (3, 10):
    report("FAIL", "Python 3.10+ is required")

# pyarrow before sentence_transformers (Windows native crash otherwise)
check_import("pyarrow.dataset", "pip install -r requirements.txt")
for mod in ("chromadb", "fastapi", "uvicorn", "pydantic", "httpx", "requests", "pandas", "pdfplumber", "docx"):
    check_import(mod, "pip install -r requirements.txt")
check_import("sentence_transformers", "pip install -r requirements.txt (needed to embed questions)")
check_import("kokoro", "Optional: the Listen button's stand-in voices", required=False)

from config import config  # noqa: E402

try:
    import chromadb
    count = chromadb.PersistentClient(path=config.CHROMA_PATH).get_collection(config.COLLECTION_NAME).count()
    report("OK" if count else "WARN", f"Elon's memory collection: {count:,} memories",
           "" if count else "python 06-Testing/embed_elon.py")
except Exception as e:
    report("WARN", f"No memory collection at {config.CHROMA_PATH} ({type(e).__name__})", "python 06-Testing/embed_elon.py")

if config.LLM_PROVIDER in ("openai", "openrouter"):
    report("OK" if config.OPENAI_API_KEY else "WARN", f"LLM provider {config.LLM_PROVIDER}: API key "
           + ("set" if config.OPENAI_API_KEY else "missing"),
           "" if config.OPENAI_API_KEY else "Add OPENAI_API_KEY to CHRONUS/.env (AI voice falls back to quotes without it)")
else:
    report("OK", f"LLM provider {config.LLM_PROVIDER} (runs on this machine)")

report("OK" if os.getenv("FISH_API_KEY") else "WARN", "Fish Audio key " + ("set" if os.getenv("FISH_API_KEY") else "missing"),
       "" if os.getenv("FISH_API_KEY") else "Optional: FISH_API_KEY in .env for cloned voices")

site = ROOT.parent / "FRONTEND" / "chronus-app" / "dist" / "index.html"
report("OK" if site.exists() else "WARN", "Website build " + ("found" if site.exists() else "missing"),
       "" if site.exists() else "npm --prefix ../FRONTEND/chronus-app install && npm --prefix ../FRONTEND/chronus-app run build")

if config.HOST not in ("127.0.0.1", "localhost", "::1") and not config.ACCESS_CODE:
    report("WARN", f"Server binds {config.HOST} without CHRONUS_ACCESS_CODE", "Set CHRONUS_ACCESS_CODE in .env")

print("\nAll required checks passed." if not failures else f"\n{failures} required check(s) failed.")
sys.exit(1 if failures else 0)
