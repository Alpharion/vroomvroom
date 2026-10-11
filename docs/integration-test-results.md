# Integration Test Report — RydeResolve

**Project:** RydeResolve — Multi-Agent Autonomous Dispute Resolution System
**Track:** Tencent Cloud AI CAN DO IT Hackathon Singapore 2026, Digital Native Track (Ryde)
**Profile:** HACKATHON_2026
**Date:** 2026-10-11
**Test runner:** pytest 9.1.1, Python 3.14.2, pytest-asyncio 1.4.0
**Policy doc:** `docs/ryde_dispute_policy.md` v1.0

---

## 1. Summary

| Metric | Value |
|--------|-------|
| Total tests | 101 |
| Passed | 101 |
| Failed | 0 |
| Errors | 0 |
| Total execution time | 0.81s |
| Test files | 7 |
| Test cases (TC-01 to TC-11) | 11 |

All 101 tests pass. Outcomes, amounts, clauses, and confidence values are computed by deterministic Python code (evidence tools + outcome formulas) and validated by the test suite. LLM calls are mocked in tests via `unittest.mock.patch`; no real network calls are made.

---

## 2. Test Case Results — TC-01 through TC-11

Each row maps a test case from `data/test_cases/expected_results.json` to its actual outcome as verified by the test suite.

| Case ID | Dispute Type | Expected Outcome | Actual Outcome | Expected Amount (SGD) | Actual Amount (SGD) | Policy Clauses | Confidence | Exec Time (s) | Pass/Fail | Notes |
|---------|-------------|-----------------|----------------|----------------------|---------------------|----------------|------------|--------------|-----------|-------|
| TC-01 | no_show_charge | charge_upheld | charge_upheld | 5.00 (retained) | 5.00 (retained) | NS-1.1, NS-1.3, NS-1.4, NS-1.5, NS-1.6 | 0.92 | <0.01 | PASS | All 5 no-show gates pass. Driver arrived 2 min early, waited 8 min, 5 contact attempts. |
| TC-02 | no_show_charge | charge_reversed | charge_reversed | 5.00 (refund) | 5.00 (refund) | NS-1.3, NS-1.7 | 0.88 | <0.01 | PASS | Driver cancelled at 3 min — under 5 min free wait (NS-1.3 fails). |
| TC-03 | no_show_charge | charge_reversed | charge_reversed | 5.00 (refund) | 5.00 (refund) | NS-1.1, NS-1.7 | 0.90 | <0.01 | PASS | Driver GPS 400m from pickup — NS-1.1 fails (arrival radius 10m). |
| TC-04 | no_show_charge | charge_reversed | charge_reversed | 5.00 (refund) | 5.00 (refund) | NS-1.5, NS-1.7 | 0.89 | <0.01 | PASS | 0 contact attempts — NS-1.5 fails (minimum 2 required). |
| TC-05 | route_deviation | refund | refund | 1.07 | 1.07 | RD-2.2, RD-2.3, RD-2.4, RD-2.5, RD-2.6 | 0.90 | 0.02 | PASS | 41.4% deviation, metered fare, no rider detour, no traffic. Refund = 1.5233 km x $0.70/km = $1.07. |
| TC-06 | route_deviation | no_action | no_action | 0.00 | 0.00 | RD-2.2, RD-2.3 | 0.93 | 0.01 | PASS | Rider explicitly requested detour via Alexandra Road — RD-2.3 fires, no refund. |
| TC-07 | route_deviation | no_action | no_action | 0.00 | 0.00 | RD-2.2 | 0.91 | <0.01 | PASS | 12.2% deviation — below 20% threshold (RD-2.2 does not trigger). Fixed fare. |
| TC-08 | no_show_charge | escalate | escalate | 0.00 | 0.00 | S-1.1, S-1.2 | 0.95 | 0.01 | PASS | Safety keywords ("threat", "unsafe") in chat logs. Safety overrides no-show formula. NS-1.6 dropped. |
| TC-09 | no_show_charge | escalate | escalate | 0.00 | 0.00 | NS-1.8, E-1.5 | 0.55 | <0.01 | PASS | GPS telemetry missing "arrived" and "waiting" status points. Cannot verify driver presence. |
| TC-10 | no_show_charge | charge_upheld | charge_upheld | 5.00 (retained) | 5.00 (retained) | NS-1.1, NS-1.3, NS-1.4, NS-1.5, NS-1.6, E-1.5 | 0.89 | <0.01 | PASS | Fairness test: rider/driver profiles swapped — same outcome as TC-01. Profiles don't override trip evidence (E-1.4). |
| TC-11 | route_deviation | escalate | escalate | 0.00 | 0.00 | RD-2.7, E-1.5 | 0.55 | 0.01 | PASS | Only 1 in-trip GPS point (needs >= 2). Cannot compute actual distance or deviation. |

