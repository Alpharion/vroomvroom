# Ryde Dispute Resolution Policy

**Project:** RydeResolve — Multi-Agent Autonomous Dispute Resolution System
**Track:** Tencent Cloud AI CAN DO IT Hackathon Singapore 2026, Digital Native Track (Ryde)
**Document owner:** Marcus (Product, Data & Pitch)
**Version:** 1.0 — draft for Damien review
**Date:** 2026-10-08

---

## 0. How to Read This Document

This document defines the rules that the Judge agent applies when ruling on
disputes. It is written so that **Python code can compute every fee, time
interval, distance, and refund amount deterministically**, while the LLM
agents (Rider Advocate, Driver Advocate, Judge) interpret evidence, cite
clause IDs, and explain rulings in plain language.

Every numbered clause below follows this structure:

> **Clause ID — Title**
> - **Rule:** the exact condition and outcome.
> - **Classification:** `OFFICIAL` (verified Ryde policy), `DATASET` (supplied
>   hackathon dataset rule), or `PROPOSED` (our design assumption, not from
>   any verified source).
> - **Evidence required:** what the evidence tools must surface.
> - **Expected outcome:** the ruling the Judge must reach when the rule fires.
> - **Source:** the reference ID from `docs/policy_sources.md`.
> - **Python computation:** the deterministic formula code must implement.

Two **policy profiles** are maintained in parallel:

| Profile | Use for | Basis |
|---|---|---|
| **HACKATHON_2026** | The prototype and all test cases | Rules from the supplied dataset DISP-002 |
| **RYDE_PUBLIC_REFERENCE** | Reference only; documents real Ryde policy | Verified Ryde help articles (see `docs/policy_sources.md`) |

Where the two profiles disagree, the discrepancy is stated explicitly in the
clause and in `docs/policy_sources.md §5`. **The prototype always uses
HACKATHON_2026 values.** RYDE_PUBLIC_REFERENCE is documented so that a
production deployment could switch profiles by changing the constants.

---

## 1. Purpose, Scope and Source Hierarchy

### 1.1 Purpose

This policy governs how the RydeResolve multi-agent system resolves disputes
between riders and driver-partners on the Ryde ride-hailing platform. It
covers the two dispute types in scope for the hackathon prototype:

1. **No-Show Charge** (`no_show_charge`) — a rider disputes a cancellation
   fee charged after the driver reported them as a no-show.
2. **Route Deviation** (`route_deviation`) — a rider disputes the fare or
   route taken, alleging the driver deviated from a reasonable route.

### 1.2 Scope

| In scope | Out of scope (for hackathon) |
|---|---|
| No-show charge disputes | Damage claims |
| Route deviation disputes | Lost-and-found |
| Safety escalation triage | Payment fraud investigation |
| Refund / compensation calculation | Insurance claims |
| Human-review escalation routing | Criminal prosecution |

### 1.3 Source hierarchy

When sources conflict, the following order applies **within each profile**:

**HACKATHON_2026 profile:**

1. The supplied dataset `DISP-002.json` `cancellation_policy` block and the
   dataset's stated rules (5 min free wait, 8 min no-show threshold, S$5 fee).
2. This policy document's `PROPOSED` rules (for gaps the dataset does not
   cover, e.g. route deviation thresholds).
3. Verified Ryde public policy — used only as a reference cross-check; it does
   **not** override dataset rules in this profile.

**RYDE_PUBLIC_REFERENCE profile:**

1. Verified Ryde help articles (primary official sources).
2. The Ryde Driver-Partner Handbook 2024 (secondary official source).
3. This policy document's `PROPOSED` rules — never override official policy.

`PROPOSED` rules are design assumptions created by Marcus for the
hackathon. They are **not** claims about Ryde's actual policy. Every
`PROPOSED` rule is labelled as such so that no one mistakes it for official
policy.

### 1.4 Core principles

These principles apply to every clause and every ruling:

- **Code computes, LLM explains.** All fees, wait durations, distances, fare
  differences, and refund amounts are calculated by deterministic Python
  functions. The Judge agent never performs arithmetic.
- **Equal treatment of advocates.** Rider Advocate and Driver Advocate
  receive the same tools, the same output schema, and the same length cap.
  The Judge must not favour whoever wrote more.
- **Trip evidence overrides behavioural history.** Ratings, dispute history,
  and fraud flags may provide context but must never override the trip-level
  evidence (GPS, timestamps, chat logs, app events) in determining the
  outcome. See clause E-1.4.
- **No automatic adverse inference from missing data.** If evidence is
  missing, the system must not assume the worst about either party. See
  clause E-1.5.
- **Safety incidents are never auto-resolved.** See Section 5.

---

## 2. No-Show Charge Disputes (NS-1.1 onward)

**Dispute type:** `no_show_charge`
**Typical scenario:** A rider is charged a cancellation fee after the driver
reports them as a no-show. The rider disputes the charge, claiming they were
present at the pickup point or the driver never arrived.

The no-show determination is a **sequential chain** — each clause is a gate.
If an earlier gate fails, the later gates are not reached and the charge is
reversed.

```
NS-1.1  Driver arrived at pickup?
  │ no → NS-1.7 (charge reversed, missing evidence)
  │ yes
  ▼
NS-1.2  Driver arrived by scheduled pickup time?
  │ no (arrived late) → continue to NS-1.3 but flag late arrival
  │ yes
  ▼
NS-1.3  Free waiting period elapsed?
  │ no (cancelled before free wait expired) → NS-1.7 (charge reversed)
  │ yes
  ▼
NS-1.4  No-show threshold reached?
  │ no → NS-1.7 (charge reversed)
  │ yes
  ▼
NS-1.5  Driver attempted contact?
  │ no → NS-1.7 (charge reversed)
  │ yes
  ▼
NS-1.6  Cancellation fee eligible → charge upheld
```

---

### NS-1.1 — Driver GPS Arrival Verification

- **Rule:** The driver must be physically present at the pickup point,
  verified by GPS telemetry showing the vehicle stationary
  (speed = 0 km/h) within the **arrival radius** of the pickup location.
  The arrival radius is the maximum distance from the pickup coordinates
  that still counts as "arrived."

  | Profile | Arrival radius |
  |---|---|
  | HACKATHON_2026 | 10 m (from `app_events.driver_arrived` details: "within 10m") |
  | RYDE_PUBLIC_REFERENCE | Not specified in official sources; 10 m is `PROPOSED` |

- **Classification:** HACKATHON_2026: `DATASET` (inferred from app event
  details). RYDE_PUBLIC_REFERENCE: `PROPOSED` (no official source specifies
  the exact GPS radius).

- **Evidence required:**
  - `gps_telemetry` entries with `status: "arrived"` or `status: "waiting"`.
  - The timestamp and coordinates of the first stationary GPS point.
  - `app_events` entry with `event_type: "driver_arrived"`.
  - Haversine distance from the GPS point to `trip_data.pickup_location`.

- **Expected outcome:**
  - If GPS confirms arrival within radius → proceed to NS-1.2.
  - If GPS shows the driver was **not** within the arrival radius when they
    claimed arrival → the charge is reversed (see NS-1.7).

- **Source:** `SRC-01` (dataset DISP-002), `SRC-06` (app event details).

