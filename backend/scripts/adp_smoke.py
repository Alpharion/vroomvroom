"""ADP smoke test -- makes one real call to verify the API works.

Usage:  python3 backend/scripts/adp_smoke.py

Requires ADP_APP_KEY in .env (or ADP_APPKEY_JUDGE etc.).
Saves the raw SSE response body to backend/scripts/adp_raw_response.txt
(never prints or saves the AppKey).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env from repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

_CHAT_URL = os.environ.get(
    "ADP_CHAT_URL", "https://wss.lke.tencentcloud.com/adp/v2/chat",
)
_RAW_OUTPUT = Path(__file__).parent / "adp_raw_response.txt"


def _get_appkey() -> str:
    key = (
        os.environ.get("ADP_APPKEY_JUDGE")
        or os.environ.get("ADP_APPKEY_DRIVER_ADVOCATE")
        or os.environ.get("ADP_APPKEY_RIDER_ADVOCATE")
        or os.environ.get("ADP_APP_KEY")
    )
    if not key:
        print("ERROR: Set ADP_APP_KEY (or ADP_APPKEY_JUDGE) in .env", file=sys.stderr)
        sys.exit(1)
    return key


def main() -> None:
    import uuid

    appkey = _get_appkey()
    body = {
        "RequestId": uuid.uuid4().hex,
        "ConversationId": uuid.uuid4().hex,
        "AppKey": appkey,
        "Contents": [{"Type": "text", "Text": "ping"}],
        "VisitorId": "vroomvroom-backend",
        "SystemRole": "Reply with exactly the word PONG and nothing else.",
        "Stream": "enable",
    }

    print(f"POST {_CHAT_URL}")
    print("System prompt: Reply with exactly the word PONG and nothing else.")
    print("User message: ping")
    print("Waiting for response...")

    raw_chunks: list[str] = []
    reply_text = ""

    with httpx.Client(timeout=90.0) as client:
        with client.stream("POST", _CHAT_URL, json=body) as resp:
            if resp.status_code != 200:
                print(f"ERROR: HTTP {resp.status_code}", file=sys.stderr)
                sys.exit(1)
            for line in resp.iter_lines():
                raw_chunks.append(line)
                # Parse SSE: lines like "event: ..." and "data: ..."
                if line.startswith("data: "):
                    data_str = line[6:]
                    raw_chunks.append("")  # blank line marker
                    if data_str == "[DONE]":
                        continue
                    import json
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    evt_type = data.get("Type", "")
                    if evt_type == "text.delta":
                        reply_text += data.get("Text", "")
                    elif evt_type == "response.completed":
                        msgs = data.get("Response", {}).get("Messages", [])
                        for msg in msgs:
                            if msg.get("Type") == "reply":
                                for content in msg.get("Contents", []):
                                    reply_text = content.get("Text", "")
                    elif evt_type == "error":
                        err = data.get("Error", {})
                        print(
                            f"ERROR from ADP: {err.get('Message', 'unknown')}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

    raw_body = "\n".join(raw_chunks)
    _RAW_OUTPUT.write_text(raw_body, encoding="utf-8")
    print(f"Raw response saved to {_RAW_OUTPUT} ({len(raw_body)} bytes)")
    print(f"Reply text: {reply_text!r}")
    if reply_text.strip().upper() == "PONG":
        print("SUCCESS: SystemRole was respected (reply is PONG).")
    else:
        print("WARNING: Reply is not PONG -- check if SystemRole is supported.")


if __name__ == "__main__":
    main()