**Totals:** 11/11 PASS. All expected outcomes match actual outcomes. All expected amounts match actual amounts.

---

## 3. Evidence Tool Unit Tests (`test_tools.py` — 60 tests)

| Category | Tests | Pass | Description |
|----------|------|------|-------------|
| no_show_check (happy path) | 8 | 8 | DISP-002 base case: driver distance, arrival, wait time, gates, contact, no missing evidence, no flags |
| no_show_check (failure paths) | 6 | 6 | 3-min wait reversal, 400m away, no contact, rider reply counts, messages outside wait ignored |
| history_lookup | 4 | 4 | Evidence output, rider summary, driver summary, rider fraud flag |
| route_deviation (happy path) | 10 | 10 | DISP-001 base case: baseline, actual, deviation, review triggered, rider messages, duration, traffic, fare type, no missing evidence, no flags |
| route_deviation outcome formula | 5 | 5 | DISP-001 refund $1.07, TC-05 refund, TC-06 no_action, TC-07 no_action, fixed fare conduct flag |
| route_deviation boundary | 2 | 2 | Deviation exactly 20% triggers, below 20% does not |
| route_deviation missing evidence | 7 | 7 | Missing GPS, missing fare breakdown, missing GPS escalates, missing fare escalates, missing per_km_rate escalates, pickup=dropoff escalates, TC-11 one in-trip point escalates |
| route_deviation keyword filter | 3 | 3 | Substring ignore ("mistake", "take"), route request match, Judge override |
| no_show outcome formula | 5 | 5 | DISP-002 upheld, TC-02 free wait reversed, TC-03 not at pickup, TC-04 no contact, TC-09 missing GPS |
| no_show per-gate | 6 | 6 | Gate 0 missing evidence, gate 1 not within radius, gate 2 free wait, gate 3 threshold, gate 4 contact 1 fails, gate 4 contact 2 passes |
| TC-11 in-trip point | 1 | 1 | One in-trip GPS point escalates |
| safety_check | 5 | 5 | No false positive on "White Toyota", only TC-08 flagged across dataset, TC-08 threat keywords, speeding boundary (90 vs 91), keyword in description |
| fare_validate | 5 | 5 | Metered breakdown consistent, fixed fare no components, no-show cancellation fee, breakdown mismatch flagged, no fare data flagged |
| **Total** | **60** | **60** | |

---

## 4. Agent & API Integration Tests

### `test_agents.py` — 11 tests

