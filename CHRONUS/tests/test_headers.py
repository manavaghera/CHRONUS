"""Browser security headers (services/security_headers.py)."""

import pytest

from services import security_headers


def _csp(response) -> dict[str, str]:
    return dict(part.strip().split(" ", 1) for part in response.headers["content-security-policy"].split(";"))


@pytest.mark.parametrize("method,path", [("get", "/health"), ("get", "/personas"), ("get", "/"),
                                         ("post", "/personas/elon_musk/build")])  # a refusal (403) too
def test_every_response_has_the_headers(client, method, path):
    headers = {"origin": "https://evil.example"} if method == "post" else {}
    r = getattr(client, method)(path, headers=headers)
    for name, value in security_headers.HEADERS.items():
        assert r.headers[name] == value
    csp = _csp(r)
    assert csp["script-src"] == "'self'" and csp["frame-ancestors"] == "'none'" and csp["object-src"] == "'none'"
    assert "unsafe-inline" not in r.headers["content-security-policy"]
    assert "strict-transport-security" not in r.headers  # plain HTTP


def test_unknown_hosts_are_refused_with_headers(srv):
    from fastapi.testclient import TestClient

    r = TestClient(srv.app, base_url="http://attacker.example").get("/health")
    assert r.status_code == 400 and r.headers["x-content-type-options"] == "nosniff"


def test_streamed_answers_and_api_docs(client):
    with client.stream("POST", "/chat/stream", json={"query": "Why Mars?"}) as r:
        assert r.headers["x-frame-options"] == "DENY"
        assert any(line.startswith("data:") for line in r.iter_lines())
    docs = client.get("/docs")
    assert "https://cdn.jsdelivr.net" in _csp(docs)["script-src"]  # Swagger UI still loads


def test_hsts_only_over_https(srv):
    from fastapi.testclient import TestClient

    r = TestClient(srv.app, base_url="https://localhost").get("/health")
    assert r.headers["strict-transport-security"] == "max-age=31536000"
