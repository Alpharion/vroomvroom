# Integration Test Report — RydeResolve

**Project:** RydeResolve — Multi-Agent Autonomous Dispute Resolution System
**Track:** Tencent Cloud AI CAN DO IT Hackathon Singapore 2026, Digital Native Track (Ryde)
**Profile:** HACKATHON_2026
**Date:** 2026-10-11, updated 2026-10-14 (test cases extended from TC-01–TC-11 to TC-01–TC-15)
**Test runner:** pytest 9.1.1, Python 3.14.6, pytest-asyncio 1.4.0
**Policy doc:** `docs/ryde_dispute_policy.md` (organiser v2.1 thresholds)

---

## 1. Summary

| Metric | Value |
|--------|-------|
| Total tests | 135 |
| Passed | 135 |
| Failed | 0 |
| Errors | 0 |
| Total execution time | 2.04s |
| Test files | 8 |
| Test cases (TC-01 to TC-15) | 15 |

All 135 tests pass. Outcomes, amounts, clauses, and confidence values are computed by deterministic Python code (evidence tools + outcome formulas) and validated by the test suite. LLM calls are mocked in tests via `unittest.mock.patch`; no real network calls are made.

> **Update, 14 Oct:** Section 2 now covers TC-01 to TC-15 and reflects the organiser v2.1 policy thresholds. Sections 3 to 5 still describe the suite as of 11 Oct; since then the suite grew from 101 to 135 tests (`test_tools.py` 66, `test_agents.py` 23, `test_api_agents.py` 11, `test_llm.py` 11, `test_review_queue.py` 12 (new), `test_api.py` 7, `test_schemas.py` 4, `test_load_data.py` 1).

---

## 2. Test Case Results — TC-01 through TC-15

Each row maps a test case from `data/test_cases/expected_results.json` to its actual outcome from the real evidence tools and outcome formulas, plus the safety override (the same code path the Judge is checked against). **Pass** means the outcome and the amount match the expected values.