- **Python computation:**
  ```python
  # haversine(pickup_lat, pickup_lng, gps_lat, gps_lng) returns meters
  driver_distance_from_pickup_m = haversine(
      trip.pickup_location.lat, trip.pickup_location.lng,
      arrived_gps.lat, arrived_gps.lng
  )
  arrived = driver_distance_from_pickup_m <= ARRIVAL_RADIUS_M  # 10
  ```

---

### NS-1.2 — Scheduled Pickup Time Verification

- **Rule:** The driver's verified arrival time is compared to the scheduled
  pickup time. The result is expressed in minutes (negative = early,
  positive = late). This clause is informational — it does not gate the
  chain, but a late arrival is a **flag** that the Judge must weigh.

  If the driver arrived **after** the no-show threshold has already elapsed
  from the scheduled pickup time, the rider cannot be a no-show for the
  pre-arrival period — see NS-1.4 note.

- **Classification:** `PROPOSED` (the comparison logic is our design; neither
  the dataset nor official sources describe how to handle late arrival in a
  dispute context).

- **Evidence required:**
  - `trip_data.scheduled_time`.
  - `trip_data.driver_arrival_time` (or the first `arrived` GPS timestamp).
  - `app_events` entry `driver_arrived`.

- **Expected outcome:**
  - `arrived_minutes_vs_scheduled < 0` → driver arrived early (no driver
    fault).
  - `arrived_minutes_vs_scheduled == 0` → on time.
  - `arrived_minutes_vs_scheduled > 0` → driver arrived late; flag raised.
    If late arrival exceeds the no-show threshold, the charge cannot stand.

- **Source:** `SRC-01` (dataset fields).

- **Python computation:**
  ```python
  arrived_minutes_vs_scheduled = (
      driver_arrival_time - scheduled_time
  ).total_seconds() / 60.0
  ```

---

### NS-1.3 — Free Waiting Period

- **Rule:** After the driver arrives at the pickup point, a free waiting
  period begins. During this period the rider is not charged. If the trip is
  cancelled before the free waiting period expires, no cancellation fee may
  be charged.

  | Profile | Free waiting period |
  |---|---|
  | HACKATHON_2026 | **5 minutes** (from `cancellation_policy.free_wait_time_min`) |
  | RYDE_PUBLIC_REFERENCE | **3 minutes** after driver presses "I'm Here" (from verified help articles) |

- **Classification:** HACKATHON_2026: `DATASET`. RYDE_PUBLIC_REFERENCE:
  `OFFICIAL`.

- **Discrepancy:** The dataset specifies 5 minutes; Ryde's public policy
  specifies 3 minutes. See `docs/policy_sources.md §5`.

- **Evidence required:**
  - `trip_data.driver_wait_start` or the first `waiting` GPS timestamp.
  - `app_events` entry `wait_timer_started`.
  - `app_events` entry `wait_timer_expired` (if it exists).
  - `trip_data.cancellation_time`.

- **Expected outcome:**
  - If `cancellation_time - wait_start < free_wait_time_min` → the driver
    cancelled during the free waiting period → **charge reversed** (NS-1.7).
  - If `cancellation_time - wait_start >= free_wait_time_min` → proceed to
    NS-1.4.

- **Source:** `SRC-01` (dataset), `SRC-02`, `SRC-03` (Ryde help articles).

- **Python computation:**
  ```python
  free_wait_min = 5  # HACKATHON_2026; use 3 for RYDE_PUBLIC_REFERENCE
  total_wait_min = (cancellation_time - wait_start).total_seconds() / 60.0
  free_wait_expired = total_wait_min >= free_wait_min
  ```

---

### NS-1.4 — No-Show Threshold

- **Rule:** After the free waiting period expires, an additional no-show
  window must elapse before the rider is classified as a no-show and the
  cancellation fee becomes chargeable. The **no-show threshold** is the total
  time from wait start that must elapse (free wait + no-show window) before
  a fee can be charged.

  | Profile | No-show threshold (total wait from arrival) |
  |---|---|
  | HACKATHON_2026 | **8 minutes** (from `cancellation_policy.no_show_threshold_min`) |
  | RYDE_PUBLIC_REFERENCE | **3 minutes** after "I'm Here" (the free wait and the no-show window are the same 3-minute period per the public policy; there is no separate extended no-show threshold) |

- **Classification:** HACKATHON_2026: `DATASET`. RYDE_PUBLIC_REFERENCE:
  `OFFICIAL`.

- **Discrepancy:** The dataset has a two-stage model (5 min free wait + 3 min
  additional no-show window = 8 min total). Ryde's public policy has a
  single 3-minute threshold after "I'm Here" is pressed. See
  `docs/policy_sources.md §5`.

- **Evidence required:**
  - `app_events` entry `cancellation_fee_applied` and its timestamp.
  - `trip_data.cancellation_time`.
  - The computed `total_wait_min` from NS-1.3.

- **Expected outcome:**
  - If `total_wait_min >= no_show_threshold_min` → no-show threshold reached
    → proceed to NS-1.5.
  - If `total_wait_min < no_show_threshold_min` → the fee was charged
    prematurely → **charge reversed** (NS-1.7).

- **Source:** `SRC-01` (dataset), `SRC-02`, `SRC-03` (Ryde help articles).

- **Python computation:**
  ```python
  no_show_threshold_min = 8  # HACKATHON_2026; use 3 for RYDE_PUBLIC_REFERENCE
  no_show_reached = total_wait_min >= no_show_threshold_min
  ```

---

### NS-1.5 — Contact Attempts

- **Rule:** The driver must have made a minimum number of contact attempts
  toward the rider before charging a no-show fee. A contact attempt is any
  of: an in-app message, an in-app call, or a push notification triggered by
  the driver.

  | Profile | Minimum contact attempts |
  |---|---|
  | HACKATHON_2026 | **2** (PROPOSED — the dataset shows 5 attempts but does not state a minimum) |
  | RYDE_PUBLIC_REFERENCE | Not specified in official sources; 2 is `PROPOSED` |

- **Classification:** `PROPOSED` for both profiles. Neither the dataset nor
  the official help articles specify a minimum number of contact attempts.
  Marcus proposes 2 as a reasonable minimum (at least one message and one
  call, or two messages).

- **Evidence required:**
  - `chat_logs` entries where `sender == "driver"` and `type` is
    `"message"`, `"call"`, or `"system"` (for driver-initiated push).
  - `app_events` entries `driver_called_rider`.
  - Count of rider replies (`sender == "rider"`).

- **Expected outcome:**
  - If `contact_attempts >= minimum_contact_attempts` → proceed to NS-1.6.
  - If `contact_attempts < minimum_contact_attempts` → the driver did not
    make reasonable efforts to reach the rider → **charge reversed**
    (NS-1.7).

- **Source:** `SRC-01` (dataset — 5 attempts present), `PROPOSED` threshold.

- **Python computation:**
  ```python
  minimum_contact_attempts = 2  # PROPOSED
  contact_attempts = count(
      c for c in chat_logs
      if c.sender == "driver" and c.type in ("message", "call")
  )
  # also count app_events: driver_called_rider
  contact_attempts += count(
      e for e in app_events if e.event_type == "driver_called_rider"
  )
  contact_made = contact_attempts >= minimum_contact_attempts
  ```

