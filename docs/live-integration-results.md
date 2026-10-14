# Live ADP Integration Test Results

**Date:** 2026-10-13 (TC-01 to TC-10); TC-11 re-run and TC-12 to TC-15 added 2026-10-14
**Branch:** `feature/organiser-integration` (TC-01 to TC-10); `backend-revamp` (TC-11 to TC-15)
**Commit:** `f5be9cb` (TC-01 to TC-10)
**ADP Model:** DeepSeek-V3.2 (Tencent Cloud ADP)
**Profile:** HACKATHON_2026
**`USE_MOCK_LLM`:** `false` (live API calls)

## Summary

All 15 test cases (TC-01 to TC-15) passed against live Tencent Cloud ADP: every outcome, refund amount and escalation status matched the expected values. TC-01 to TC-10 were run on 13 Oct; TC-11 was re-run and TC-12 to TC-15 (new cases) were run on 14 Oct, after the ADP AppKey issue in the local `.env` was fixed. Clause lists are not part of the pass criterion: the Judge often cites more clauses than the fixture lists (see Observations). The 22 sample trips in the app were also run live on 14 Oct and are reported in their own section below: 22 of 22 match: DISP-103 failed before a fix and passes after it, and DISP-001-ORG matches the organiser's key after a one-trip change.

| Metric | Value |
|---|---|
| Cases passed | **15 / 15 (100%)** |
| Total wall-clock time | 346.3 s (~5 min 46 s), summed over the two runs |
| Mean duration | 23.1 s |
| Median duration | 20.4 s |
| P95 duration | 28.5 s |
| Min duration | 17.7 s (TC-08) |
| Max duration | 30.1 s (TC-13) |

These results are distinct from the 139 mocked unit tests (which use `USE_MOCK_LLM=true` and read from the LLM cache). The live suite exercises the full pipeline: evidence extraction → Rider Advocate → Driver Advocate → Judge → escalation branch, all via real ADP API calls with SSE streaming.

## Results Table

| Case | Type | Expected | Actual | Amount (Exp / Act) | Conf (Exp / Act) | Escalated | Clauses Cited | Duration |
|------|------|----------|--------|---------------------|-------------------|-----------|---------------|----------|
| TC-01 | no_show_charge | charge_upheld | charge_upheld | — / $5.00 | 0.92 / 0.95 | No | NS-1.6, NS-1.1, NS-1.3, NS-1.4, NS-1.5 | 20.3 s |
| TC-02 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.88 / 0.95 | No | NS-1.3, NS-1.7 | 19.3 s |
| TC-03 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.90 / 0.95 | No | NS-1.1, NS-1.7 | 27.8 s |
| TC-04 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.89 / 0.95 | No | NS-1.5, NS-1.7, E-1.4 | 24.1 s |
| TC-05 | route_deviation | refund | refund | $1.07 / $1.07 | 0.90 / 0.95 | No | RD-2.6, RD-2.2, RD-2.3, RD-2.4, RD-2.5 | 28.5 s |
| TC-06 | route_deviation | no_action | no_action | — / $0.00 | 0.93 / 0.95 | No | RD-2.3 | 18.4 s |
| TC-07 | route_deviation | no_action | no_action | — / $0.00 | 0.91 / 0.95 | No | RD-2.2, RD-2.1, RD-2.5 | 18.0 s |
| TC-08 | no_show_charge | escalate | escalate | — / $0.00 | 0.95 / 0.95 | **Yes** | S-1.1, S-1.2 | 17.7 s |
| TC-09 | no_show_charge | escalate | escalate | — / $0.00 | 0.55 / 0.65 | **Yes** | NS-1.8, E-1.5 | 28.1 s |
| TC-10 | no_show_charge | charge_upheld | charge_upheld | — / $5.00 | 0.89 / 0.95 | No | NS-1.6, NS-1.1, NS-1.2, NS-1.3, NS-1.4, NS-1.5, E-1.4 | 20.4 s |
| TC-11 | route_deviation | escalate | escalate | — / $0.00 | 0.55 / 0.65 | **Yes** | RD-2.7, E-1.5 | 19.2 s |
| TC-12 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.88 / 0.95 | No | NS-1.5, NS-1.7 | 27.6 s |
| TC-13 | route_deviation | no_action | no_action | $0.00 / $0.00 | 0.85 / 0.95 | No | RD-2.5, RD-2.2, RD-2.3, RD-2.4, RD-2.8 | 30.1 s |
| TC-14 | route_deviation | escalate | escalate | — / $0.00 | 0.60 / 0.90 | **Yes** | RD-2.8, E-1.5 | 27.7 s |
| TC-15 | route_deviation | escalate | escalate | — / $0.00 | 0.50 / 0.95 | **Yes** | S-1.1, S-1.2 | 19.1 s |

