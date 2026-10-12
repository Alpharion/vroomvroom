"""LLM client for Tencent Cloud ADP (Agent Development Platform).

Agents call ``chat()`` to get an ``LLMResult``; the client handles SSE
streaming, caching, retries, and mock mode.  ``parse_model_reply()`` strips
Markdown fences before validating JSON against a Pydantic model.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

# Load .env from the repo root (parents[2] = repo root from backend/agents/)
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

logger = logging.getLogger("vroomvroom.llm")

_ADP_CHAT_URL = os.environ.get(
    "ADP_CHAT_URL", "https://wss.lke.tencentcloud.com/adp/v2/chat",
)
_VISITOR_ID = "vroomvroom-backend"
_TIMEOUT = 90.0
_CACHE_DIR = Path(__file__).resolve().parents[1] / ".llm_cache"

# Per-agent env-var suffix mapping (uppercase, matches .env conventions).
_AGENT_ENV_SUFFIXES = {
    "rider_advocate": "RIDER_ADVOCATE",
    "driver_advocate": "DRIVER_ADVOCATE",
    "judge": "JUDGE",
}


class LLMError(Exception):
    """Raised when the LLM call fails or the response is unusable."""


@dataclass
class LLMResult:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached: bool


# ---------- AppKey resolution ----------


def _get_appkey(agent: str) -> str:
    """Resolve the AppKey for *agent*.

    Checks ``ADP_APPKEY_<AGENT>`` first, then falls back to
    ``ADP_APP_KEY``.  Raises ``LLMError`` if neither is set.
    """
    suffix = _AGENT_ENV_SUFFIXES.get(agent)
    if suffix:
        per_agent_key = os.environ.get(f"ADP_APPKEY_{suffix}")
        if per_agent_key:
            return per_agent_key
    fallback_key = os.environ.get("ADP_APP_KEY")
    if fallback_key:
        return fallback_key
    var_name = f"ADP_APPKEY_{suffix}" if suffix else "ADP_APP_KEY"
    raise LLMError(
        f"No AppKey configured. Set {var_name} or ADP_APP_KEY in .env."
    )


# ---------- Cache ----------


def _cache_key(agent: str, system_prompt: str, user_message: str) -> str:
    """SHA-256 hash of agent + system_prompt + user_message."""
    raw = agent + "\x00" + system_prompt + "\x00" + user_message
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_path(key: str, cache_dir: Path | None = None) -> Path:
    d = cache_dir or _CACHE_DIR
    return d / f"{key}.json"


def _cache_read(key: str, cache_dir: Path | None = None) -> LLMResult | None:
    path = _cache_path(key, cache_dir)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return LLMResult(
        text=data["text"],
        input_tokens=data.get("input_tokens"),
        output_tokens=data.get("output_tokens"),
        total_tokens=data.get("total_tokens"),
        cached=True,
    )


def _cache_write(key: str, result: LLMResult, cache_dir: Path | None = None) -> None:
    path = _cache_path(key, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Always write with cached=False so the cached file reflects the
    # original live result, not the cached flag.
    data = asdict(result)
    data["cached"] = False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- SSE parser ----------


def _parse_sse_stream(lines: list[str]) -> tuple[str, dict[str, Any] | None]:
    """Parse SSE lines and return (reply_text, stat_info).

    Walks the SSE event/data pairs, tracking text deltas/replacements and
    extracting the final text from ``response.completed``.

    Returns ``(text, stat_info)`` where *stat_info* is the ``StatInfo``
    dict from ``response.completed`` (or ``None`` if absent).

    Raises ``LLMError`` if an ``error`` event is encountered or the stream
    ends without ``response.completed``.
    """
    accumulated_text = ""
    completed_text: str | None = None
    stat_info: dict[str, Any] | None = None
    saw_completed = False

    for line in lines:
        if not line.startswith("data: "):
            continue
        data_str = line[6:]
        if data_str == "[DONE]":
            continue
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        evt_type = data.get("Type", "")

        if evt_type == "error":
            err = data.get("Error", {})
            raise LLMError(err.get("Message", "Unknown ADP error"))

        if evt_type == "text.delta":
            accumulated_text += data.get("Text", "")
        elif evt_type == "text.replace":
            # text.replace replaces the full accumulated text so far
            accumulated_text = data.get("Text", "")
        elif evt_type == "response.completed":
            saw_completed = True
            resp = data.get("Response", {})
            stat_info = resp.get("StatInfo")
            messages = resp.get("Messages", [])
            for msg in messages:
                if msg.get("Type") == "reply":
                    for content in msg.get("Contents", []):
                        if content.get("Type") == "text":
                            completed_text = content.get("Text", "")

    if not saw_completed:
        raise LLMError("Stream ended without response.completed event.")

    # Prefer the text from response.completed; fall back to accumulated.
    if completed_text is not None:
        return completed_text, stat_info
    return accumulated_text, stat_info


# ---------- HTTP call ----------


async def _call_adp(
    agent: str,
    system_prompt: str,
    user_message: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LLMResult:
    """Make a live ADP call and return an ``LLMResult``."""
    appkey = _get_appkey(agent)
    body = {
        "RequestId": uuid.uuid4().hex,
        "ConversationId": uuid.uuid4().hex,
        "AppKey": appkey,
        "Contents": [{"Type": "text", "Text": user_message}],
        "VisitorId": _VISITOR_ID,
        "SystemRole": system_prompt,
        "Stream": "enable",
    }

    async def _do_request(client: httpx.AsyncClient) -> list[str]:
        lines: list[str] = []
        async with client.stream("POST", _ADP_CHAT_URL, json=body) as resp:
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp,
                )
            if resp.status_code != 200:
                raise LLMError(f"ADP returned HTTP {resp.status_code}")
            async for line in resp.aiter_lines():
                lines.append(line)
        return lines

    # Retry once on network error or 5xx.
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, transport=transport,
    ) as client:
        try:
            lines = await _do_request(client)
        except (httpx.HTTPStatusError, httpx.HTTPError) as exc:
            logger.info("Retrying %s after error: %s", agent, exc)
            lines = await _do_request(client)

    text, stat_info = _parse_sse_stream(lines)
    return LLMResult(
        text=text,
        input_tokens=stat_info.get("InputTokens") if stat_info else None,
        output_tokens=stat_info.get("OutputTokens") if stat_info else None,
        total_tokens=stat_info.get("TotalTokens") if stat_info else None,
        cached=False,
    )


# ---------- Public API ----------


async def chat(
    agent: str,
    system_prompt: str,
    user_message: str,
    *,
    cache_dir: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LLMResult:
    """Call the LLM for *agent* and return an ``LLMResult``.

    *agent* is one of "rider_advocate", "driver_advocate", "judge".

    If ``USE_MOCK_LLM=true`` in the environment, reads from the cache only
    and never calls ADP.  Otherwise calls ADP live and writes the result
    to the cache.
    """
    use_mock = os.environ.get("USE_MOCK_LLM", "").lower() == "true"
    key = _cache_key(agent, system_prompt, user_message)

    if use_mock:
        result = _cache_read(key, cache_dir)
        if result is None:
            raise LLMError(
                f"No cached response for {agent}; run once with USE_MOCK_LLM=false."
            )
        logger.info(
            "%s cached tokens=%s (mock mode)",
            agent,
            result.total_tokens,
        )
        return result

    start = time.monotonic()
    result = await _call_adp(agent, system_prompt, user_message, transport=transport)
    elapsed = time.monotonic() - start

    _cache_write(key, result, cache_dir)

    logger.info(
        "%s live tokens=%s time=%.1fs",
        agent,
        result.total_tokens,
        elapsed,
    )
    return result


# ---------- JSON helper ----------


def parse_model_reply(text: str, model: type[BaseModel]) -> BaseModel:
    """Strip Markdown fences and parse *text* as *model*.

    Removes ```` ```json ... ``` ```` fences, trims any text before the
    first ``{`` or after the last ``}``, then validates with
    ``model.model_validate_json``.

    Raises ``LLMError`` with the validation error and the first 500 chars
    of the reply on failure.
    """
    stripped = text.strip()

    # Remove Markdown code fences.
    if stripped.startswith("```"):
        # Drop the opening fence line (```json or ```).
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        # Drop the closing fence.
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]

    # Trim to the outermost JSON object.
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        stripped = stripped[first_brace:last_brace + 1]

    try:
        return model.model_validate_json(stripped)
    except ValidationError as exc:
        raise LLMError(
            f"Failed to parse model reply: {exc}\n"
            f"Reply (first 500 chars): {text[:500]}"
        ) from exc