---

### NS-1.6 — Cancellation Fee Eligibility (Charge Upheld)

- **Rule:** If NS-1.1 through NS-1.5 all pass (driver arrived, free wait
  expired, no-show threshold reached, contact attempted), the cancellation
  fee is **eligible** and the charge is **upheld**.

  | Profile | Cancellation fee amount | Fee goes to |
  |---|---|---|
  | HACKATHON_2026 | **S$5.00** (from `cancellation_policy.cancellation_fee_after_wait`) | `driver_compensation` |
  | RYDE_PUBLIC_REFERENCE | **S$6.61** (rider-facing, from help article SRC-02) / **S$4.50** (driver-receiving, from help article SRC-03) | Driver compensation |

- **Classification:** HACKATHON_2026: `DATASET`. RYDE_PUBLIC_REFERENCE:
  `OFFICIAL`.

- **Discrepancy:** The dataset fee is S$5.00. Ryde's public articles show
  different figures: the rider-facing article (SRC-02) states S$6.61, while
  the driver-facing article (SRC-03) states S$4.50. The S$6.61 may include
  platform fees and GST. See `docs/policy_sources.md §5`.

- **Evidence required:** All evidence from NS-1.1 through NS-1.5, plus
  `trip_data.cancellation_fee`.

- **Expected outcome:**
  - Outcome: `charge_upheld`.
  - `amount_sgd`: the cancellation fee amount (S$5.00 in HACKATHON_2026).
  - The Judge must explain that the driver followed the correct process:
    arrived, waited the required period, attempted contact.

- **Source:** `SRC-01` (dataset), `SRC-02`, `SRC-03` (Ryde help articles).

- **Python computation:**
  ```python
  cancellation_fee = 5.00  # HACKATHON_2026; use 6.61 or 4.50 for RYDE_PUBLIC_REFERENCE
  if arrived and free_wait_expired and no_show_reached and contact_made:
      outcome = "charge_upheld"
      amount_sgd = cancellation_fee
  ```

---

### NS-1.7 — Charge Reversed (Refund Conditions)

- **Rule:** If any of NS-1.1, NS-1.3, NS-1.4, or NS-1.5 fails, the
  cancellation fee is **reversed** and the rider is refunded the full
  cancellation fee amount. The refund is always the full fee — there is no
  partial refund for no-show charges.

  Specific failure conditions and their outcomes:

  | Failed clause | Reason | Outcome |
  |---|---|---|
  | NS-1.1 | Driver not at pickup (GPS > arrival radius) | `charge_reversed`, full refund |
  | NS-1.3 | Cancelled before free wait expired | `charge_reversed`, full refund |
  | NS-1.4 | Fee charged before no-show threshold | `charge_reversed`, full refund |
  | NS-1.5 | Insufficient contact attempts | `charge_reversed`, full refund |

- **Classification:** `PROPOSED` (the full-refund policy is our design;
  official sources do not describe partial refunds for no-show charges).

- **Evidence required:** The specific evidence that failed the gate.

- **Expected outcome:**
  - Outcome: `charge_reversed`.
  - `amount_sgd`: the cancellation fee amount (refunded).
  - The Judge must explain which gate failed and why.

- **Source:** `PROPOSED`.

- **Python computation:**
  ```python
  if not (arrived and free_wait_expired and no_show_reached and contact_made):
      outcome = "charge_reversed"
      amount_sgd = cancellation_fee  # refunded
  ```

---

### NS-1.8 — Missing Evidence Handling

- **Rule:** If critical evidence is missing or contradictory (e.g., no GPS
  telemetry, no `driver_arrived` app event, GPS data gap during the waiting
  period), the system cannot verify the no-show chain. In this case:
  - The ruling is **not** automatically in favour of either party.
  - The Judge must set a **low confidence score** (below the escalation
    threshold) and **escalate to human review**.
  - No adverse inference is drawn from the missing data (see E-1.5).

- **Classification:** `PROPOSED`.

- **Evidence required:** The absence of evidence that should exist (e.g., no
  GPS points between `wait_start` and `cancellation_time`).

- **Expected outcome:**
  - Outcome: `escalate`.
  - `amount_sgd`: 0.00 (no action pending human review).
  - `confidence`: below escalation threshold (e.g., < 0.70).
  - `escalated`: true.
  - `escalation_reason`: "missing evidence: [specific gap]".

- **Source:** `PROPOSED`.

- **Python computation:**
  ```python
  critical_fields = [
      "gps_telemetry",           # must have arrived/waiting points
      "driver_arrival_time",     # or derivable from GPS
      "cancellation_time",
      "chat_logs",               # must exist (even if empty list is ok,
                                 # absence of the key is a problem)
  ]
  missing = [f for f in critical_fields if not get(trip, f)]
  if missing:
      outcome = "escalate"
      confidence = 0.50  # below escalation threshold
      escalated = True
      escalation_reason = f"missing evidence: {missing}"
  ```

---

## 3. Route Deviation Disputes (RD-2.1 onward)

**Dispute type:** `route_deviation`
**Typical scenario:** A rider alleges the driver took a longer or
unreasonable route, resulting in a higher fare or longer trip time.

### Critical context: Ryde uses fixed fares

Per verified Ryde policy (SRC-04): *"The trip fare is fixed based on
pick-up and drop-off points. So you may decide to take the fastest or most
efficient route based on your GPS."*

This means:

- **A route deviation does NOT automatically create a monetary refund.**
  Because fares are fixed on pickup/dropoff, a longer route does not
  necessarily increase the fare.
- Route deviation review is about **driver conduct and trip quality**, not
  automatic fare adjustment.
- A **monetary refund** only arises if the fare was **not** fixed (e.g.,
  RydeTAXI metered fare, surge-adjusted fare, or a fare that included
  distance/time components that were inflated by the deviation).

The clauses below distinguish a **deviation review trigger** (which may
warrant a conduct flag or partial refund in specific cases) from a
**monetary refund entitlement** (which requires verified excess charges).

---

### RD-2.1 — Actual vs. Reasonable Baseline Route

- **Rule:** The actual route taken (from GPS telemetry) is compared to a
  **reasonable baseline route** — the shortest or fastest route between
  pickup and dropoff as computed by a routing service (or a straight-line
  Haversine baseline as a fallback for the hackathon).

  The deviation is expressed as a percentage:
  `deviation_pct = (actual_distance_km - baseline_distance_km) / baseline_distance_km * 100`

  | Profile | Baseline route method |
  |---|---|
  | HACKATHON_2026 | Haversine straight-line distance × 1.3 road-network factor (PROPOSED) |
  | RYDE_PUBLIC_REFERENCE | Routing service shortest/fastest route (PROPOSED — official sources do not specify the baseline method) |

- **Classification:** `PROPOSED` for both profiles. No official source
  describes how Ryde measures route deviation internally.

- **Evidence required:**
  - `gps_telemetry` for the trip (en-route and in-trip points).
  - `trip_data.pickup_location` and `trip_data.dropoff_location`.
  - Computed `actual_distance_km` (sum of GPS segment distances).
  - Computed `baseline_distance_km`.

