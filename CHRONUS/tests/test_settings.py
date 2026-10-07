"""Settings are checked at startup (config.validate), secrets are never printed,
and /ready says when the server can actually answer."""

import os
import subprocess
import sys

import config as config_module
from config import ChronusConfig, describe, validate


def test_typos_are_errors_not_silent_fallbacks(monkeypatch):
    monkeypatch.setenv("CHRONUS_RETRIEVAL_MODE", "hybird")
    monkeypatch.setenv("CHRONUS_LLM_PROVIDER", "openroute")
    errors, _ = validate(ChronusConfig())
    assert any("hybird" in e for e in errors) and any("openroute" in e for e in errors)


def test_provider_names_ignore_case(monkeypatch):
    # "OpenRouter" used to send every request to Ollama
    monkeypatch.setenv("CHRONUS_LLM_PROVIDER", " OpenRouter ")
    monkeypatch.setenv("CHRONUS_RETRIEVAL_MODE", "Hybrid")
    cfg = ChronusConfig()
    assert (cfg.LLM_PROVIDER, cfg.RETRIEVAL_MODE) == ("openrouter", "hybrid") and not validate(cfg)[0]


def test_secrets_are_never_printed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-or-v1-not-a-real-key")
    monkeypatch.setenv("CHRONUS_ACCESS_CODE", "4821")
    monkeypatch.setenv("CHRONUS_USERS", "asha:mango-tree")
    text = "\n".join(describe(ChronusConfig()))
    assert "sk-or-v1" not in text and "4821" not in text and "mango-tree" not in text
    assert "OPENAI_API_KEY: set (hidden)" in text


def test_server_refuses_to_start_with_bad_settings():
    env = {**os.environ, "CHRONUS_RETRIEVAL_MODE": "hybird", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, "-c", "import api_server"], cwd=config_module.Path(config_module.__file__).parent,
                            env=env, capture_output=True, text=True, timeout=300)
    assert result.returncode != 0 and "hybird" in result.stderr


def test_ready_reports_what_is_missing(srv, client, monkeypatch):
    class NotLoaded:
        loaded = False

    monkeypatch.setattr(srv, "embedder", NotLoaded())
    r = client.get("/ready")
    assert r.status_code == 503 and r.json()["checks"]["embedding_model"] is False
    monkeypatch.undo()
    srv.embedder.encode(["warm up"])
    r = client.get("/ready")
    checks = r.json()["checks"]
    assert checks["embedding_model"] is True and checks["settings"] is True
    assert r.status_code == (200 if checks["memories"] else 503)