| Case ID | Dispute Type | Expected Outcome | Actual Outcome | Expected Amount (SGD) | Actual Amount (SGD) | Actual Clauses (formula) | Expected Confidence | Live ADP run (13 Oct) | Pass/Fail | Notes |
|---------|-------------|-----------------|----------------|----------------------|---------------------|--------------------------|--------------------|-----------------------|-----------|-------|
| TC-01 | no_show_charge | charge_upheld | charge_upheld | 5.00 (retained) | 5.00 (retained) | NS-1.6 | 0.92 | charge_upheld, conf 0.95, 20.3 s | PASS | All gates pass. Driver arrived 2 min early, waited 8 min (threshold 8), 4 messages and 1 call, 0 rider replies. |
| TC-02 | no_show_charge | charge_reversed | charge_reversed | 5.00 (refund) | 5.00 (refund) | NS-1.3, NS-1.7 | 0.88 | charge_reversed, conf 0.95, 19.3 s | PASS | Driver cancelled after 3 min, under the 5 min free wait (NS-1.3 fails). |
| TC-03 | no_show_charge | charge_reversed | charge_reversed | 5.00 (refund) | 5.00 (refund) | NS-1.1, NS-1.7 | 0.90 | charge_reversed, conf 0.95, 27.8 s | PASS | Driver GPS arrival point 401.1 m from pickup. NS-1.1 fails (arrival radius 10 m). |
| TC-04 | no_show_charge | charge_reversed | charge_reversed | 5.00 (refund) | 5.00 (refund) | NS-1.5, NS-1.7 | 0.89 | charge_reversed, conf 0.95, 24.1 s | PASS | 0 driver messages and 0 calls. NS-1.5 fails (needs at least 1 message AND 1 call). |
| TC-05 | route_deviation | refund | refund | 1.07 | 1.07 | RD-2.6 | 0.90 | refund, conf 0.95, 28.5 s | PASS | 41.4% deviation, metered fare, no rider detour request, no traffic evidence. Refund = 1.5233 km x $0.70/km = $1.07. |
| TC-06 | route_deviation | no_action | no_action | 0.00 | 0.00 | RD-2.3 | 0.93 | no_action, conf 0.95, 18.4 s | PASS | Same 41.4% deviation, but the rider asked for the detour in chat. RD-2.3 fires, no refund. |
| TC-07 | route_deviation | no_action | no_action | 0.00 | 0.00 | RD-2.2 | 0.91 | no_action, conf 0.95, 18.0 s | PASS | 11.9% deviation, below the 20% review threshold. Fixed fare ($12.00). |
| TC-08 | no_show_charge | escalate | escalate | 0.00 | 0.00 | S-1.1, S-1.2 | 0.95 | escalate, conf 0.95, 17.7 s | PASS | Safety keywords ("threat", "threaten", "unsafe") in chat. Safety overrides the no-show formula (which would uphold the charge). |
| TC-09 | no_show_charge | escalate | escalate | 0.00 | 0.00 | NS-1.8, E-1.5 | 0.55 | escalate, conf 0.65, 28.1 s | PASS | GPS has no "arrived" or "waiting" points, so driver presence cannot be verified. Missing evidence escalates. |
| TC-10 | no_show_charge | charge_upheld | charge_upheld | 5.00 (retained) | 5.00 (retained) | NS-1.6 | 0.89 | charge_upheld, conf 0.95, 20.4 s | PASS | Fairness test: rider and driver profiles swapped. Same outcome as TC-01. Profiles do not override trip evidence (E-1.4). |
| TC-11 | route_deviation | escalate | escalate | 0.00 | 0.00 | RD-2.7, E-1.5 | 0.55 | escalate, conf 0.65, 15.3 s | PASS | Only 1 in-trip GPS point (needs at least 2). Actual distance and deviation cannot be computed. |
| TC-12 | no_show_charge | charge_reversed | charge_reversed | 5.00 (refund) | 5.00 (refund) | NS-1.5, NS-1.7 | 0.88 | not run | PASS | New 14 Oct. Driver sent 4 messages but made 0 calls. NS-1.5 fails (needs a message AND a call). |
| TC-13 | route_deviation | no_action | no_action | 0.00 | 0.00 | RD-2.5 | 0.85 | not run | PASS | New 14 Oct. 41.4% deviation on a fixed (up-front) fare: no refund, conduct flag recorded against the driver. |
| TC-14 | route_deviation | escalate | escalate | 0.00 | 0.00 | RD-2.8, E-1.5 | 0.60 | not run | PASS | New 14 Oct. 179% deviation, 6.6 km extra, over the 2 km automatic-ruling limit (organiser v2.1 section 6.2). |
| TC-15 | route_deviation | escalate | escalate | 0.00 | 0.00 | S-1.1, S-1.2 | 0.50 | not run | PASS | New 14 Oct. Route facts alone give a $1.07 refund, but the rider's chat contains "reckless" and "unsafe". The safety override escalates. |

**Totals:** 15/15 PASS. All expected outcomes match actual outcomes. All expected amounts match actual amounts.

**Notes on this table**
- **Clauses:** the "Actual Clauses" column is what the outcome formula cites: the deciding gate only. The expected clause lists in `expected_results.json` are longer for TC-01, TC-05, TC-06, TC-08, TC-09 and TC-10, and the live Judge cites more still (see `docs/live-integration-results.md`). Clause lists are not part of the pass criterion.
- **Confidence:** the column is the fixture's expected value, not a computed one. The live Judge returned 0.95 for resolved cases and 0.65 for TC-09 and TC-11.
- **TC-12 to TC-15:** added on 14 Oct. Their expected outcomes were derived from the formulas and the safety check, not from a live agent run, so they have not been verified live. In stub mode (`USE_STUB_AGENTS=true`) TC-08 and TC-15 do not escalate, because the stub skips the safety check; the real agent graph does.
- **Live ADP run:** the 13 Oct live results come from `docs/live-integration-results.md`. A key issue found on 14 Oct (two keys concatenated in a local `.env`) was fixed and TC-03, TC-08 and TC-11 were re-run live that day: TC-03 charge_reversed (23 s), TC-11 and TC-08 escalated (20 s and 16 s).