- **Expected outcome:**
  - Compute `deviation_pct`. This is a **review trigger**, not an automatic
    refund. Proceed to RD-2.2.

- **Source:** `SRC-04` (fixed fare context), `PROPOSED` methodology.

- **Python computation:**
  ```python
  # Haversine baseline with road-network factor
  straight_line_km = haversine_km(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
  baseline_distance_km = straight_line_km * 1.3  # PROPOSED road factor
  actual_distance_km = sum_of_gps_segment_distances(gps_telemetry)
  deviation_pct = ((actual_distance_km - baseline_distance_km) / baseline_distance_km) * 100
  ```

---

### RD-2.2 — Deviation Review Threshold (20%)

- **Rule:** A route deviation of **20% or more** above the baseline triggers
  a **mandatory review**. Below 20%, no review is triggered and no refund is
  owed (barring other evidence).

  | Profile | Review threshold |
  |---|---|
  | HACKATHON_2026 | **20%** (PROPOSED) |
  | RYDE_PUBLIC_REFERENCE | Not specified in official sources; 20% is `PROPOSED` |

- **Classification:** `PROPOSED`. This threshold is a design assumption from
  Marcus, based on the team brief's example (`R-3.2: deviation >20%
  without rider request → refund the difference`). It is **not** from any
  verified Ryde source.

- **Evidence required:**
  - `deviation_pct` from RD-2.1.
  - Chat logs to check for rider-requested detours (RD-2.3).

- **Expected outcome:**
  - If `deviation_pct < 20` → no review triggered, outcome `no_action`,
    `amount_sgd = 0.00`.
  - If `deviation_pct >= 20` → proceed to RD-2.3 (check for rider-requested
    detour), RD-2.4 (traffic/road conditions), RD-2.5 (fare validation).

- **Source:** `PROPOSED` (team brief example, not official policy).

- **Python computation:**
  ```python
  DEVIATION_REVIEW_THRESHOLD_PCT = 20.0  # PROPOSED
  review_triggered = deviation_pct >= DEVIATION_REVIEW_THRESHOLD_PCT
  if not review_triggered:
      outcome = "no_action"
      amount_sgd = 0.00
  ```

---

### RD-2.3 — Rider-Requested Detours

- **Rule:** If the rider requested or agreed to the detour (evidenced by
  chat logs or app events), the deviation is **justified** and no refund is
  owed, regardless of the deviation percentage.

  A rider-requested detour is detected by:
  - Chat messages from the rider containing route instructions (e.g.,
    "can you go via XYZ road", "take the highway").
  - App events showing a rider-initiated stop addition or route change.
  - Rider agreement to a driver-proposed alternative route ("sure, go
    ahead").

- **Classification:** `PROPOSED` (the detection logic is our design; SRC-04
  confirms the driver may take the rider's suggested route but does not
  describe dispute handling).

- **Evidence required:**
  - `chat_logs` with rider messages containing route-related content.
  - `app_events` with stop additions or route changes.
  - The LLM agents interpret whether a message constitutes a detour request
    or agreement. The keyword filter (`contains_route_content()`) surfaces
    candidates only — it cannot distinguish a request ("please take the
    expressway") from a complaint ("why are you taking this route??"). The
    Judge LLM makes the final intent determination. TC-05 tests this: the
    rider's message "Are we going the right way?" matches the keyword filter
    but is a question, not a route request.

- **Expected outcome:**
  - If a rider-requested detour is evidenced → outcome `no_action`,
    `amount_sgd = 0.00`.
  - The Judge explains that the rider agreed to the route.

- **Source:** `SRC-04` (rider may suggest route), `PROPOSED` dispute logic.

- **Python computation:**
  ```python
  # Code surfaces the relevant chat logs; LLM determines intent.
  rider_route_messages = [
      c for c in chat_logs
      if c.sender == "rider" and contains_route_content(c.content)
  ]
  rider_requested_detour = len(rider_route_messages) > 0
  # The Judge LLM interprets whether these messages constitute a request
  # or agreement. Code does NOT make the final intent determination.
  if rider_requested_detour:
      outcome = "no_action"
      amount_sgd = 0.00
  ```

---

### RD-2.4 — Traffic and Road Conditions

- **Rule:** If the deviation was caused by verifiable traffic conditions,
  road closures, accidents, or other real-world factors, the deviation is
  **excused** and no refund is owed — **provided the fare is fixed** (see
  RD-2.5).

  Evidence of traffic/road conditions may include:
  - GPS telemetry showing slow speeds or stops consistent with traffic.
  - Timestamps showing unusually long trip duration vs. estimate.
  - Chat messages from the driver mentioning traffic ("heavy traffic on
    PIE, taking alternate route").

- **Classification:** `PROPOSED`.

- **Evidence required:**
  - GPS speed data during the trip.
  - Trip duration vs. estimated duration.
  - Driver chat messages about traffic/road conditions.

- **Expected outcome:**
  - If traffic/road conditions are evidenced → the deviation is excused.
    Outcome `no_action`, `amount_sgd = 0.00` (for fixed-fare trips).
  - If no traffic evidence and fare is fixed → the deviation is noted as a
    driver conduct flag, but still no monetary refund (see RD-2.5).

- **Source:** `PROPOSED`.

- **Python computation:**
  ```python
  # Code computes trip duration and average speed; LLM interprets
  # whether the pattern indicates traffic.
  trip_duration_min = (dropoff_time - pickup_time).total_seconds() / 60.0
  avg_speed_kmh = actual_distance_km / (trip_duration_min / 60.0)
  # LLM judges whether slow segments + driver messages indicate traffic
  ```

---

### RD-2.5 — Fare Validation

- **Rule:** Before any monetary refund is calculated, the fare type must be
  determined:

  | Fare type | Deviation refund? |
  |---|---|
  | **Fixed fare** (standard RydeX, RydePOOL, etc.) | **No monetary refund** for route deviation. The fare is fixed on pickup/dropoff. A deviation >20% without rider request or traffic justification results in a **driver conduct flag**, not a refund. |
  | **Metered fare** (RydeTAXI) | **Refund the verified excess** if the deviation is unjustified. |
  | **Surge-adjusted or distance/time-based fare** | **Refund the verified excess** if the deviation is unjustified. |

  For the hackathon prototype, unless the dataset explicitly indicates a
  metered or distance-based fare, **assume fixed fare** and do not compute a
  monetary refund for route deviation.

- **Classification:** `OFFICIAL` (fixed fare per SRC-04) + `PROPOSED` (the
  refund logic for metered/distance fares is our design).

- **Evidence required:**
  - `trip_data.fare_breakdown` or equivalent fare data (TBD with Damien —
    see `schemas.md` note: "Route deviation cases will also need planned
    route + fare breakdown").
  - Service type (RydeX, RydeTAXI, etc.) if available.

- **Expected outcome:**
  - Fixed fare + unjustified deviation >20% → outcome `no_action` (no
    refund), but flag driver conduct for review.
  - Metered/distance fare + unjustified deviation → proceed to RD-2.6 for
    refund calculation.

- **Source:** `SRC-04` (fixed fare), `SRC-07` (RydeTAXI is metered),
  `PROPOSED` refund logic.

- **Python computation:**
  ```python
  fare_type = determine_fare_type(trip_data)  # "fixed" | "metered" | "distance_time"
  if fare_type == "fixed":
      if deviation_pct >= 20 and not rider_requested_detour and not traffic_justified:
          # No monetary refund; flag conduct
          outcome = "no_action"
          amount_sgd = 0.00
          conduct_flag = True
  elif fare_type in ("metered", "distance_time"):
      # Proceed to RD-2.6
      pass
  ```

---

### RD-2.6 — Refund Calculation (Metered/Distance Fares Only)

- **Rule:** For metered or distance/time-based fares where an unjustified
  deviation is confirmed (deviation ≥ 20%, no rider request, no traffic
  justification), the refund is the **verified excess charge**:

  ```
  excess_distance_km = actual_distance_km - baseline_distance_km
  excess_fare_sgd = excess_distance_km * per_km_rate_sgd
  refund_sgd = min(excess_fare_sgd, actual_fare_sgd)  # never exceed the fare
  ```

  The `per_km_rate_sgd` must be extracted from the fare breakdown. If it
  cannot be extracted, escalate (missing evidence).

- **Classification:** `PROPOSED`.

- **Evidence required:**
  - Fare breakdown with distance-based components and per-km rate.
  - `actual_distance_km` and `baseline_distance_km` from RD-2.1.
  - Confirmation from RD-2.3 (no rider request) and RD-2.4 (no traffic
    justification).

- **Expected outcome:**
  - Outcome: `refund`.
  - `amount_sgd`: computed refund.
  - The Judge explains the calculation and cites the deviation percentage.

- **Source:** `PROPOSED`.

- **Python computation:**
  ```python
  if fare_type in ("metered", "distance_time") and \
     deviation_pct >= 20 and not rider_requested_detour and not traffic_justified:
      excess_distance_km = actual_distance_km - baseline_distance_km
      excess_fare_sgd = excess_distance_km * per_km_rate_sgd
      refund_sgd = min(excess_fare_sgd, actual_fare_sgd)
      outcome = "refund"
      amount_sgd = refund_sgd
  ```

### RD-2.7 — Missing Evidence Handling

- **Rule:** If any critical evidence required to evaluate a route-deviation
  dispute is missing or insufficient, the case must be escalated to human
  review. No automatic ruling (for or against either party) may be issued.

  Critical evidence fields for route deviation:
  1. `gps_telemetry` — must have at least 2 in-trip points to compute
     actual distance. If absent or with fewer than 2 in-trip points,
     deviation cannot be computed.
  2. `trip_data.fare_breakdown` — must be present to determine fare type
     (fixed, metered, distance_time). If absent, fare type cannot be
     determined.
  3. `fare_breakdown.per_km_rate_sgd` — must be present when fare type is
     metered or distance_time and RD-2.6 would fire (deviation ≥ 20%, no
     rider request, no traffic justification). If absent, refund cannot be
     computed.

- **Classification:** `PROPOSED` (mirrors NS-1.8 pattern for no-show).

- **Evidence required:**
  - All inputs required by RD-2.1 through RD-2.6, verified for completeness.

- **Expected outcome:**
  - Outcome: `escalate`.
  - `amount_sgd`: 0.00.
  - `cited_policy_clauses`: `["RD-2.7", "E-1.5"]`.
  - `confidence`: < 0.70 (below auto-ruling threshold).
  - `escalated`: true.
  - `escalation_reason`: "missing evidence for route deviation: [fields]".

- **Source:** `PROPOSED`.

- **Python computation:**
  ```python
  missing = []
  if len([p for p in gps_telemetry if p.status == "in_trip"]) < 2:
      missing.append("gps_telemetry")
  if fare_breakdown is None:
      missing.append("fare_breakdown")
  elif fare_type in ("metered", "distance_time") and per_km_rate_sgd is None \
       and deviation_pct >= 20 and not rider_requested_detour \
       and not traffic_justified:
      missing.append("per_km_rate_sgd")
  if missing:
      return ("escalate", 0.00, ["RD-2.7", "E-1.5"], False)
  ```

---

### RD-2.8 — Deviation Exceeding 2km Auto-Rule Boundary

- **Rule:** When the excess distance (actual route distance minus baseline
  route distance) exceeds 2 km, the AI agent may not issue an automatic
  ruling. The case must be escalated to human review regardless of
  confidence level. This implements organiser policy v2.1 §6.2:
  "Route deviation: AI agent ruling if confidence ≥80% AND deviation ≤2km,
  else escalate."

- **Classification:** `OFFICIAL` (organiser policy v2.1 §6.2).

- **Evidence required:**
  - `excess_distance_km` = `actual_distance_km - baseline_distance_km`
    (computed by RD-2.1).

- **Expected outcome:**
  - Outcome: `escalate`.
  - `amount_sgd`: 0.00.
  - `cited_policy_clauses`: `["RD-2.8", "E-1.5"]`.
  - `escalated`: true.
  - `escalation_reason`: "deviation exceeds 2km auto-rule boundary".

- **Source:** `SRC-ORG-1` (organiser policy v2.1 §6.2).

- **Python computation:**
  ```python
  excess_km = actual_distance_km - baseline_distance_km
  if excess_km > DEVIATION_AUTO_RULE_KM:  # 2.0
      return ("escalate", 0.00, ["RD-2.8", "E-1.5"], False)
  ```

---

## 4. Safety Escalation (S-1.1 onward)

Safety clauses apply to **both** dispute types and may be triggered by
evidence in any dispute.

### S-1.1 — Safety Incident Categories

- **Rule:** If any of the following are detected in the dispute evidence,
  the case is classified as a **safety incident** and must be escalated to
  human review. The system must **never** auto-resolve a safety incident.

  Safety incident categories:
  1. **Threats** — explicit or implied threats of violence in chat logs.
  2. **Harassment** — sexual, racial, verbal, or other harassment in chat
     logs or reported by either party.
  3. **Assault** — physical assault alleged or evidenced.
  4. **Dangerous driving** — GPS telemetry showing reckless behaviour
     (excessive speeding, erratic movement) or reported by the rider.
  5. **Discrimination** — comments on race, ethnicity, national origin,
     disability, etc. (per SRC-06 community standards).

- **Classification:** `OFFICIAL` (SRC-06 establishes zero-tolerance for
  these behaviours) + `PROPOSED` (the detection triggers and escalation
  routing are our design).

- **Evidence required:**
  - `chat_logs` content (LLM scans for threats, harassment, discrimination).
  - `gps_telemetry` speed data (code flags speeding above threshold).
  - `dispute_ticket.description` (rider's own report may describe the
    incident).

- **Expected outcome:**
  - Outcome: `escalate`.
  - `amount_sgd`: 0.00 (no financial action; human reviewer decides).
  - `confidence`: not applicable (safety overrides confidence).
  - `escalated`: true.
  - `escalation_reason`: "safety incident: [category]".

- **Source:** `SRC-06` (Driver Performance and Community Standards).

- **Python computation:**
  ```python
  SAFETY_KEYWORDS = [
      "threat", "threaten", "assault", "hit", "attack", "harass",
      "abuse", "racist", "race", "discriminat", "dangerous",
      "reckless", "scared", "afraid", "unsafe", "weapon",
  ]
  SPEEDING_THRESHOLD_KMH = 90  # PROPOSED for Singapore expressways

  def detect_safety_incident(chat_logs, gps_telemetry, description):
      text = " ".join([c.content for c in chat_logs]) + " " + description
      keyword_hit = any(kw in text.lower() for kw in SAFETY_KEYWORDS)
      speeding_hit = any(p.speed_kmh > SPEEDING_THRESHOLD_KMH for p in gps_telemetry)
      return keyword_hit or speeding_hit

  if detect_safety_incident(chat_logs, gps_telemetry, description):
      outcome = "escalate"
      amount_sgd = 0.00
      escalated = True
      escalation_reason = "safety incident detected"
  ```

  **Note:** The keyword list is a first-pass filter. The LLM agents make the
  final semantic determination of whether a message constitutes a threat,
  harassment, etc. Code surfaces candidates; LLM confirms intent.

---

### S-1.2 — Mandatory Human Review

- **Rule:** Any safety incident (S-1.1) or low-confidence ruling (see E-1.6)
  must be routed to the human review queue. The system must:
  - Mark the case as `escalated: true`.
  - Set `escalation_reason` to a specific string.
  - Not issue a binding financial outcome (`amount_sgd = 0.00`).
  - Notify both parties that the case is under human review.

- **Classification:** `OFFICIAL` (SRC-06: "Driver-partners will be given the
  opportunity to respond before final decisions are made, except in urgent
  or high-risk situations") + `PROPOSED` (the routing logic is our design).

- **Evidence required:** The triggering evidence (safety keywords, speeding,
  or low confidence score).

- **Expected outcome:** See S-1.1.

- **Source:** `SRC-06`.

---

## 5. Evidence and Fairness (E-1.1 onward)

### E-1.1 — Evidence Reliability

- **Rule:** Evidence sources are ranked by reliability for the Judge's
  consideration:

  | Tier | Source | Reliability |
  |---|---|---|
  | 1 | `app_events` (system-generated, timestamped) | Highest — system facts |
  | 2 | `gps_telemetry` (device-generated, timestamped) | High — location facts |
  | 3 | `chat_logs` (user-generated, timestamped) | Medium — communications |
  | 4 | `dispute_ticket.description` (party's own account) | Low — self-serving |
  | 5 | `rider_profile` / `driver_profile` (history, ratings) | Contextual — see E-1.4 |

  When evidence conflicts, higher-tier evidence takes precedence. The Judge
  must explain any decision to rely on lower-tier evidence over higher-tier.

- **Classification:** `PROPOSED`.

- **Evidence required:** All available evidence, classified by tier.

- **Expected outcome:** The Judge cites the tier of evidence relied upon.

- **Source:** `PROPOSED`.

---

### E-1.2 — Equal Treatment of Advocates

- **Rule:** The Rider Advocate and Driver Advocate must receive:
  - The same set of evidence tools with the same output format.
  - The same output schema (`advocate_brief` from `schemas.md`).
  - The same length cap on arguments.
  - The same prompt structure (role, instructions, constraints).

  The Judge must not favour the advocate who writes more or argues more
  persuasively at the expense of evidence.

- **Classification:** `OFFICIAL` (design principle from team brief, derived
  from fairness requirements) / `PROPOSED` (the specific implementation).

- **Evidence required:** Advocate briefs from both sides.

- **Expected outcome:** Both briefs are presented to the Judge with
  identical structure.

- **Source:** `docs/team-brief.md §2 Key design rules`, `PROPOSED`.

---

### E-1.3 — Evidence Must Be Cited

- **Rule:** Every argument in an advocate brief must cite:
  - At least one `evidence_refs` pointing to a specific evidence field.
  - At least one `clauses` ID from this policy document.

  The Judge must cite clause IDs in its ruling (`clauses_cited` field).

- **Classification:** `PROPOSED`.

- **Evidence required:** Advocate briefs and ruling output.

- **Expected outcome:** Rulings without clause citations are invalid (schema
  validation rejects them).

- **Source:** `docs/schemas.md §3 Advocate brief`, `docs/schemas.md §4 Ruling`,
  `PROPOSED`.

---

### E-1.4 — Ratings and Histories Must Not Override Trip Evidence

- **Rule:** Rider and driver profiles (ratings, dispute history, fraud
  flags, account age, total trips) provide **context** but must **never**
  override trip-level evidence (GPS, timestamps, chat logs, app events) in
  determining the outcome.

  Specifically:
  - A rider with a poor dispute history or fraud flags may still have a
    legitimate dispute if the trip evidence supports their claim.
  - A driver with an excellent rating and long history may still have
    violated policy if the trip evidence shows it.
  - Profile data may be mentioned in the Judge's explanation as context but
    must not be cited as the **basis** for the outcome.

- **Classification:** `PROPOSED` (the principle is a fairness design choice;
  SRC-06 mentions using AI to detect fraud but does not describe how
  histories are weighed in disputes).

- **Evidence required:** Trip evidence (tiers 1–3) and profile data (tier 5).

- **Expected outcome:** The outcome is determined by trip evidence. Profile
  data is mentioned as context only.

- **Source:** `PROPOSED`, `SRC-06` (fraud detection context).

- **Python computation:**
  ```python
  # Code computes the outcome from trip evidence (NS-1.x / RD-2.x chain).
  # Profile data is passed to the Judge LLM for context in the explanation,
  # but the outcome and amount_sgd are determined by the code path above.
  # The Judge prompt must instruct: "Do not let ratings or dispute history
  # override the trip evidence in determining the outcome."
  ```

---

### E-1.5 — No Automatic Adverse Inference from Missing Data

- **Rule:** If evidence is missing (e.g., GPS gap, no chat logs, missing app
  event), the system must **not** assume the missing evidence favours
  either party. Missing evidence triggers NS-1.8 (no-show) or escalation
  (route deviation), not an automatic ruling against the party whose
  evidence is missing.

- **Classification:** `PROPOSED`.

- **Evidence required:** Identification of the specific missing evidence.

- **Expected outcome:** Escalation to human review (see S-1.2, E-1.6).

- **Source:** `PROPOSED`.

---

### E-1.6 — Confidence and Explanation Requirements

- **Rule:** Every ruling includes a `confidence` score between 0.0 and 1.0.
  The Judge LLM produces the confidence score based on evidence completeness
  and clarity.

  | Confidence | Action |
  |---|---|
  | ≥ 0.85 | Ruling issued automatically |
  | 0.70 – 0.84 | Ruling issued but flagged for spot-check |
  | < 0.70 | Escalated to human review (no auto-ruling) |

  Every ruling must include:
  - `explanation_rider`: plain-language explanation for the rider.
  - `explanation_driver`: plain-language explanation for the driver.
  - `clauses_cited`: list of clause IDs applied.

- **Classification:** `PROPOSED` (thresholds are Marcus's design).

- **Evidence required:** The full evidence set and the Judge's reasoning.

- **Expected outcome:**
  - High confidence → ruling issued.
  - Low confidence → `escalate`, `amount_sgd = 0.00`.

- **Source:** `PROPOSED`, `docs/team-brief.md §2`.

- **Python computation:**
  ```python
  AUTO_RULING_THRESHOLD = 0.85
  SPOT_CHECK_THRESHOLD = 0.70

  if confidence >= AUTO_RULING_THRESHOLD:
      escalated = False
  elif confidence >= SPOT_CHECK_THRESHOLD:
      escalated = False  # but flagged for spot-check
      spot_check = True
  else:
      outcome = "escalate"
      amount_sgd = 0.00
      escalated = True
      escalation_reason = "low confidence"
  ```

---

## 6. Decision Table

### No-Show Charge — Decision Matrix (HACKATHON_2026)

| Driver at pickup? (NS-1.1) | Arrived by scheduled time? (NS-1.2) | Free wait expired? (NS-1.3) | No-show threshold reached? (NS-1.4) | Contact attempted? (NS-1.5) | Missing evidence? (NS-1.8) | Outcome | Amount (S$) |
|---|---|---|---|---|---|---|---|
| Yes | Yes/Early | Yes | Yes | Yes | No | `charge_upheld` | 5.00 |
| Yes | Yes | Yes | Yes | No ( < 2 attempts) | No | `charge_reversed` | 5.00 (refund) |
| Yes | Yes | Yes | No | — | No | `charge_reversed` | 5.00 (refund) |
| Yes | Yes | No | — | — | No | `charge_reversed` | 5.00 (refund) |
| No (GPS > 10m) | — | — | — | — | No | `charge_reversed` | 5.00 (refund) |
| — | — | — | — | — | Yes | `escalate` | 0.00 |

### Route Deviation — Decision Matrix (HACKATHON_2026)

| Deviation ≥ 20%? (RD-2.2) | Rider requested detour? (RD-2.3) | Traffic justified? (RD-2.4) | Fare type (RD-2.5) | Missing evidence? (RD-2.7) | Outcome | Amount (S$) |
|---|---|---|---|---|---|---|
| No | — | — | — | No | `no_action` | 0.00 |
| Yes | Yes | — | — | No | `no_action` | 0.00 |
| Yes | No | Yes | Fixed | No | `no_action` | 0.00 |
| Yes | No | Yes | Metered | No | `no_action` | 0.00 |
| Yes | No | No | Fixed | No | `no_action` + conduct flag | 0.00 |
| Yes | No | No | Metered | No | `refund` | computed excess |
| Yes | No | No | Distance/time | No | `refund` | computed excess |
| — | — | — | — | Yes | `escalate` | 0.00 |

### Safety — Decision Matrix

| Safety incident detected? (S-1.1) | Outcome | Amount (S$) | Escalated |
|---|---|---|---|
| Yes | `escalate` | 0.00 | true |
| No | proceed to dispute-type rules | — | false |

### Confidence — Decision Matrix

| Confidence | Escalated? | Notes |
|---|---|---|
| ≥ 0.85 | false | Auto-ruling issued |
| 0.70 – 0.84 | false | Ruling issued, flagged for spot-check |
| < 0.70 | true | Escalated to human review |

---

## 7. Implementation Handoff for Damien

### 7.1 Constants to implement

Damien should implement these as a Python constants module (e.g.,
`backend/app/policy_constants.py`) so that profile switching is a one-line
change.

```python
# === HACKATHON_2026 PROFILE (default for prototype) ===
PROFILE = "HACKATHON_2026"