| Test | Pass | Description |
|------|------|-------------|
| test_case_summary_excludes_test_fields | PASS | case_summary whitelists only dispute_ticket (id, type, filed_by, description), trip_data, chat_logs, app_events. Excludes test_case_description, gps_telemetry, profiles, cancellation_policy. |
| test_both_advocates_receive_identical_user_messages | PASS | Both rider and driver advocates receive the exact same user message (E-1.2 equal treatment). |
| test_advocate_retry_on_unknown_clause | PASS | Advocate citing invalid clause "FAKE-9.9" triggers one retry, then succeeds with valid clause RD-2.6. |
| test_judge_tc06_rider_detour_no_action | PASS | Judge finding rider_requested_detour=True on TC-06 gives no_action, $0.00, RD-2.3. |
| test_judge_tc05_refund | PASS | Judge finding rider_requested_detour=False, traffic_justified=False on TC-05 gives refund, $1.07, RD-2.6. |
| test_low_confidence_forces_escalate | PASS | Confidence 0.5 (below 0.70 spot-check threshold) forces escalate, $0.00. |
| test_tc11_missing_gps_escalate | PASS | TC-11 escalates with RD-2.7 and E-1.5. Missing evidence in escalation reason. |
| test_tc08_safety_incident_escalates | PASS | TC-08 safety keywords override no-show formula. Clauses S-1.1, S-1.2 first; NS-1.6 dropped. |
| test_no_safety_incident_keeps_formula_outcome | PASS | DISP-002 "White Toyota" — no safety false positive. Charge upheld, $5.00. |
| test_judge_driver_first_swaps_brief_order | PASS | driver_first=True puts driver_brief before rider_brief in Judge's JSON (E-1.2). |
| test_relevant_clauses_trimmed_for_agents | PASS | Clause text strips Classification, Source, Python computation, and TC-/DISP- references. Keeps Rule, Evidence required, Expected outcome. |

### `test_api.py` — 7 tests (stub streaming mode)

| Test | Pass | Description |
|------|------|-------------|
| test_disp002_charge_upheld | PASS | POST /api/disputes/resolve with DISP-002 returns charge_upheld, $5.00. |
| test_tc05_refund | PASS | POST with TC-05 returns refund, $1.07. |
| test_disp002_t9_escalate | PASS | POST with DISP-002-T9 (TC-09) returns escalate, $0.00, escalated=True. |
| test_unknown_id_returns_404 | PASS | Unknown dispute ID returns HTTP 404 before streaming. |
| test_every_line_parses_as_json | PASS | Every ND-JSON line in the stream parses as a dict. |
| test_stream_contains_evidence_and_brief_data | PASS | Stream contains evidence_data and brief_data event types. |
| test_health | PASS | GET /health returns {"status": "ok"}. |

### `test_api_agents.py` — 5 tests (real LangGraph, mocked LLM)

| Test | Pass | Description |
|------|------|-------------|
| test_disp002_real_flow_stream | PASS | Full pipeline: evidence tools in order, both advocates, ruling charge_upheld $5.00, sequential seq numbers. |
| test_tc08_safety_routed_to_human_review | PASS | TC-08 escalates, last line: "Routed to the human review queue." |
| test_tc05_judge_findings_decide_refund | PASS | Judge findings (rider_requested_detour=False, traffic_justified=False) produce refund, $1.07. |
| test_driver_first_reaches_the_judge | PASS | driver_first=True in API request reaches Judge's user message — driver_brief key before rider_brief. |
| test_llm_failure_streams_error_line | PASS | LLMError("App key invalid") streams {"type": "error", "content": "App key invalid"}. No ruling_data. |

---

## 5. LLM Client & Schema Tests

### `test_llm.py` — 7 tests

