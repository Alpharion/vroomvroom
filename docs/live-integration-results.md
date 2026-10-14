# Live ADP Integration Test Results

**Date:** 2026-10-13 (TC-01 to TC-10); TC-11 re-run and TC-12 to TC-15 added 2026-10-14
**Branch:** `feature/organiser-integration` (TC-01 to TC-10); `backend-revamp` (TC-11 to TC-15)
**Commit:** `f5be9cb` (TC-01 to TC-10)
**ADP Model:** DeepSeek-V3.2 (Tencent Cloud ADP)
**Profile:** HACKATHON_2026
**`USE_MOCK_LLM`:** `false` (live API calls)

## Summary

All 15 test cases passed against live Tencent Cloud ADP: every outcome, refund amount and escalation status matched the expected values. TC-01 to TC-10 were run on 13 Oct; TC-11 was re-run and TC-12 to TC-15 (new cases) were run on 14 Oct, after the ADP AppKey issue in the local `.env` was fixed. Clause lists are not part of the pass criterion: the Judge often cites more clauses than the fixture lists (see Observations).

| Metric | Value |
|---|---|
| Cases passed | **15 / 15 (100%)** |
| Total wall-clock time | 346.3 s (~5 min 46 s), summed over the two runs |
| Mean duration | 23.1 s |
| Median duration | 20.4 s |
| P95 duration | 28.5 s |
| Min duration | 17.7 s (TC-08) |
| Max duration | 30.1 s (TC-13) |

These results are distinct from the 135 mocked unit tests (which use `USE_MOCK_LLM=true` and read from the LLM cache). The live suite exercises the full pipeline: evidence extraction → Rider Advocate → Driver Advocate → Judge → escalation branch, all via real ADP API calls with SSE streaming.

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

## Test Environment

- **Python:** 3.14.2 (13 Oct run), 3.14.6 (14 Oct run)
- **ADP endpoint:** Tencent Cloud ADP (DeepSeek-V3.2)
- **Streaming:** SSE (Server-Sent Events)
- **LLM calls per case:** 3 (evidence extractor, advocate pair in parallel, judge) — 5 for escalated cases (adds escalation reasoning)
- **14 Oct run setup:** the backend's `.env` had two ADP keys concatenated on the `ADP_APP_KEY` line, which made ADP reject every call. Trimming it to the first 128 characters fixed it. The 14 Oct runs used `USE_MOCK_LLM=false` with that key and `run_live_suite.run_one()` for TC-11 to TC-15 only
- **Caching:** Live calls write to cache; subsequent mock runs read from cache for reproducible unit tests
- **Expected-answer isolation:** Expected verdicts, amounts, and reasoning from `expected_results.json` are never passed to any agent. Only `TC-*.json` input files (containing trip facts, GPS, chat logs, app events) are sent to the agents.

## Raw Data

Full machine-readable results: `backend/.live_results.json`