# No-show
ARRIVAL_RADIUS_M = 10              # NS-1.1 (DATASET: from app event details)
FREE_WAIT_TIME_MIN = 5            # NS-1.3 (DATASET: cancellation_policy)
NO_SHOW_THRESHOLD_MIN = 8         # NS-1.4 (DATASET: cancellation_policy)
MINIMUM_CONTACT_ATTEMPTS = 2      # NS-1.5 (PROPOSED)
CANCELLATION_FEE_SGD = 5.00       # NS-1.6 (DATASET: cancellation_policy)
# FEE_GOES_TO = "driver_compensation"

# Route deviation
ROAD_NETWORK_FACTOR = 1.3         # RD-2.1 (PROPOSED)
DEVIATION_REVIEW_THRESHOLD_PCT = 20.0  # RD-2.2 (PROPOSED)
# For fixed fares: no refund. For metered: compute excess.

# Safety
SPEEDING_THRESHOLD_KMH = 90       # S-1.1 (PROPOSED)
SAFETY_KEYWORDS = [               # S-1.1 (PROPOSED)
    "threat", "threaten", "assault", "hit", "attack", "harass",
    "abuse", "racist", "race", "discriminat", "dangerous",
    "reckless", "scared", "afraid", "unsafe", "weapon",
]

