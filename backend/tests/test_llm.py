"""Tests for the ADP LLM client (no real network calls)."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from agents.llm import LLMError, LLMResult, chat, parse_model_reply
from schemas import Ruling

# ---- Test SSE body (based on the real ADP response) ----

_MOCK_SSE_BODY = (
    'event: request_ack\n'
    'data: {"Type":"request_ack","RequestAck":{"Role":"user","RecordId":"fake_record_001","ConversationId":"fake_conv_001","Status":"success","StatusDesc":"Request Succeeded","Messages":[{"Type":"question","MessageId":"rpl_fake_q_001","Name":"question","Title":"User Question","Icon":"","Status":"success","StatusDesc":"","Contents":[{"Type":"text","Text":"ping"}],"ExtraInfo":{"Elapsed":"0","StartTime":"1791641301000","EndTime":"0"},"RecordId":""}],"ExtraInfo":{"RequestId":"fake_req_001","TraceId":"fake_trace_001","Elapsed":"0","StartTime":"1791641301000","IsFromSelf":true,"IsLlmGenerated":false,"CanRating":false,"CanFeedback":false,"ReplyMethod":0,"FromName":"","FromAvatar":"","HasRead":false,"EndTime":"0"}},"Timestamp":"1791641302094","RecordId":""}\n'
    '\n'
    'event: response.created\n'
    'data: {"Type":"response.created","Response":{"Role":"assistant","RecordId":"fake_record_002","RelatedRecordId":"fake_record_001","ConversationId":"fake_conv_001","Status":"processing","StatusDesc":"","ExtraInfo":{"RequestId":"fake_req_001","TraceId":"fake_trace_002","Elapsed":"1296","StartTime":"1791641301946","IsFromSelf":false,"IsLlmGenerated":false,"CanRating":false,"CanFeedback":false,"ReplyMethod":0,"FromName":"Ryde Dispute Resolution","FromAvatar":"","HasRead":false,"EndTime":"0"}},"Timestamp":"1791641303243","RecordId":""}\n'
    '\n'
    'event: response.processing\n'
    'data: {"Type":"response.processing","Response":{"Role":"assistant","RecordId":"fake_record_002","RelatedRecordId":"fake_record_001","ConversationId":"fake_conv_001","Status":"processing","StatusDesc":"LLM direct reply","ExtraInfo":{"RequestId":"fake_req_001","TraceId":"fake_trace_002","Elapsed":"1296","StartTime":"1791641301946","IsFromSelf":false,"IsLlmGenerated":false,"CanRating":false,"CanFeedback":false,"ReplyMethod":0,"FromName":"","FromAvatar":"","HasRead":false,"EndTime":"0"}},"Timestamp":"1791641303243","RecordId":""}\n'
    '\n'
    'event: message.added\n'
    'data: {"Type":"message.added","Message":{"Type":"reply","MessageId":"rpl_fake_reply_001","Name":"reply","Title":"","Icon":"","Status":"processing","StatusDesc":"Replying","ExtraInfo":{"Elapsed":"0","StartTime":"1791641303740","EndTime":"0"},"RecordId":""},"Timestamp":"1791641303740","RecordId":""}\n'
    '\n'
    'event: content.added\n'
    'data: {"Type":"content.added","MessageId":"rpl_fake_reply_001","ContentIndex":0,"Content":{"Type":"text"},"Timestamp":"1791641303741","RecordId":""}\n'
    '\n'
    'event: text.replace\n'
    'data: {"Type":"text.replace","MessageId":"rpl_fake_reply_001","ContentIndex":0,"Text":"PONG","Timestamp":"1791641303741","RecordId":""}\n'
    '\n'
    'event: message.done\n'
    'data: {"Type":"message.done","MessageId":"rpl_fake_reply_001","Message":{"Type":"reply","MessageId":"rpl_fake_reply_001","Name":"reply","Title":"","Icon":"","Status":"success","StatusDesc":"Reply Completed","Contents":[{"Type":"text","Text":"PONG"}],"ExtraInfo":{"Elapsed":"24","StartTime":"1791641303740","EndTime":"1791641303764"},"RecordId":""},"Timestamp":"1791641303764","RecordId":""}\n'
    '\n'
    'event: response.completed\n'
    'data: {"Type":"response.completed","Response":{"Role":"assistant","RecordId":"fake_record_002","RelatedRecordId":"fake_record_001","ConversationId":"fake_conv_001","Status":"success","StatusDesc":"LLM direct reply","Messages":[{"Type":"reply","MessageId":"rpl_fake_reply_001","Name":"reply","Title":"","Icon":"","Status":"success","StatusDesc":"Reply Completed","Contents":[{"Type":"text","Text":"PONG"}],"ExtraInfo":{"Elapsed":"24","StartTime":"1791641303740","EndTime":"1791641303764"},"RecordId":""}],"Procedures":[{"Name":"large_language_model","Title":"LLM direct reply","Status":"success","IntentCate":"self_awareness","ResourceStatus":0,"Type":"agent","Agent":{"ModelName":"","Input":"","Output":"","Content":"ping","System":"Reply with exactly the word PONG and nothing else.","RewriteQuery":""}}],"StatInfo":{"InputTokens":10,"OutputTokens":5,"TotalTokens":15,"TotalCost":"1817"},"ExtraInfo":{"RequestId":"fake_req_001","TraceId":"fake_trace_002","Elapsed":"1818","StartTime":"1791641301946","IsFromSelf":false,"IsLlmGenerated":true,"CanRating":true,"CanFeedback":false,"ReplyMethod":1,"FromName":"Ryde Dispute Resolution","FromAvatar":"","HasRead":false,"EndTime":"1791641303764"}},"Timestamp":"1791641303765","RecordId":""}\n'
    '\n'
    'event: done\n'
    'data: [DONE]\n'
    '\n'
)

# SSE body without response.completed (for the missing-completion test)
_MOCK_SSE_NO_COMPLETION = (
    'event: request_ack\n'
    'data: {"Type":"request_ack","RequestAck":{"Role":"user","RecordId":"fake_record_003","ConversationId":"fake_conv_003","Status":"success","StatusDesc":"Request Succeeded","Messages":[{"Type":"question","MessageId":"rpl_fake_q_003","Name":"question","Title":"User Question","Icon":"","Status":"success","StatusDesc":"","Contents":[{"Type":"text","Text":"ping"}],"ExtraInfo":{"Elapsed":"0","StartTime":"1791641301000","EndTime":"0"},"RecordId":""}],"ExtraInfo":{"RequestId":"fake_req_003","TraceId":"fake_trace_003","Elapsed":"0","StartTime":"1791641301000","IsFromSelf":true,"IsLlmGenerated":false,"CanRating":false,"CanFeedback":false,"ReplyMethod":0,"FromName":"","FromAvatar":"","HasRead":false,"EndTime":"0"}},"Timestamp":"1791641302094","RecordId":""}\n'
    '\n'
    'event: done\n'
    'data: [DONE]\n'
    '\n'
)


def _make_mock_transport(body: str) -> httpx.MockTransport:
    """Create an httpx MockTransport that returns the given SSE body."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body.encode(),
            headers={"content-type": "text/event-stream"},
        )
    return httpx.MockTransport(handler)