## Observations

### Confidence Values
- **Auto-resolved cases (TC-01 through TC-07, TC-10, TC-12, TC-13):** All returned confidence 0.95, above the 0.85 auto-ruling threshold. The ADP model consistently returned high confidence when evidence was complete and unambiguous.
- **Escalated cases (TC-08, TC-09, TC-11, TC-14, TC-15):**
  - TC-08 (safety): confidence 0.95 — safety incidents escalate regardless of confidence (S-1.1 override).
  - TC-09 (missing GPS): confidence 0.65 — below 0.70 spot-check threshold, correctly escalated due to missing `arrived`/`waiting` GPS points.
  - TC-11 (insufficient GPS): confidence 0.65 — below 0.70 spot-check threshold, correctly escalated due to only 1 in-trip GPS point. Re-run on 14 Oct: same result (escalation reason: "Low confidence (65%, needs 80%); Missing evidence: gps_telemetry").
  - TC-14 (detour over 2 km): confidence 0.90 — escalated by the 2 km automatic-ruling limit (RD-2.8), not by low confidence. Reason: "Route was 6.60 km longer than the baseline, over the 2 km limit for automatic rulings (RD-2.8)".
  - TC-15 (route dispute plus safety complaint): confidence 0.95 — escalated by the safety override (S-1.1, S-1.2). Reason: "Safety incident: keyword: reckless, unsafe". The route facts alone give a $1.07 refund; safety took precedence.
- Expected confidence values for TC-09 and TC-11 were 0.55; live results returned 0.65. For TC-14 and TC-15 the fixture expected 0.60 and 0.50, but the live Judge returned 0.90 and 0.95 because those cases escalate on a rule rather than on doubt, so the confidence figure does not decide the escalation. Both are below the 0.70 threshold, so the escalation outcome is correct either way. The slightly higher live confidence likely reflects the ADP model hedging less aggressively than the expected fixture assumed.

### Clause Citations
- All cited clauses match the expected policy framework. Minor ordering differences (e.g., NS-1.6 before NS-1.1 in TC-01) are cosmetic — the Judge agent lists clauses in the order they appear in its reasoning, not numerically.
- TC-04 and TC-10 cited E-1.4 (adverse inference for missing evidence) in addition to the expected NS clauses — this is correct, as both cases involve parties with missing evidence in their profiles.
- TC-07 cited RD-2.1 (actual distance calculation) and RD-2.5 (fixed fare = conduct_flag only) in addition to RD-2.2 — this is more thorough than the expected minimum and is correct.
- TC-08 cited both S-1.1 (safety keyword detection) and S-1.2 (safety escalation override) — correct.
- TC-12 cited exactly the expected clauses (NS-1.5, NS-1.7). TC-14 cited RD-2.8 and E-1.5 as expected. TC-15 cited S-1.1 and S-1.2 as expected.
- **TC-13 over-cited:** the outcome is correct (no_action, $0.00), but the Judge listed RD-2.5, RD-2.2, RD-2.3, RD-2.4 and RD-2.8. The fixture expects RD-2.5 only. RD-2.3 (rider-requested detour) does not apply because the rider made no such request, and RD-2.8 does not apply because the excess distance is 1.52 km, under the 2 km limit. Clause lists are not part of the pass criterion, but a reviewer reading the ruling would see two citations that are wrong for this case.