# Confidence
AUTO_RULING_THRESHOLD = 0.85      # E-1.6 (PROPOSED)
SPOT_CHECK_THRESHOLD = 0.70       # E-1.6 (PROPOSED)

# === RYDE_PUBLIC_REFERENCE PROFILE (reference only, not used in prototype) ===
# FREE_WAIT_TIME_MIN_RYDE = 3
# NO_SHOW_THRESHOLD_MIN_RYDE = 3   # same 3-min period, no separate threshold
# CANCELLATION_FEE_RIDER_FACING = 6.61
# CANCELLATION_FEE_DRIVER_RECEIVING = 4.50
```

### 7.2 Evidence tool requirements

Damien's evidence tools must surface these facts for the Judge:

**`no_show_check()` must output:**
```json
{
  "driver_distance_from_pickup_m": 0.0,
  "arrived": true,
  "arrived_minutes_vs_scheduled": -2.0,
  "total_wait_min": 8.0,
  "free_wait_expired": true,
  "no_show_threshold_reached": true,
  "contact_attempts": 5,
  "rider_replies": 0,
  "missing_evidence": []
}
```

**`route_deviation()` must output:**
```json
{
  "baseline_distance_km": 5.2,
  "actual_distance_km": 7.8,
  "deviation_pct": 50.0,
  "review_triggered": true,
  "rider_route_messages": [],
  "rider_requested_detour": false,
  "trip_duration_min": 18.5,
  "avg_speed_kmh": 25.3,
  "traffic_justified": false,
  "fare_type": "fixed",
  "per_km_rate_sgd": null
}
```

**`fare_validate()` must output:**
```json
{
  "fare_type": "fixed",
  "actual_fare_sgd": 12.50,
  "per_km_rate_sgd": null,
  "surge_applied": false
}
```

**`history_lookup()` must output:**
```json
{
  "rider": { "avg_rating": 3.9, "total_trips": 34, "dispute_history": {...}, "fraud_flags": 1 },
  "driver": { "avg_rating": 4.9, "total_trips": 3201, "dispute_history": {...}, "fraud_flags": 0 }
}
```

### 7.3 Refund formulas (code, not LLM)

```python
def compute_no_show_outcome(facts, constants):
    """Returns (outcome, amount_sgd, clauses_cited)."""
    if facts.missing_evidence:
        return ("escalate", 0.00, ["NS-1.8", "E-1.5"])

    if not facts.arrived:
        return ("charge_reversed", constants.CANCELLATION_FEE_SGD, ["NS-1.1", "NS-1.7"])

    if not facts.free_wait_expired:
        return ("charge_reversed", constants.CANCELLATION_FEE_SGD, ["NS-1.3", "NS-1.7"])

    if not facts.no_show_threshold_reached:
        return ("charge_reversed", constants.CANCELLATION_FEE_SGD, ["NS-1.4", "NS-1.7"])

    if facts.contact_attempts < constants.MINIMUM_CONTACT_ATTEMPTS:
        return ("charge_reversed", constants.CANCELLATION_FEE_SGD, ["NS-1.5", "NS-1.7"])

    return ("charge_upheld", constants.CANCELLATION_FEE_SGD, ["NS-1.6"])


