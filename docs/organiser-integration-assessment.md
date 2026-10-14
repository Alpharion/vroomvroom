# Organiser Integration Assessment

**Date:** 2026-10-13
**Author:** CodeBuddy (for Marcus)
**Branch:** `feature/organiser-integration` (from `origin/main` @ `cb0b53d`)
**Status:** AWAITING DECISION GATE A — do not edit active policy or calculation code until answered.
**Documents:** Received and copied to `incoming/` on 2026-10-13. Assessment below verified against actual document content.

---

## 1. Documents Received

1. `incoming/Document 1 — Fare Dispute Sample Data (JSON).md` — DISP-003 fare dispute case (S$12 quote, S$16.50 charged, unnotified surge, expected S$4.50 refund).
2. `incoming/Document 2 — Ryde Dispute Resolution Policy v2.1 (Markdown).md` — organiser policy with different thresholds, refund matrix, and 3 precedent rulings.
3. `incoming/RydeResolve Route Deviation Dataset — DISP-001.md` — organiser route-deviation case (Orchard Central → Changi T3, 4.3 km excess, expected S$3.44 partial refund).

---

## 2. Existing Repo State (Baseline)

| Item | Value |
|---|---|
| Branch | `feature/organiser-integration` from `origin/main` |
| Base commit | `cb0b53dad910b925fec7de37f86a2d887a1f9f2d` |
| Python | 3.14.2 |
| Pytest | 117 passed (all mocked LLM — `USE_MOCK_LLM=true` forced in `conftest.py`) |
| ADP_APP_KEY | Present in `.env` (not printed) |
| Dispute types supported | `no_show_charge`, `route_deviation` |
| DISP-001 (repo) | Tiong Bahru Plaza → VivoCity, metered fare, expected refund S$1.07 |
| DISP-002 (repo) | No-show charge, expected charge_upheld S$5.00 |
| TC-01 through TC-11 | 11 test cases covering no-show, route deviation, safety, fairness, edge cases |
| Policy doc | `docs/ryde_dispute_policy.md` v1.0 (Marcus's draft) |

---

## 3. Conflict Matrix

### 3.1 DISP-001 Identity Conflict

| Aspect | Repo DISP-001 | Organiser DISP-001 |
|---|---|---|
| Route | Tiong Bahru Plaza → VivoCity | Orchard Central → Changi T3 |
| Expected refund | S$1.07 | S$3.44 |
| Fare type | Metered (RydeTAXI) | Standard/fixed (upfront quote S$28.50, actual S$35.00) |
| Fare structure | Flat (`fare_type`, `actual_fare_sgd`, `per_km_rate_sgd`) | Nested (`estimated.total`, `actual.total`, `delta.total`, `excess_distance_fare`) |
| GPS status field | `status` (trip_started, in_trip, trip_completed) | No `status` field — uses `point` and `location_desc` |
| Chat field | `content` | `message` (different key name) |
| Extra fields | `data_label` | `case_metadata`, `evidence_summary`, `recommended_ruling`, `traffic_conditions`, `traffic_analysis`, `chat_log_analysis`, `optimal_route` |

**Risk:** Overwriting or conflating the two would destroy the existing test fixture (TC-05 depends on the repo's DISP-001 data for its S$1.07 refund calculation) and break 5+ unit tests.

**Recommendation:** Add the organiser case under a unique ID (`DISP-001-ORG`) and filename. Never overwrite `data/DISP-001.json` or `data/DISP-001.expected.json`.

### 3.2 DISP-003 Fare Dispute (New Type)

| Aspect | Value |
|---|---|
| Dispute type | `fare_dispute` (not currently supported) |
| Quoted fare | S$12.00 |
| Charged fare | S$16.50 |
| Issue | Unnotified surge |
| Expected refund | S$4.50 |

**Backend compatibility gaps:**
- `DisputeType` in `schemas/models.py` is `Literal["no_show_charge", "route_deviation"]` — `fare_dispute` would fail Pydantic validation.
- `gather_evidence()` in `agents/context.py` only routes to `no_show_check` or `route_deviation` — no fare-dispute evidence tool or outcome formula exists.
- `relevant_clauses()` only handles `NS-*` and `RD-*` prefixes — no `FD-*` clauses.
- `frontend/cases.py` reads any `*.json` from `data/`, so the file would appear in the UI, but the backend would 404/422 on resolution.
- No `compute_fare_dispute_outcome()` function exists.

**Recommendation:** Do NOT add `fare_dispute` as a supported type unless explicitly approved. Keep DISP-003 as a reference/test fixture only. Fare dispute is a stretch goal, not part of the stable MVP.

### 3.3 Policy Threshold Conflicts

| Rule | Existing Policy (v1.0) | Organiser Policy (v2.1, per brief) |
|---|---|---|
| **No-show wait** | 5-min free wait + 8-min no-show threshold (2-stage, from DISP-002 dataset) | 5-min free wait, then cancel (single threshold; §2.1) |
| **Contact attempts** | Minimum 2 (PROPOSED, `MINIMUM_CONTACT_ATTEMPTS=2`) | At least 1 in-app message AND 1 phone call (§2.3) |
| **Route deviation** | 20% threshold → review; fixed fare = no refund; metered = refund excess | 1 km tolerance, >1 km unnotified = partial refund, no traffic evidence = full refund; >2 km + confidence <80% = escalate (§1.3, §6.2) |
| **Escalation** | Confidence < 0.70 (PROPOSED, `SPOT_CHECK_THRESHOLD=0.70`) | <$10 final; $10-$50 need 80%+ confidence; >$50 human review; fraud flag ≥1 → 95% (§6.1, §6.3) |
| **Confidence auto-ruling** | ≥ 0.85 auto, 0.70–0.84 spot-check, < 0.70 escalate | No separate auto-ruling threshold — 80% is the only gate for $10-$50 |

**Impact of changing thresholds:**
- Changing `FREE_WAIT_TIME_MIN`, `NO_SHOW_THRESHOLD_MIN`, or `MINIMUM_CONTACT_ATTEMPTS` in `policy_constants.py` would break TC-01 through TC-04 and TC-09/TC-10 (11 tests depend on current values).
- Changing `DEVIATION_REVIEW_THRESHOLD_PCT` or the route deviation logic would break TC-05 through TC-07 and TC-11.
- Changing `SPOT_CHECK_THRESHOLD` or `AUTO_RULING_THRESHOLD` would break the confidence-gated escalation tests.

### 3.4 Organiser DISP-001 Internal Conflict (VERIFIED)

The organiser DISP-001 dataset expects an automatic S$3.44 partial refund. However, the organiser policy v2.1 §6.2 states: "Route deviation: AI agent ruling if confidence ≥ 80% **and deviation ≤ 2km**, else escalate." The deviation is 4.3 km, which exceeds the 2 km boundary. Per the organiser's own policy, this case should be **escalated to human review**, not auto-resolved with a S$3.44 refund.

The dataset's `recommended_ruling` justifies the partial refund because traffic was justified (PIE vehicle fire) but notification failed (§1.2). The refund is for the excess distance fare only (S$3.44), not the full excess (S$6.50). This is a **genuine policy ambiguity** that requires a human decision.

**Numerical integrity check (VERIFIED):**
- `excess_distance_fare_refunded`: 3.44
- `excess_toll_fare`: 2.22
- `excess_time_fare`: 0.33
- `excess_surge_amount`: 0.51
- Sum: 3.44 + 2.22 + 0.33 + 0.51 = 6.50 ✓ (matches `fare_breakdown.delta.total`)
- The S$3.44 refund = `excess_distance_fare` from `fare_breakdown`, computed at S$0.80/km × 4.3 km = S$3.44 ✓
- The fare breakdown states: "distance fare is calculated at $0.80/km" — this differs from the repo's `per_km_rate_sgd` of S$0.70 in DISP-001.

### 3.5 Schema Incompatibilities (VERIFIED)

The organiser datasets use **different field names and structures** from the repo's Pydantic models. A field transform is required before they can be loaded by the backend.

| Field | Repo schema | Organiser DISP-001-ORG | Organiser DISP-003 |
|---|---|---|---|
| GPS `status` | Required (`trip_started`, `in_trip`, `trip_completed`, etc.) | Not present — uses `location_desc` | Not present — no status field |
| GPS extra fields | `timestamp`, `lat`, `lng`, `speed_kmh`, `status` | Has `point` and `location_desc` | Has only `timestamp`, `lat`, `lng`, `speed_kmh` |
| Chat `content` | `content` (required) | `message` (different key) | `message` (different key) |
| Chat extra | `timestamp`, `sender`, `type` | Has `message_id`, `sender_name` | Has `message_id` |
| `fare_breakdown` | Flat dict with `fare_type`, `actual_fare_sgd`, `per_km_rate_sgd` | Nested `estimated`/`actual`/`delta` dicts with `excess_distance_fare` | Nested `upfront_quote`/`actual_fare`/`comparison` dicts |
| `trip_data` | Has `scheduled_time`, `driver_arrival_time`, `cancellation_time`, etc. | Has `start_time`, `end_time`, `estimated_duration_min`, `actual_distance_km`, `estimated_fare`, `actual_fare` | Has `start_time`, `end_time`, `upfront_quote`, `actual_fare`, `fare_difference` |
| `dispute_type` | `no_show_charge` or `route_deviation` | `route_deviation` ✓ | `fare_dispute` ✗ (not in `DisputeType` Literal) |
| `cancellation_policy` | `CancellationPolicy` model (optional) | Not present | Not present |
| `rider_profile.dispute_history` | Has `upheld`, `rejected` | Has `upheld`, `rejected`, `last_dispute_date` | Has `upheld`, `rejected` |
| `driver_profile` | Has `service_type` | Has `vehicle_color`, `license_class`, `partner_since`, `completion_rate`, `cancellation_rate` | Has no extras |

**Transform strategy for DISP-001-ORG:**
- Rename `message` → `content` in chat_logs.
- Add `status` field to GPS points (infer from `location_desc` or position in array: first=trip_started, last=trip_completed, middle=in_trip).
- Flatten `fare_breakdown` to repo-compatible shape (`fare_type: "fixed"`, `actual_fare_sgd`, `per_km_rate_sgd`).
- Map `start_time` → `scheduled_time`, add `driver_arrival_time` = `start_time` (no separate arrival data).
- Strip `case_metadata`, `evidence_summary`, `recommended_ruling`, `traffic_conditions`, `traffic_analysis`, `chat_log_analysis`, `optimal_route` from agent input.

**Transform strategy for DISP-003:**
- Cannot be loaded as a `DisputeCase` because `dispute_type: "fare_dispute"` fails Pydantic validation.
- Store as reference fixture only unless `fare_dispute` is added to the `DisputeType` Literal.
- Same field renames needed (chat `message` → `content`, GPS `status` inference, fare breakdown flattening).

---

## 4. Affected Files

| File | Impact |
|---|---|
| `data/DISP-001.json` | **Do not modify** — existing test fixture |
| `data/DISP-001.expected.json` | **Do not modify** — existing test fixture |
| `data/DISP-001-ORG.json` | **New** — organiser route case (agent input) |
| `data/DISP-001-ORG.expected.json` | **New** — organiser route case (test fixture) |
| `data/DISP-003.json` | **New** — fare dispute case (reference fixture only, unless approved) |
| `data/DISP-003.expected.json` | **New** — fare dispute expected (test fixture) |
| `docs/organiser_policy_v2.1.md` | **New** — verbatim organiser policy |
| `docs/policy_sources.md` | **Modify** — add organiser source classification |
| `backend/schemas/models.py` | **Modify only if fare_dispute approved** — add `fare_dispute` to `DisputeType` |
| `backend/app/policy_constants.py` | **Modify only if policy decision** — change thresholds |
| `backend/agents/context.py` | **Modify only if policy decision** — add `FD-*` clause routing |
| `backend/tools/` | **New tool only if fare_dispute approved** — `fare_dispute_check.py` |
| `backend/app/main.py` | **Modify** — case index will auto-pick up new files |
| `frontend/cases.py` | **Modify** — case list will auto-pick up new files |
| `docs/organiser-integration-assessment.md` | **This file** |

---

## 5. Implementation Effort Estimate

| Task | Effort | Risk |
|---|---|---|
| Import organiser policy v2.1 verbatim | Low | None — documentation only |
| Add DISP-001-ORG as reference fixture | Low — parse JSON, create input + expected files | Low — must verify field compatibility with Pydantic |
| Add DISP-003 as reference fixture | Low — parse JSON, create input + expected files | Low — marked as unsupported |
| Update `policy_sources.md` | Low | None |
| Add `fare_dispute` as supported type | High — new schema, evidence tool, outcome formula, Judge findings, tests | High — could destabilise MVP |
| Reconcile policy thresholds | High — changes constants, breaks tests, needs re-verification | High — could break 11+ existing tests |
| Live integration tests (Phase 5) | Medium — run scripts, collect data | Medium — depends on ADP availability |

---

## 6. Decision Questions (DECISION GATE A)

**The following must be answered by Marcus and Damien before any code changes:**

1. **Which policy is authoritative for the live demo?**
   - Option A: Keep existing v1.0 policy (HACKATHON_2026 profile). Organiser v2.1 is reference only.
   - Option B: Switch to organiser v2.1 policy. Requires updating all constants, tests, and potentially refund formulas.
   - Option C: Run both side-by-side with a profile switch (like the existing `HACKATHON_2026` / `RYDE_PUBLIC_REFERENCE` pattern).

2. **Should organiser DISP-001 (Orchard Central → Changi T3) be auto-refunded S$3.44 or escalated at >2 km per the organiser policy's own rule?**
   - The brief explicitly notes this conflict. We need a ruling on which rule takes precedence.
   - **Decision (14 Oct):** follow the organiser's ruling for this one trip (auto-refund S$3.44); the 2 km escalation rule stays in force for every other case. Implemented as `ORGANISER_REFERENCE_CASES` in `backend/app/policy_constants.py`.

3. **Is fare dispute (`fare_dispute`) a stretch goal or a supported third type?**
   - If stretch goal: DISP-003 is stored as a reference fixture only, no backend support.
   - If supported: requires new schema, evidence tool, outcome formula, Judge findings, tests — significant work with regression risk.

4. **What are the final no-show rules?**
   - 5-min free wait + 8-min threshold (existing) vs 5-minute cancellation (organiser)?
   - Minimum 2 contact attempts (existing) vs one message AND one call (organiser)?

5. **What are the final route-deviation rules?**
   - 20% deviation threshold (existing) vs 1 km refund matrix + 2 km human-review boundary (organiser)?

6. **What are the final escalation/confidence thresholds?**
   - < 0.70 confidence (existing) vs monetary/category 80% and fraud-related 95% (organiser)?

7. **Should the organiser route case (DISP-001-ORG) be runnable in the live demo, or reference-only?**
   - If runnable: needs to pass through the full pipeline (evidence tools → advocates → Judge).
   - If reference-only: stored as a documented fixture, not in the case index.

---

## 7. Recommendation

**Priority order (from the execution brief):** Stable existing two-type MVP > live correctness > policy consistency > submission evidence > optional fare-dispute feature.

1. **Do NOT change active policy thresholds or calculation code** until Decision Gate A is answered.
2. **Import organiser documents as reference material** — `docs/organiser_policy_v2.1.md` verbatim, new case files under unique IDs with separate `.expected.json` files.
3. **Mark DISP-003 as unsupported** unless fare_dispute is explicitly approved.
4. **Proceed to Phase 5 (live integration tests)** with the existing 11 test cases against real ADP, since this does not depend on the organiser materials.
5. **Only implement fare_dispute or threshold changes after MVP is proven stable live.**

---

*This assessment will be updated once the organiser documents are provided and Decision Gate A is answered.*