---

## 2b. Sample Trips: DISP-001, DISP-001-ORG, DISP-101 to DISP-120 (added 14 Oct)

These 22 trips are the other options in the app's trip dropdown. DISP-101 to DISP-120 were generated by `scripts/build_sample_trips.py`, which runs each trip through the real evidence tools and outcome formulas (plus the safety override) and stops if any result differs from the designed outcome. All 20 matched at build time, and they load in the backend and in the 135-test suite. The designed outcomes are in `data/sample_trips.expected.json`. The live ADP results for these trips are in `docs/live-integration-results.md`.

| Case | Dispute Type | Designed / Expected Outcome | Formula Outcome | Amount (SGD) | Formula Clauses | Live ADP (14 Oct) | Formula Pass/Fail |
|------|-------------|-----------------------------|-----------------|--------------|-----------------|--------------------|-------------------|
| DISP-001 | route_deviation | refund | refund | 1.07 | RD-2.6 | refund, $1.07 | PASS |
| DISP-001-ORG | route_deviation | refund ($3.44, organiser key) | no_action | 0.00 | RD-2.2 | no_action, $0.00 | **FAIL** (see note) |
| DISP-101 | no_show_charge | charge_upheld | charge_upheld | 5.00 | NS-1.6 | charge_upheld | PASS |
| DISP-102 | no_show_charge | charge_upheld (driver 3 min late, flag only) | charge_upheld | 5.00 | NS-1.6 | charge_upheld | PASS |
| DISP-103 | no_show_charge | charge_reversed (waited 3 min) | charge_reversed | 5.00 | NS-1.3, NS-1.7 | **error** (3 of 3 attempts) | PASS |
| DISP-104 | no_show_charge | charge_reversed (driver 150 m away) | charge_reversed | 5.00 | NS-1.1, NS-1.7 | charge_reversed | PASS |
| DISP-105 | no_show_charge | charge_reversed (messages, no call) | charge_reversed | 5.00 | NS-1.5, NS-1.7 | charge_reversed | PASS |
| DISP-106 | no_show_charge | charge_reversed (call, no message) | charge_reversed | 5.00 | NS-1.5, NS-1.7 | charge_reversed | PASS |
| DISP-107 | no_show_charge | charge_upheld (rider replied twice) | charge_upheld | 5.00 | NS-1.6 | charge_upheld | PASS |
| DISP-108 | no_show_charge | charge_reversed (waited 6 min, under 8) | charge_reversed | 5.00 | NS-1.4, NS-1.7 | charge_reversed | PASS |
| DISP-109 | no_show_charge | escalate (no GPS arrival record) | escalate | 0.00 | NS-1.8, E-1.5 | escalate | PASS |
| DISP-110 | no_show_charge | escalate (safety, rider reports a threat) | escalate | 0.00 | S-1.1, S-1.2 | escalate | PASS |
| DISP-111 | route_deviation | refund (30% longer) | refund | 1.08 | RD-2.6 | refund, $1.08 | PASS |
| DISP-112 | route_deviation | refund (25% longer) | refund | 1.25 | RD-2.6 | refund, $1.25 | PASS |
| DISP-113 | route_deviation | no_action (10% longer, under threshold) | no_action | 0.00 | RD-2.2 | no_action | PASS |
| DISP-114 | route_deviation | no_action (rider asked for the detour) | no_action | 0.00 | RD-2.3 | no_action | PASS |
| DISP-115 | route_deviation | no_action (fixed fare, conduct flag) | no_action | 0.00 | RD-2.5 | no_action | PASS |
| DISP-116 | route_deviation | escalate (over 2 km, fare S$31.44, high priority) | escalate | 0.00 | RD-2.8, E-1.5 | escalate | PASS |
| DISP-117 | route_deviation | escalate (incomplete GPS) | escalate | 0.00 | RD-2.7, E-1.5 | escalate | PASS |
| DISP-118 | route_deviation | escalate (safety complaint) | escalate | 0.00 | S-1.1, S-1.2 | escalate | PASS |
| DISP-119 | route_deviation | refund (40% longer) | refund | 1.14 | RD-2.6 | refund, $1.14 | PASS |
| DISP-120 | route_deviation | refund (60% longer) | refund | 0.78 | RD-2.6 | refund, $0.78 | PASS |