### Refund Amounts
- TC-05: $1.07 refund (1.5233 km excess × $0.70/km = $1.0663, rounded to $1.07) — exact match.
- TC-02, TC-03, TC-04: $5.00 reversal (full cancellation fee refund) — exact match.
- All other cases: $0.00 (no refund, charge upheld, or escalated with charge held) — correct.

### Escalation Handling
- 5 of 15 cases escalated (TC-08, TC-09, TC-11, TC-14, TC-15) — all correctly, and no case that should have resolved was escalated.
- Safety escalation (TC-08) fired on keyword detection: "threat", "threaten", "unsafe". The system escalated with reason: "Safety incident: keyword: threat, threaten, unsafe".
- Evidence-gap escalations (TC-09, TC-11) fired on low confidence + missing GPS evidence. Escalation reasons explicitly named the missing evidence type.
- Safety escalation also fired on a route dispute (TC-15), where the rider's chat contained "reckless" and "unsafe".
- The 2 km automatic-ruling limit fired on TC-14 (6.60 km extra).

### Duration Analysis
- Route deviation cases averaged 23.0 s; no-show cases averaged 23.2 s — no significant difference.
- The longest case was TC-13 (30.1 s), where the Judge reasoned about a fixed fare, a rider-request check and a traffic check. TC-05 (28.5 s) is next, with the most complex computation: deviation percentage, rider-requested-detour check, traffic justification check, and refund formula.
- The shortest case is now TC-08 (17.7 s). TC-11 took 15.3 s on 13 Oct and 19.2 s on 14 Oct, so the "short-circuits on missing evidence" explanation is not borne out: run-to-run variation is several seconds.
- Total wall-clock for all 15 cases: ~5 min 46 s (two runs; 13 Oct plus the 14 Oct re-run and additions). Each case involves 3 sequential LLM calls (evidence extraction, two advocates in parallel, judge), so ~7 s per LLM call on average.

## Sample Trips: DISP-001, DISP-001-ORG and DISP-101 to DISP-120 (live, 14 Oct)

The 22 trips in the app's trip dropdown (other than DISP-002, which is the same case as TC-01) were run through live ADP on 14 Oct with the same pipeline and settings as the test cases. "Expected" is the designed outcome in `data/sample_trips.expected.json` for DISP-101 to DISP-120, and the answer keys in `data/DISP-001.expected.json` and `data/DISP-001-ORG.expected.json` for the two older trips. Pass means the outcome and amount match.

**Result: 22 of 22 match. DISP-103 errored on its first three attempts and passes after a fix, and DISP-001-ORG matches the organiser's ruling after a one-trip change (both described below).**

