"""Moved to services/post_process.py; kept so older scripts here still import it."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.post_process import *  # noqa: F401,F403,E402
from services.post_process import scrub  # noqa: F401,E402