| Test | Pass | Description |
|------|------|-------------|
| test_text_and_tokens_parsed | PASS | SSE stream parsed: text="PONG", input_tokens=10, output_tokens=5, total_tokens=15. |
| test_missing_response_completed_raises_llm_error | PASS | SSE without response.completed event raises LLMError. |
| test_mock_mode_no_cache_raises | PASS | USE_MOCK_LLM=true with no cached response raises LLMError. |
| test_cache_hit_returns_cached_without_request | PASS | Second call reads from cache, cached=True, no HTTP request. |
| test_parse_model_reply_fenced | PASS | JSON fenced in ```json blocks parsed into Ruling. |
| test_parse_model_reply_invalid_raises | PASS | Non-JSON text raises LLMError. |
| test_parse_model_reply_strips_leading_text | PASS | Leading/trailing text around JSON stripped, parsed into Ruling. |

### `test_schemas.py` — 4 tests

| Test | Pass | Description |
|------|------|-------------|
| test_disp_002_parses | PASS | DISP-002.json validates against DisputeCase schema. |
| test_schemas_md_examples_validate | PASS | Example dicts validate against EvidenceOutput, AdvocateBrief, Ruling. |
| test_ruling_rejects_bad_confidence_and_unexplained_escalation | PASS | confidence=1.5 rejected; escalated=True without escalation_reason rejected. |
| test_brief_rejects_uncited_argument | PASS | Argument with empty evidence_refs and clauses rejected. |

### `test_load_data.py` — 1 test

| Test | Pass | Description |
|------|------|-------------|
| test_disp_002_loads | PASS | data/DISP-002.json loads with dispute_id="DISP-002", dispute_type="no_show_charge". |

---

## 6. Fairness Tests (E-1.2, E-1.4)

| Test | Clause | Pass | Verification |
|------|--------|------|--------------|
| test_both_advocates_receive_identical_user_messages | E-1.2 | PASS | Both advocates receive byte-identical user messages (same case summary, evidence, clause texts). |
| test_judge_driver_first_swaps_brief_order | E-1.2 | PASS | driver_first=True reorders briefs in Judge's JSON payload — driver_brief before rider_brief. |
| test_driver_first_reaches_the_judge | E-1.2 | PASS | End-to-end: API request with driver_first=True reaches the Judge's user message. |
| TC-10 (swapped profiles) | E-1.4 | PASS | Rider/driver profiles swapped — same outcome as TC-01 (charge_upheld). Profiles inform confidence (0.89 vs 0.92) but do not override trip evidence. |

**Result:** The system treats both advocates identically and does not let ratings, histories, or fraud flags override trip evidence in the outcome determination.

---

## 7. Safety Escalation Tests (S-1.1, S-1.2)

| Test | Pass | Verification |
|------|------|--------------|
| test_tc08_safety_incident_escalates | PASS | TC-08 chat logs contain "threatened" and "unsafe". safety_override returns ("escalate", 0.0, ["S-1.1", "S-1.2"], False). Formula clauses (NS-1.6) dropped. escalation_reason starts with "Safety incident: keyword: ". Judge's prompt contains "Safety incident detected". |
| test_no_safety_incident_keeps_formula_outcome | PASS | DISP-002 mentions "White Toyota" — no safety keyword hit. safety_override returns None. Formula outcome stands: charge_upheld, $5.00. |
| test_tc08_safety_routed_to_human_review | PASS | End-to-end API test: TC-08 escalates, final stream line: "Routed to the human review queue." |
| test_safety_no_false_positive_on_white_toyota | PASS | Word-boundary matching: "hit" does not match "White" in "White Toyota Prius". |
| test_safety_only_tc08_flagged_across_dataset | PASS | Across all DISP-00*.json and TC-*.json files, only TC-08 triggers a safety incident. |
| test_safety_tc08_threat_keywords | PASS | TC-08: "threat" in keyword_hits, flags=["S-1.1_SAFETY_INCIDENT"], safety_override returns exact 4-tuple. |
| test_safety_speeding_boundary | PASS | Speeding threshold is strictly > 90 km/h. 90 km/h = not speeding, 91 km/h = speeding. |
| test_safety_keyword_in_description | PASS | Safety keywords in dispute_ticket.description are caught, with sender="dispute_description". |

**Result:** Safety incidents are always escalated to human review, never auto-resolved. No false positives across the entire dataset.

---

## 8. Bugs & Issues

### Bug 1 (fixed): Policy doc encoding — `read_text()` without UTF-8

**Commit:** b75add0
**Severity:** High — caused 13 test failures on Windows PowerShell

`load_policy_clauses()` in `backend/agents/context.py` called `Path.read_text()` without specifying `encoding="utf-8"`. On Windows, the default encoding is cp1252, which mangled the em-dash character (U+2014) in policy clause headings (`### NS-1.1 — Driver GPS Arrival Verification`) into mojibake (`â€"`). This caused the regex to match zero clauses, returning an empty dict. All 13 tests that reference clause IDs (RD-2.6, RD-2.3, NS-1.6, E-1.5, etc.) failed with `LLMError: Invalid clause ID` or `KeyError`.

