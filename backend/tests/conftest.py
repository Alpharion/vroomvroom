"""Shared pytest setup.

- Puts backend/ on sys.path, so `pytest` works from the repo root as well
  as from backend/ (imports like `from schemas import ...`).
- Gives every test an empty, in-memory review queue, so API tests never
  write to backend/.review_queue.json.
- Ignores the mode flags in the developer's .env: tests run the real agent
  flow (USE_STUB_AGENTS unset) and can never call ADP (USE_MOCK_LLM=true).
"""

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.fixture(autouse=True)
def _env_flags(monkeypatch):
    import agents.llm  # noqa: F401  (loads .env first, so the overrides below win)

    monkeypatch.delenv("USE_STUB_AGENTS", raising=False)
    monkeypatch.setenv("USE_MOCK_LLM", "true")


@pytest.fixture(autouse=True)
def review_queue(monkeypatch):
    import app.main
    from app.review_queue import ReviewQueue

    queue = ReviewQueue(store_path=None)
    monkeypatch.setattr(app.main, "review_queue", queue)
    return queue