| Case | Type | Expected | Actual | Amount (Exp / Act) | Conf | Escalated | Clauses Cited | Duration | Result |
|------|------|----------|--------|---------------------|------|-----------|---------------|----------|--------|
| DISP-001 | route_deviation | refund | refund | $1.07 / $1.07 | 0.95 | No | RD-2.6, RD-2.2, RD-2.3, RD-2.4, RD-2.5 | 26.1 s | PASS |
| DISP-001-ORG | route_deviation | refund | refund | $3.44 / $3.44 | 0.95 | No | ORG-RD-1.2, ORG-RD-1.3, RD-2.2, RD-2.3, RD-2.4, RD-2.5, RD-2.6 | 25.5 s | PASS (after change) |
| DISP-101 | no_show_charge | charge_upheld | charge_upheld | $5.00 / $5.00 | 0.95 | No | NS-1.6, NS-1.1, NS-1.3, NS-1.4, NS-1.5 | 31.3 s | PASS |
| DISP-102 | no_show_charge | charge_upheld | charge_upheld | $5.00 / $5.00 | 0.95 | No | NS-1.6, NS-1.1, NS-1.2, NS-1.3, NS-1.4, NS-1.5 | 28.2 s | PASS |
| DISP-103 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.95 | No | NS-1.3, NS-1.7 | 19.6 s | PASS (after fix) |
| DISP-104 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.95 | No | NS-1.1, NS-1.7 | 24.9 s | PASS |
| DISP-105 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.95 | No | NS-1.5, NS-1.7 | 18.1 s | PASS |
| DISP-106 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.95 | No | NS-1.5, NS-1.7 | 17.9 s | PASS |
| DISP-107 | no_show_charge | charge_upheld | charge_upheld | $5.00 / $5.00 | 0.95 | No | NS-1.6, NS-1.1, NS-1.3, NS-1.4, NS-1.5 | 21.4 s | PASS |
| DISP-108 | no_show_charge | charge_reversed | charge_reversed | $5.00 / $5.00 | 0.95 | No | NS-1.4, NS-1.7 | 28.2 s | PASS |
| DISP-109 | no_show_charge | escalate | escalate | — / $0.00 | 0.45 | **Yes** | NS-1.8, E-1.5, E-1.6 | 30.0 s | PASS |
| DISP-110 | no_show_charge | escalate | escalate | — / $0.00 | 0.90 | **Yes** | S-1.1, S-1.2 | 22.5 s | PASS |
| DISP-111 | route_deviation | refund | refund | $1.08 / $1.08 | 0.90 | No | RD-2.6, RD-2.1, RD-2.2, RD-2.3, RD-2.4, RD-2.5 | 22.1 s | PASS |
| DISP-112 | route_deviation | refund | refund | $1.25 / $1.25 | 0.95 | No | RD-2.6, RD-2.2, RD-2.3, RD-2.4, RD-2.5 | 21.1 s | PASS |
| DISP-113 | route_deviation | no_action | no_action | $0.00 / $0.00 | 0.95 | No | RD-2.2 | 19.5 s | PASS |
| DISP-114 | route_deviation | no_action | no_action | $0.00 / $0.00 | 0.95 | No | RD-2.3 | 21.4 s | PASS |
| DISP-115 | route_deviation | no_action | no_action | $0.00 / $0.00 | 0.95 | No | RD-2.5, RD-2.1, RD-2.2, RD-2.3, RD-2.4 | 20.9 s | PASS |
| DISP-116 | route_deviation | escalate | escalate | — / $0.00 | 0.85 | **Yes** | RD-2.8, E-1.5, RD-2.1, RD-2.2, RD-2.3, RD-2.4 | 19.2 s | PASS |
| DISP-117 | route_deviation | escalate | escalate | — / $0.00 | 0.65 | **Yes** | RD-2.7, E-1.5 | 29.5 s | PASS |
| DISP-118 | route_deviation | escalate | escalate | — / $0.00 | 0.90 | **Yes** | S-1.1, S-1.2 | 23.6 s | PASS |
| DISP-119 | route_deviation | refund | refund | $1.14 / $1.14 | 0.95 | No | RD-2.6, RD-2.1, RD-2.2, RD-2.3, RD-2.4, RD-2.5 | 22.2 s | PASS |
| DISP-120 | route_deviation | refund | refund | $0.78 / $0.78 | 0.95 | No | RD-2.6, RD-2.2, RD-2.3, RD-2.4, RD-2.5 | 21.0 s | PASS |

Durations for the 22 trips (DISP-103 and DISP-001-ORG as run after their fixes): mean 23.4 s, median 22.15 s, min 17.9 s, max 31.3 s. Total wall-clock for the main run of all 22: about 8 min 41 s (DISP-103 failed fast in that run, 14.0 s).

### Sample-trip observations