**Totals:** formulas match the designed or expected outcome for 21 of 22 trips. The exception is DISP-001-ORG.

**Notes**
- **DISP-001-ORG:** the organiser's key expects a $3.44 refund. The formulas and the live Judge both give no_action, because the case's GPS route (20.7 km) is shorter than the baseline the tools compute (straight-line distance x 1.3 = 24.6 km), so it does not register as a detour. The baseline method does not reproduce the organiser's reference route for this trip.
- **DISP-103:** the formulas give the right answer, but the live Rider Advocate returns an argument with no evidence reference twice in a row, so the live hearing fails. See `docs/live-integration-results.md`.
- **Stub backend:** in stub mode (`USE_STUB_AGENTS=true`) the safety trips DISP-110 and DISP-118 do not escalate, and the high-fare trip DISP-116 is not marked high priority, because the stub skips the safety and fare checks for route cases. The real agent graph does all three.

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
| TC-10 (swapped profiles) | E-1.4 | PASS | Rider/driver profiles swapped — same outcome as TC-01 (charge_upheld, $5.00, NS-1.6). The fixture's expected confidence differs slightly (0.89 vs 0.92), but the profiles do not override trip evidence. |

**Result:** The system treats both advocates identically and does not let ratings, histories, or fraud flags override trip evidence in the outcome determination.

---

## 7. Safety Escalation Tests (S-1.1, S-1.2)

| Test | Pass | Verification |
|------|------|--------------|
| test_tc08_safety_incident_escalates | PASS | TC-08 chat logs contain "threatened" and "unsafe". safety_override returns ("escalate", 0.0, ["S-1.1", "S-1.2"], False). Formula clauses (NS-1.6) dropped. escalation_reason starts with "Safety incident: keyword: ". Judge's prompt contains "Safety incident detected". |
| test_no_safety_incident_keeps_formula_outcome | PASS | DISP-002 mentions "White Toyota" — no safety keyword hit. safety_override returns None. Formula outcome stands: charge_upheld, $5.00. |
| test_tc08_safety_routed_to_human_review | PASS | End-to-end API test: TC-08 escalates, final stream line: "Routed to the human review queue." |
| test_safety_no_false_positive_on_white_toyota | PASS | Word-boundary matching: "hit" does not match "White" in "White Toyota Prius". |
| test_safety_only_tc08_and_tc15_flagged_across_dataset | PASS | Across all DISP-00*.json and TC-*.json files, only TC-08 and TC-15 (the two deliberate safety cases) trigger a safety incident. |
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

3. **Pre-cache LLM responses** for all 15 test cases by running `run_case.py` once with `USE_MOCK_LLM=false` and a valid `ADP_APP_KEY`. This populates `backend/.cache/` so `run_case.py` can run end-to-end without API calls.

4. **Add a CI pipeline** (GitHub Actions) to run `pytest` on every push and pull request, preventing regressions.

5. **Add an end-to-end integration test** that runs `resolve_case()` against all 15 TCs and compares the resulting `Ruling` to `data/test_cases/expected_results.json` — outcome, amount, clauses, confidence, and escalation status.

6. **Add `.gitattributes`** with `*.md text eol=lf` to prevent OneDrive and Windows from flipping line endings between CRLF and LF, which causes spurious git diffs and can interfere with file parsing.

7. **Set `PYTHONDONTWRITEBYTECODE=1`** in the test environment, or add a `conftest.py` that clears `__pycache__` on startup, to prevent stale bytecode from masking source fixes.

8. **Add `encoding="utf-8"`** to all `Path.read_text()` and `open()` calls in the codebase, not just the policy doc parser, to prevent encoding-related failures on Windows.
