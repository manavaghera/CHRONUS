"""Start the CHRONUS server: API + website on http://127.0.0.1:8001.

Works from any directory. Host and port come from config.py (override with
CHRONUS_HOST / CHRONUS_PORT in .env). It binds loopback by default: binding
0.0.0.0 exposes the server to your whole network, so only do that with
CHRONUS_ACCESS_CODE set.

    python run_server.py            # or: python api_server.py
    python run_server.py --reload   # restart on code changes (development)
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from config import config  # noqa: E402

if __name__ == "__main__":
    if config.HOST not in ("127.0.0.1", "localhost", "::1") and not config.ACCESS_CODE:
        print(f"WARNING: binding {config.HOST} with no CHRONUS_ACCESS_CODE: anyone on the network can use this server.")
    print(f"CHRONUS on http://{config.HOST}:{config.PORT}")
    uvicorn.run("api_server:app", host=config.HOST, port=config.PORT, reload="--reload" in sys.argv)