# ---- Config helpers ----

_AGENT = "judge"
_SYSTEM_PROMPT = "Reply with exactly the word PONG and nothing else."
_USER_MESSAGE = "ping"


def _patch_env(**kwargs):
    """Patch environment variables for tests."""
    env = dict(os.environ)
    env.update(kwargs)
    # Remove per-agent keys by default so the fallback ADP_APP_KEY is used.
    for key in ("ADP_APPKEY_RIDER_ADVOCATE", "ADP_APPKEY_DRIVER_ADVOCATE",
                "ADP_APPKEY_JUDGE"):
        env.pop(key, None)
    return patch.dict(os.environ, env, clear=True)


# ---- Tests ----


@pytest.mark.asyncio
async def test_text_and_tokens_parsed(tmp_path):
    """Live call: text and tokens are parsed correctly from the SSE stream."""
    env = {
        "ADP_APP_KEY": "test-key-not-real",
        "USE_MOCK_LLM": "false",
    }
    transport = _make_mock_transport(_MOCK_SSE_BODY)
    with _patch_env(**env):
        result = await chat(
            _AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
            cache_dir=tmp_path, transport=transport,
        )
    assert result.text == "PONG"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.total_tokens == 15
    assert result.cached is False


@pytest.mark.asyncio
async def test_missing_response_completed_raises_llm_error(tmp_path):
    """Stream without response.completed → LLMError."""
    env = {
        "ADP_APP_KEY": "test-key-not-real",
        "USE_MOCK_LLM": "false",
    }
    transport = _make_mock_transport(_MOCK_SSE_NO_COMPLETION)
    with _patch_env(**env):
        with pytest.raises(LLMError, match="without response.completed"):
            await chat(
                _AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
                cache_dir=tmp_path, transport=transport,
            )


@pytest.mark.asyncio
async def test_mock_mode_no_cache_raises(tmp_path):
    """USE_MOCK_LLM=true with no cache entry → LLMError."""
    env = {
        "ADP_APP_KEY": "test-key-not-real",
        "USE_MOCK_LLM": "true",
    }
    with _patch_env(**env):
        with pytest.raises(LLMError, match="No cached response for judge"):
            await chat(
                _AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
                cache_dir=tmp_path,
            )


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_without_request(tmp_path):
    """After a live call, a second call in mock mode returns cached=True."""
    env_live = {
        "ADP_APP_KEY": "test-key-not-real",
        "USE_MOCK_LLM": "false",
    }
    transport = _make_mock_transport(_MOCK_SSE_BODY)

    # Step 1: live call, writes to cache.
    with _patch_env(**env_live):
        result1 = await chat(
            _AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
            cache_dir=tmp_path, transport=transport,
        )
    assert result1.cached is False
    assert result1.text == "PONG"

    # Step 2: mock mode, should read from cache, no HTTP request.
    env_mock = {
        "ADP_APP_KEY": "test-key-not-real",
        "USE_MOCK_LLM": "true",
    }
    with _patch_env(**env_mock):
        result2 = await chat(
            _AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
            cache_dir=tmp_path, transport=transport,
        )
    assert result2.cached is True
    assert result2.text == "PONG"
    assert result2.total_tokens == 15


