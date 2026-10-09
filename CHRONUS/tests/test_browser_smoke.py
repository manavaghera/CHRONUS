"""
Browser smoke test: the built website, served by the real API, in Chromium.

Catches what the unit tests can't: a page that crashes on load, a lazy-loaded
page that fails to fetch, a security header that blocks the site's own
scripts, a broken chat → sources → source viewer flow.

Runs when the website is built and Playwright is installed:

    npm --prefix FRONTEND/chronus-app run build
    pip install playwright && python -m playwright install chromium
    python -m pytest tests/test_browser_smoke.py

Skipped otherwise (CI runs it in its own job, .github/workflows/ci.yml).
CHRONUS_CHROMIUM=/path/to/chromium uses a browser that is already installed.
"""

import base64
import os
import socket
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="pip install playwright")

pytestmark = pytest.mark.browser

DOCUMENT = ("In the garden behind our house I grew mangoes, tomatoes and tulsi, and I watered them every evening.\n\n"
            "I taught fractions to the children of our village school for thirty years, mostly with mangoes.\n\n"
            "My younger brother Ravi moved to Pune in 1979 and wrote me a letter every single month.")


@pytest.fixture(scope="module")
def site(srv):
    """The API and the built website on a free local port."""
    import uvicorn

    if not any(getattr(r, "name", "") == "site" for r in srv.app.routes):
        pytest.skip("website not built (npm --prefix FRONTEND/chronus-app run build)")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    # lifespan off: this server runs inside the test session, which already holds the
    # data lock its startup would take (services/instance_lock.py)
    server = uvicorn.Server(uvicorn.Config(srv.app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "server didn't start"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def model(client, srv):
    """A small custom model to chat with (the sample setup has no Elon archive)."""
    from services import personas as ps

    pid = client.post("/personas", json={"name": "pytest Smoke", "relationship": "self", "consent": True}).json()["id"]
    r = client.post(f"/personas/{pid}/documents",
                    json={"filename": "notes.txt", "content_base64": base64.b64encode(DOCUMENT.encode()).decode()})
    assert r.status_code == 200, r.text
    for i in range(1, 9):
        client.post(f"/personas/{pid}/interview", json={"question_id": f"Q{i}", "answer": f"Interview answer {i} about teaching."})
    assert client.post(f"/personas/{pid}/build").status_code == 200
    ps.update_persona(pid, distance_threshold=0.95)  # the sample setup's hash embedder isn't semantic
    yield pid
    client.delete(f"/personas/{pid}")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(executable_path=os.getenv("CHRONUS_CHROMIUM") or None)
        except Exception as e:
            if os.getenv("CI"):
                raise
            pytest.skip(f"Chromium not available ({e.__class__.__name__}); python -m playwright install chromium")
        yield b
        b.close()


@pytest.fixture
def page(browser, site):
    """A fresh page that records crashes, blocked resources and server errors."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    pg.set_default_timeout(15000)
    pg.problems = []
    pg.on("pageerror", lambda e: pg.problems.append(f"page error: {e}"))
    pg.on("console", lambda m: pg.problems.append(f"blocked: {m.text}")
          if "Content Security Policy" in m.text else None)
    pg.on("response", lambda r: pg.problems.append(f"{r.status} {r.url}")
          if r.url.startswith(site) and r.status >= 500 else None)
    yield pg
    context.close()


def test_pages_load_without_errors(page, site, model):
    page.goto(site + "/")
    page.locator("h1").first.wait_for()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "skip-link"

    # every page is its own lazy-loaded chunk
    for route, text in [("/#/models", "pytest Smoke"), ("/#/create", "Who are you"), (f"/#/create/{model}", "Preserving"),
                        ("/#/pretrained", "Try it on history"), ("/#/voice", "Keep the voice")]:
        page.goto(site + route)
        page.get_by_text(text, exact=False).first.wait_for()
    assert page.problems == []


def test_chat_and_open_a_source(page, site, model):
    page.goto(f"{site}/#/chat/{model}")
    page.get_by_role("button", name="Quotes only").click()
    page.fill("#chat-in", "What did you grow in the garden?")
    page.keyboard.press("Enter")
    answer = page.locator(".msg--ai").nth(1)  # the first is the greeting
    answer.wait_for()
    page.wait_for_function("!document.querySelector('.caret')")
    assert "mangoes" in answer.inner_text().lower()

    page.locator(".src .linkbtn", has_text="View in context").first.click()
    viewer = page.locator(".viewer")
    viewer.wait_for()
    assert "garden" in viewer.inner_text()
    # Focus moves into the dialog (useDialog.js focuses on the next tick, so
    # wait for it: checking at once raced it and failed one CI run in five)
    page.wait_for_function("document.activeElement.closest('.viewer') !== null", timeout=3000)
    page.keyboard.press("Escape")
    viewer.wait_for(state="detached")
    assert page.problems == []


def test_theme_toggle(page, site):
    page.goto(site + "/")
    toggle = page.locator('.nav button[aria-label^="Switch to"]')
    first = "dark" if "dark" in toggle.get_attribute("aria-label") else "light"
    second = "light" if first == "dark" else "dark"
    toggle.click()
    page.wait_for_function(f"document.documentElement.dataset.theme === '{first}'")
    toggle.click()
    page.wait_for_function(f"document.documentElement.dataset.theme === '{second}'")
    page.reload()
    page.locator("h1").first.wait_for()
    assert page.evaluate("document.documentElement.dataset.theme") == second  # remembered
    assert page.problems == []