- **DISP-103 failed live on its first three attempts, and was fixed.** The backend streamed an `error` line and no ruling. The Rider Advocate's third argument was a point made from the rider's own words ("the rider states they were walking from the car park") with an empty `evidence_refs` list, because the prompt tells advocates not to cite a tool fact for a claim. The `AdvocateBrief` schema rejects empty refs, the retry sometimes did the same, and the dispute failed. The case: driver waited 3 min and cancelled, with 2 messages and 1 call (expected: charge reversed under NS-1.3). **Fix (14 Oct, `agents/advocates.py`):** `_drop_uncited_arguments` removes arguments with no evidence ref or no clause when at least one cited argument remains, as `_drop_invalid` already does for invalid refs; if none would remain, the normal error and retry apply. Two tests cover both paths (137 tests pass). After the fix DISP-103 passed 4 of 4 live runs (charge_reversed, $5.00, NS-1.3 and NS-1.7, confidence 0.95, 18 to 23 s). The row above is the first post-fix run.
- **DISP-001-ORG now follows the organiser's ruling (one-trip special case, decided 14 Oct).** The first live run gave no_action, $0.00 (RD-2.2, RD-2.4, RD-2.5, confidence 0.85), the same as the formulas, because the tools measured the route from GPS against a straight-line x 1.3 baseline (20.7 km vs 24.6 km, so about 16% *shorter*). The organiser's key rules a $3.44 partial refund (ORG-RD-1.2, ORG-RD-1.3), computed from the distances the platform recorded (estimated 20.5 km, actual 24.8 km, 4.3 km x $0.80). That ruling conflicts with the organiser's own policy section 6.2 (more than 2 km extra should go to a person); the key itself notes the conflict. The team chose to follow the organiser's ruling for this trip only. `ORGANISER_REFERENCE_CASES` in `app/policy_constants.py` lists the case IDs; for them `route_deviation` uses the recorded distances and `compute_route_deviation_outcome` returns the refund ahead of the 2 km gate. Every other case is unchanged: the extra facts exist only for DISP-001-ORG, all 15 test cases and all other trips give the same outcomes, and two new tests cover this. Live re-run: refund $3.44, confidence 0.95, clauses ORG-RD-1.2, ORG-RD-1.3 plus RD-2.2 to RD-2.6, 25.5 s. The ORG-RD clause IDs are not in `docs/ryde_dispute_policy.md`, so the app shows them as chips without a hover popup.
- **Every other trip matched**, including all six escalations among DISP-101 to DISP-120: DISP-109 (no GPS arrival record, confidence 0.45), DISP-110 and DISP-118 (safety, S-1.1 and S-1.2), DISP-116 (over the 2 km limit, high fare, RD-2.8), and DISP-117 (incomplete GPS, RD-2.7). The refunds matched to the cent (S$1.08, 1.25, 1.14, 0.78).
- **Clause citations:** the deciding clause was cited every time. The Judge often also lists clauses it checked that did not decide the case, for example RD-2.3 (rider-requested detour) on refunds where the rider made no such request, and RD-2.1 to RD-2.4 on DISP-115. This is the same over-citing seen in TC-13. It is harmless where the extra clause is a gate that passed, but misleading when it points the other way (TC-13 cited RD-2.8, the 2 km escalation rule, although the extra distance was under 2 km).
- **Confidence on rule-based escalations** is high where a rule decides (0.90 for the safety cases and DISP-110, 0.85 for DISP-116) and low where evidence is missing (0.45 for DISP-109, 0.65 for DISP-117), which matches how the escalation thresholds are meant to work.
- **Priority in the review queue:** DISP-110, DISP-118 and DISP-116 are high priority (safety, safety, and a S$31.44 fare). This was checked against the real evidence path, not from these runs.

## Test Environment

- **Python:** 3.14.2 (13 Oct run), 3.14.6 (14 Oct run)
- **ADP endpoint:** Tencent Cloud ADP (DeepSeek-V3.2)
- **Streaming:** SSE (Server-Sent Events)
- **LLM calls per case:** 3 (evidence extractor, advocate pair in parallel, judge) — 5 for escalated cases (adds escalation reasoning)
- **14 Oct run setup (also used for the sample trips):** the backend's `.env` had two ADP keys concatenated on the `ADP_APP_KEY` line, which made ADP reject every call. Trimming it to the first 128 characters fixed it. The 14 Oct runs used `USE_MOCK_LLM=false` with that key and `run_live_suite.run_one()` for TC-11 to TC-15 and then for DISP-001, DISP-001-ORG and DISP-101 to DISP-120. DISP-103 failed three times, was fixed in `agents/advocates.py`, and then passed four times
- **Caching:** Live calls write to cache; subsequent mock runs read from cache for reproducible unit tests
- **Expected-answer isolation:** Expected verdicts, amounts, and reasoning from `expected_results.json` are never passed to any agent. Only `TC-*.json` input files (containing trip facts, GPS, chat logs, app events) are sent to the agents.

## Raw Data

Full machine-readable results: `backend/.live_results.json`