def compute_route_deviation_outcome(facts, constants):
    """Returns (outcome, amount_sgd, clauses_cited, conduct_flag)."""
    # Gate 0: Missing evidence → escalate
    if facts.missing_evidence:
        return ("escalate", 0.00, ["RD-2.7", "E-1.5"], False)

    if not facts.review_triggered:
        return ("no_action", 0.00, ["RD-2.2"], False)

    if facts.rider_requested_detour:
        return ("no_action", 0.00, ["RD-2.3"], False)

    if facts.fare_type == "fixed":
        if not facts.traffic_justified:
            return ("no_action", 0.00, ["RD-2.5"], True)  # conduct flag
        return ("no_action", 0.00, ["RD-2.4", "RD-2.5"], False)

    # metered or distance_time
    if not facts.traffic_justified:
        excess_km = facts.actual_distance_km - facts.baseline_distance_km
        excess_fare = excess_km * facts.per_km_rate_sgd
        refund = min(excess_fare, facts.actual_fare_sgd)
        return ("refund", refund, ["RD-2.6"], False)

    return ("no_action", 0.00, ["RD-2.4"], False)


def check_safety(chat_logs, gps_telemetry, description, constants):
    """Returns (is_safety_incident, category)."""
    text = " ".join([c["content"] for c in chat_logs]) + " " + description
    keyword_hits = [kw for kw in constants.SAFETY_KEYWORDS if kw in text.lower()]
    speeding = any(p["speed_kmh"] > constants.SPEEDING_THRESHOLD_KMH for p in gps_telemetry)

    if keyword_hits or speeding:
        categories = []
        if keyword_hits:
            categories.append("keyword: " + ", ".join(keyword_hits))
        if speeding:
            categories.append("speeding")
        return (True, "; ".join(categories))
    return (False, None)
