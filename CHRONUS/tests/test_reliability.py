"""A slow or failing AI provider (services/natural_mode.py): a whole-answer
deadline, a circuit breaker that switches to quotes, streams that stop when
the person leaves, and roundtable seats that answer at the same time."""

import time
from contextlib import contextmanager
from unittest import mock

import requests

from services import natural_mode as nm
from services import personas as ps
from services.roundtable import _in_parallel

MEMS = [(0.0, "Mars is the next logical step for civilization.", {"source_type": "tweet", "source_file": "x"}, 0.3)]


def _cloud(monkeypatch, deadline=25.0):
    monkeypatch.setattr(nm.config, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(nm.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(nm.config, "LLM_DEADLINE_SECONDS", deadline)


def _slow_stream(lines, delay, consumed):
    @contextmanager
    def post(*args, **kwargs):
        response = mock.Mock()

        def iter_lines(decode_unicode=True):
            for line in lines:
                time.sleep(delay)
                consumed.append(line)
                yield line
        response.iter_lines = iter_lines
        yield response
    return post


def test_a_slow_stream_is_cut_off_at_the_deadline(monkeypatch):
    _cloud(monkeypatch, deadline=0.2)
    token = 'data: {"choices": [{"delta": {"content": "Mars "}}]}'
    consumed = []
    monkeypatch.setattr(nm.requests, "post", _slow_stream([token] * 50, 0.02, consumed))
    started = time.monotonic()
    out = nm.generate_natural_response("Why Mars?", MEMS, {}, on_token=lambda t: None)
    assert time.monotonic() - started < 2 and len(consumed) < 50  # it used to wait up to 60 s
    assert out["mode"] == "mix_method_fallback" and "slow or unavailable" in out["notice"]


def test_requests_use_the_deadline_as_timeout(monkeypatch, fake_llm):
    with fake_llm(content="Mars is the next logical step for civilization.") as post:
        nm.config.LLM_DEADLINE_SECONDS, old = 7.0, nm.config.LLM_DEADLINE_SECONDS
        try:
            nm.generate_natural_response("Why Mars?", MEMS, {})
        finally:
            nm.config.LLM_DEADLINE_SECONDS = old
    assert post.call_args.kwargs["timeout"] == (5.0, 7.0)


def test_breaker_skips_a_failing_provider_then_retries(monkeypatch):
    _cloud(monkeypatch)
    down = mock.Mock(side_effect=requests.ConnectionError("down"))
    monkeypatch.setattr(nm.requests, "post", down)
    for _ in range(3):
        assert nm.generate_natural_response("Why Mars?", MEMS, {})["mode"] == "mix_method_fallback"
    assert down.call_count == 3
    out = nm.generate_natural_response("Why Mars?", MEMS, {})
    assert down.call_count == 3 and "slow or unavailable" in out["notice"]  # no call while open: answered at once
    nm.breaker.open_until = 0  # a minute later
    nm.generate_natural_response("Why Mars?", MEMS, {})
    assert down.call_count == 4


def test_generation_stops_when_the_person_leaves(monkeypatch):
    _cloud(monkeypatch)
    token = 'data: {"choices": [{"delta": {"content": "Mars "}}]}'
    consumed = []
    monkeypatch.setattr(nm.requests, "post", _slow_stream([token] * 50, 0, consumed))
    seen = []

    def on_token(text):
        seen.append(text)
        if len(seen) == 3:
            raise nm.StreamCancelled()
    nm.generate_natural_response("Why Mars?", MEMS, {}, on_token=on_token)
    assert len(consumed) == 3  # the provider stream was closed, not read to the end
    assert nm.breaker.failures == 0  # leaving isn't a provider failure


def test_roundtable_seats_answer_at_the_same_time():
    token = ps.current_user.set("asha")
    try:
        def seat():
            time.sleep(0.3)
            return {"user": ps.current_user.get()}
        started = time.monotonic()
        results = _in_parallel([seat] * 4)
        elapsed = time.monotonic() - started
    finally:
        ps.current_user.reset(token)
    assert elapsed < 0.9 and results == [{"user": "asha"}] * 4  # in order, with the caller's account