# ---- parse_model_reply tests ----


def test_parse_model_reply_fenced():
    """parse_model_reply strips ```json fences and validates."""
    reply = (
        "Here is my ruling:\n"
        "```json\n"
        + json.dumps({
            "dispute_id": "DISP-001",
            "outcome": "refund",
            "amount_sgd": 1.07,
            "confidence": 0.9,
            "clauses_cited": ["RD-2.6"],
            "explanation_rider": "The route deviated by 41.4%.",
            "explanation_driver": "The deviation was unjustified.",
            "conduct_flag": False,
            "escalated": False,
            "escalation_reason": None,
        })
        + "\n```\n"
    )
    ruling = parse_model_reply(reply, Ruling)
    assert isinstance(ruling, Ruling)
    assert ruling.outcome == "refund"
    assert ruling.amount_sgd == 1.07


def test_parse_model_reply_invalid_raises():
    """parse_model_reply raises LLMError on invalid JSON/model."""
    reply = "This is not valid JSON at all."
    with pytest.raises(LLMError, match="Failed to parse model reply"):
        parse_model_reply(reply, Ruling)


def test_parse_model_reply_strips_leading_text():
    """parse_model_reply trims text before the first { and after the last }."""
    reply = (
        "I'll explain my reasoning first. "
        '{"dispute_id": "DISP-002", "outcome": "charge_upheld", '
        '"amount_sgd": 5.0, "confidence": 0.92, '
        '"clauses_cited": ["NS-1.6"], '
        '"explanation_rider": "Driver followed protocol.", '
        '"explanation_driver": "All gates passed.", '
        '"conduct_flag": false, "escalated": false, '
        '"escalation_reason": null}'
        " some trailing text"
    )
    ruling = parse_model_reply(reply, Ruling)
    assert isinstance(ruling, Ruling)
    assert ruling.outcome == "charge_upheld"


# ---- Hung requests are retried ----


def _flaky_transport(hangs: int, seen: list) -> httpx.MockTransport:
    """Time out the first *hangs* requests, then return the normal SSE body."""
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        if len(seen) <= hangs:
            raise httpx.ReadTimeout("no data", request=request)
        return httpx.Response(200, content=_MOCK_SSE_BODY.encode(),
                              headers={"content-type": "text/event-stream"})
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_hung_request_retried_with_fresh_ids(tmp_path):
    seen: list = []
    with _patch_env(ADP_APP_KEY="test-key-not-real", USE_MOCK_LLM="false"):
        result = await chat(_AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
                            cache_dir=tmp_path, transport=_flaky_transport(2, seen))
    assert result.text == "PONG"
    assert len(seen) == 3
    assert len({b["RequestId"] for b in seen}) == 3
    assert len({b["ConversationId"] for b in seen}) == 3


@pytest.mark.asyncio
async def test_request_hanging_every_time_raises_clear_error(tmp_path):
    seen: list = []
    with _patch_env(ADP_APP_KEY="test-key-not-real", USE_MOCK_LLM="false"):
        with pytest.raises(LLMError, match="ADP did not respond for judge after 3 attempts"):
            await chat(_AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
                       cache_dir=tmp_path, transport=_flaky_transport(3, seen))
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_retry_switches_to_fallback_model(tmp_path):
    """The first model hangs; the retry asks ADP for the fallback model."""
    seen: list = []
    env = {"ADP_APP_KEY": "test-key-not-real", "USE_MOCK_LLM": "false",
           "ADP_MODEL_NAME": "DeepSeek-V3.2", "ADP_FALLBACK_MODEL_NAME": "Kimi-K2.5"}
    with _patch_env(**env):
        result = await chat(_AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
                            cache_dir=tmp_path, transport=_flaky_transport(1, seen))
    assert result.text == "PONG"
    assert [b["ModelName"] for b in seen] == ["DeepSeek-V3.2", "Kimi-K2.5"]


@pytest.mark.asyncio
async def test_no_model_name_by_default(tmp_path):
    """Without the env vars, the app's own model is used (no ModelName sent)."""
    seen: list = []
    env = {"ADP_APP_KEY": "test-key-not-real", "USE_MOCK_LLM": "false",
           "ADP_MODEL_NAME": "", "ADP_FALLBACK_MODEL_NAME": ""}
    with _patch_env(**env):
        await chat(_AGENT, _SYSTEM_PROMPT, _USER_MESSAGE,
                   cache_dir=tmp_path, transport=_flaky_transport(0, seen))
    assert "ModelName" not in seen[0]