```

**Note on `conduct_flag`:** `compute_route_deviation_outcome()` returns a
4-tuple `(outcome, amount_sgd, clauses_cited, conduct_flag)`. The
`conduct_flag` must be surfaced in the `Ruling` output (see
`schemas.md §4` — the `conduct_flag` field). When `True`, it indicates
that a fixed-fare trip had an unjustified deviation ≥ 20% with no rider
request and no traffic justification. No monetary refund is issued, but
the driver's conduct is flagged for review.

### 7.4 Judge prompt constraints

The Judge prompt must include:
- "You must cite at least one clause ID from the policy in `clauses_cited`."
- "You must not let rider/driver ratings, dispute history, or fraud flags
  override the trip evidence in determining the outcome."
- "The outcome and amount are provided to you by the code. You do not
  compute them. You explain them."
- "If a safety incident is flagged, you must set `escalated: true` and
  `outcome: escalate`."
- "Produce two explanations: `explanation_rider` and `explanation_driver`."

### 7.5 DISP-002 expected result

Running DISP-002 through the no-show chain:

| Clause | Check | Result |
|---|---|---|
| NS-1.1 | GPS at pickup (0 m from pickup, speed 0) | Pass |
| NS-1.2 | Arrived 08:43 vs scheduled 08:45 → –2 min (early) | Pass |
| NS-1.3 | Wait 08:43 → 08:51 = 8 min ≥ 5 min free wait | Pass |
| NS-1.4 | 8 min ≥ 8 min no-show threshold | Pass |
| NS-1.5 | 5 contact attempts (4 messages + 1 call) ≥ 2 | Pass |
| NS-1.6 | All gates passed → charge upheld | **S$5.00** |
| E-1.6 | High confidence (all evidence present, consistent) | ~0.90+ |

**Expected ruling: `charge_upheld`, S$5.00, confidence ~0.90+.**

### 7.6 Verification: DISP-002 verdict derived from evidence, not hardcoded

The `compute_no_show_outcome()` function in §7.3 produces the DISP-002
verdict by walking the evidence-derived gate chain, not by returning a
hardcoded answer. Tracing the function with DISP-002's facts:

| Step | Code path | Facts from evidence | Result |
|---|---|---|---|
| 1 | `if facts.missing_evidence:` | `missing_evidence = []` (no gaps) | Not triggered |
| 2 | `if not facts.arrived:` | `arrived = True` (GPS 0m ≤ 10m) | Not triggered |
| 3 | `if not facts.free_wait_expired:` | `free_wait_expired = True` (8 min ≥ 5 min) | Not triggered |
| 4 | `if not facts.no_show_threshold_reached:` | `no_show_threshold_reached = True` (8 min ≥ 8 min) | Not triggered |
| 5 | `if facts.contact_attempts < 2:` | `contact_attempts = 5` (5 ≥ 2) | Not triggered |
| 6 | `return ("charge_upheld", 5.00, ["NS-1.6"])` | All gates passed | **Result** |

The outcome and amount are determined entirely by the evidence facts
produced by `no_show_check()`. The dataset's "Expected ruling" field is
never read by the code. The "Evidence Summary" in
`docs/sample-dataset-DISP-002.md` is never passed to the agents. This
satisfies the constraint in `schemas.md`: *"Never pass the dataset's
'expected ruling' or evidence summary to the agents."*

---

## 8. References

All sources are documented in detail in `docs/policy_sources.md`. Summary:

| Ref ID | Source | URL | Classification | Verified |
|---|---|---|---|---|
| SRC-01 | Dataset DISP-002 | `data/DISP-002.json` | DATASET | Yes |
| SRC-02 | Cancellation and Waiting Fee (help article) | https://help.rydesharing.com/hc/en-us/articles/23534478435353 | OFFICIAL (primary) | Yes |
| SRC-03 | Cancellation and Waiting Time Policy (help article) | https://help.rydesharing.com/hc/en-us/articles/33362932998937 | OFFICIAL (primary) | Yes |
| SRC-04 | Driver Route Policy (help article) | https://help.rydesharing.com/hc/en-us/articles/4412122016153 | OFFICIAL (primary) | Yes |
| SRC-05 | Cancellation Fee Waiver Request (help article) | https://help.rydesharing.com/hc/en-us/articles/18229758389017 | OFFICIAL (primary) | Yes |
| SRC-06 | Driver Performance and Community Standards (help article) | https://help.rydesharing.com/hc/en-us/articles/33362721809049 | OFFICIAL (primary) | Yes |
| SRC-07 | Ryde Driver-Partner Handbook 2024 | https://rydesharing.com/wp-content/uploads/2024/06/Ryde-Driver-Partners-Handbook-2024-V23_4-6.pdf | OFFICIAL (secondary) | Yes |
| SRC-08 | Team brief | `docs/team-brief.md` | INTERNAL | Yes |
| SRC-09 | Schemas | `schemas.md` | INTERNAL | Yes |

---

*End of policy document. This is a hackathon prototype policy — not legal
advice and not a substitute for Ryde's actual terms of service.*