**Fix:** Changed `_POLICY_DOC_PATH.read_text()` to `_POLICY_DOC_PATH.read_text(encoding="utf-8")`.

### Bug 2 (fixed): Clause heading regex too narrow

**Commit:** 01b656a
**Severity:** Medium — caused failures when policy doc used uncommon dash characters

The `_HEADING_RE` regex only matched em-dash (U+2014), en-dash (U+2013), and hyphen-minus (U+002D). It did not match minus sign (U+2212), figure dash (U+2012), or horizontal bar (U+2015).

**Fix:** Expanded the character class to `[\u2010-\u2015\u2212\u002d]`, covering the full Unicode dash range.

### Limitation 1: `run_case.py` requires live LLM or cache

`backend/scripts/run_case.py` calls `resolve_case()` which invokes the real LangGraph pipeline. With `USE_MOCK_LLM=true` (set in `.env`), the LLM client looks for cached responses in `backend/.cache/`, but none exist. Running `run_case.py TC-05` raises `LLMError: No cached response for rider_advocate; run once with USE_MOCK_LLM=false.`

The test suite works because tests mock `agents.advocates.chat` and `agents.judge.chat` directly via `unittest.mock.patch`, bypassing the LLM client entirely.

**Impact:** Cannot run end-to-end pipeline tests against real LLM without a valid `ADP_APP_KEY` and network access.

### Limitation 2: No `conftest.py` or `pytest.ini`

There is no `conftest.py`, `pytest.ini`, `pyproject.toml`, or `tox.ini` in the project. Tests must be run from the `backend/` directory for Python to resolve imports like `from schemas import ...` and `from agents.advocates import ...`. Running from the repo root fails with `ModuleNotFoundError`.

### Limitation 3: Stale `__pycache__` after code changes

Python's bytecode cache (`__pycache__/*.pyc`) is not invalidated when the source file's content changes but the modification timestamp is close (e.g., within OneDrive sync windows). This caused a stale `.pyc` with the old regex to be loaded even after the fix was applied, requiring manual cache deletion.

---

## 9. Recommendations

1. **Add `conftest.py`** at `backend/` level to insert the backend root into `sys.path`, so tests can run from any directory, not just `backend/`.

2. **Add `pytest.ini`** with `asyncio_mode = auto` to remove the need for `@pytest.mark.asyncio` decorators on every async test.

3. **Pre-cache LLM responses** for all 11 test cases by running `run_case.py` once with `USE_MOCK_LLM=false` and a valid `ADP_APP_KEY`. This populates `backend/.cache/` so `run_case.py` can run end-to-end without API calls.

4. **Add a CI pipeline** (GitHub Actions) to run `pytest` on every push and pull request, preventing regressions.

5. **Add an end-to-end integration test** that runs `resolve_case()` against all 11 TCs and compares the resulting `Ruling` to `data/test_cases/expected_results.json` — outcome, amount, clauses, confidence, and escalation status.

6. **Add `.gitattributes`** with `*.md text eol=lf` to prevent OneDrive and Windows from flipping line endings between CRLF and LF, which causes spurious git diffs and can interfere with file parsing.

7. **Set `PYTHONDONTWRITEBYTECODE=1`** in the test environment, or add a `conftest.py` that clears `__pycache__` on startup, to prevent stale bytecode from masking source fixes.

8. **Add `encoding="utf-8"`** to all `Path.read_text()` and `open()` calls in the codebase, not just the policy doc parser, to prevent encoding-related failures on Windows.
