# Policy Sources — Verification Record

**Project:** RydeResolve — Multi-Agent Autonomous Dispute Resolution System
**Track:** Tencent Cloud AI CAN DO IT Hackathon Singapore 2026, Digital Native Track (Ryde)
**Document owner:** Marcus (Product, Data & Pitch)
**Date:** 2026-10-08
**Companion to:** `docs/ryde_dispute_policy.md`

---

## 1. Purpose

This document records every source used to compile the Ryde dispute
resolution policy, its classification, verification status, the date it was
verified, and the key facts extracted from it. It exists so that every rule
in `docs/ryde_dispute_policy.md` is traceable to a source or explicitly
labelled as a proposed assumption.

**No invented content.** Where a source could not be accessed or did not
contain the expected information, it is marked as `UNVERIFIED`. No policy
clauses or quotations have been fabricated.

---

## 2. Source Classification Scheme

| Classification | Meaning |
|---|---|
| `OFFICIAL (primary)` | A direct Ryde help article or official Ryde publication, accessed and verified. |
| `OFFICIAL (secondary)` | An official Ryde document (e.g., the Driver-Partner Handbook) that supplements primary sources. |
| `DATASET` | The supplied hackathon dataset (DISP-002). These are the rules the prototype uses, which may differ from real Ryde policy. |
| `ORGANISER` | Documents provided by the hackathon organisers (Ryde/ChinaBUddy). Not verified as current public Ryde policy. Kept separate from `OFFICIAL`, `DATASET`, and `PROPOSED`. |
| `INTERNAL` | Our team's own documents (team brief, schemas). |
| `PROPOSED` | A design assumption created by Marcus for the hackathon. Not from any external source. |
| `UNVERIFIED` | A source that could not be accessed or did not contain the expected content. |

---

## 3. Verified Sources

### SRC-01 — Dataset DISP-002

| Field | Value |
|---|---|
| **URL / Path** | `data/DISP-002.json` (also documented in `docs/sample-dataset-DISP-002.md`) |
| **Classification** | DATASET |
| **Verified** | Yes — 2026-10-08 |
| **Description** | The hackathon-provided sample dispute dataset for a no-show charge case. |

**Key facts extracted (used by HACKATHON_2026 profile):**

| Fact | Value | Used in clause |
|---|---|---|
| Free waiting period | 5 minutes | NS-1.3 |
| Cancellation fee | S$5.00 | NS-1.6 |
| No-show threshold | 8 minutes (total wait from arrival) | NS-1.4 |
| Fee goes to | `driver_compensation` | NS-1.6 |
| Arrival radius | 10 m (from `app_events.driver_arrived` details: "Driver GPS within 10m of pickup point") | NS-1.1 |
| Expected ruling | Cancellation charge **UPHELD** | (validation target, not passed to agents) |

**Important note:** The dataset's `cancellation_policy` block and the
`app_events` details are the authoritative source for HACKATHON_2026
constants. The "Evidence Summary" and "Expected ruling" sections of
`docs/sample-dataset-DISP-002.md` must **never** be passed to the AI agents
(per `schemas.md`: "Never pass the dataset's 'expected ruling' or evidence
summary to the agents").

---

### SRC-02 — Cancellation and Waiting Fee (Ryde Help Article)

| Field | Value |
|---|---|
| **URL** | https://help.rydesharing.com/hc/en-us/articles/23534478435353-Cancellation-and-Waiting-Fee |
| **Classification** | OFFICIAL (primary) |
| **Verified** | Yes — 2026-10-08 |
| **Description** | Rider-facing cancellation and waiting fee policy. |

**Key facts extracted (verbatim from source):**

**On-demand trips:**
- Cancellations within **3 minutes of matching** are not chargeable.
- **Cancellation Fee of S$6.61** charged if:
  - Rider cancels after 3 minutes of matching, **OR**
  - Driver presses "I'm Here", waits > 3 minutes for rider, and cancels
    (rider no-show, no trip completion).
- **Waiting Time Fee of S$5** may be charged if:
  - Driver presses "I'm Here", waits > 3 minutes for rider to board, and
    continues the trip (rider boards, trip completed).

**Advanced (scheduled) trips:**
- Cancellations **> 15 minutes before scheduled trip time** are not
  chargeable.
- If the advanced trip request is accepted only after the 15-minute window
  closes, riders have a **3-minute grace period**.
- **Cancellation Fee of S$6.61** charged if:
  - Rider cancels after the cancellation window, **OR**
  - Driver cancels after waiting > 3 minutes (rider no-show).
- **Waiting Time Fee of S$5** may be charged if driver waits > 3 minutes
  and trip is completed.

**Fee notes:**
- For fares up to S$18: flat fee of S$1.15 (exclusive of GST) included in
  base fare.
- For fares exceeding S$18: flat fee of S$1.35 (exclusive of GST) included
  in base fare.
- Cashless transactions: payment transaction fee of 1.96% + S$0.24
  (inclusive of GST).

**Applicable to RYDE_PUBLIC_REFERENCE profile.** Not used in HACKATHON_2026
(which uses the dataset's S$5.00 fee and 5-minute wait).

---

### SRC-03 — Cancellation and Waiting Time Policy (Ryde Help Article)

| Field | Value |
|---|---|
| **URL** | https://help.rydesharing.com/hc/en-us/articles/33362932998937-Cancellation-and-Waiting-Time-Policy |
| **Classification** | OFFICIAL (primary) |
| **Verified** | Yes — 2026-10-08 |
| **Description** | Driver-facing cancellation and waiting time policy. |

**Key facts extracted (verbatim from source):**

**On-demand trips:**
- Cancellations within **3 minutes of matching** are not chargeable.
- Driver receives a **Cancellation Fee of S$4.50** if:
  - Rider cancels after 3 minutes of matching.
- Driver may charge a **Waiting Time Fee of S$4.50** if:
  - Driver pressed "I'm Here", waits > 3 minutes for rider, and cancels
    (rider no-show), **OR**
  - Driver pressed "I'm Here", waits > 3 minutes for rider to board, and
    continues the trip.

**Advanced (scheduled) trips:**
- Cancellations > 15 minutes before scheduled time are not chargeable.
- If advanced trip accepted after the 15-minute window, riders have a
  3-minute grace period.
- Driver receives **Cancellation Fee of S$4.50** if rider cancels after
  the cancellation window.
- Waiting Time Fee of S$4.50 applies under the same conditions as
  on-demand.

**Applies to all service types.**

**Discrepancy with SRC-02:** SRC-02 (rider-facing) states the cancellation
fee as S$6.61; SRC-03 (driver-facing) states S$4.50. The difference
(S$2.11) likely represents platform fees and GST retained by Ryde. See §6.

---

### SRC-04 — Driver Route Policy (Ryde Help Article)

| Field | Value |
|---|---|
| **URL** | https://help.rydesharing.com/hc/en-us/articles/4412122016153-Am-I-required-to-follow-the-suggested-route-by-the-rider |
| **Classification** | OFFICIAL (primary) |
| **Verified** | Yes — 2026-10-08 |
| **Description** | Policy on whether drivers must follow the rider's suggested route. |

**Key facts extracted (verbatim from source):**

> "The trip fare is fixed based on pick-up and drop-off points. So you may
> decide to take the fastest or most efficient route based on your GPS.
> However, if you do not mind taking the route suggested by the rider,
> agreeing and travelling via the rider's suggested route may result in a
> happier ride!"

**Critical implications for route deviation disputes:**
1. **Fares are fixed** based on pickup and dropoff points — not metered by
   distance or time (for standard service types).
2. The driver is **not required** to follow the rider's suggested route.
3. The driver may choose the fastest/most efficient route per GPS.
4. Because fares are fixed, **a longer route does not automatically
   increase the fare**. A route deviation is a conduct/quality issue, not
   an automatic monetary refund.

This is the basis for `docs/ryde_dispute_policy.md` RD-2.5 (fare
validation) and the principle that deviation ≠ automatic refund.

---

### SRC-05 — Cancellation Fee Waiver Request (Ryde Help Article)

| Field | Value |
|---|---|
| **URL** | https://help.rydesharing.com/hc/en-us/articles/18229758389017-Cancellation-Fee-Waiver-Request |
| **Classification** | OFFICIAL (primary) |
| **Verified** | Yes — 2026-10-08 |
| **Description** | Process for riders to request a cancellation fee waiver. |

**Key facts extracted (verbatim from source):**

- Riders who feel unfairly charged may submit a fee waiver request via
  **RydeHELP** in the app **within 30 days** of the trip.
- If eligible, Ryde issues a **voucher with a unique code worth S$6.61**
  as a refund for the incurred cancellation charges.
- The voucher must be used to top up the Ryde wallet within the expiry
  period.
- Requests submitted **after 30 days** will not be considered for waivers.
- The voucher is **non-refundable** and cannot be exchanged for cash.
- No extension of the expiry date.
- "The increase is due to the platform fee changes effective 17 Feb 2026."

**Implications for the dispute system:**
- The waiver value (S$6.61) matches SRC-02's cancellation fee, confirming
  consistency in the rider-facing fee amount.
- The 30-day window is an official policy that the prototype could
  implement as a time-limit check on dispute eligibility (PROPOSED — not
  currently in the policy clauses, could be added as NS-1.0).
- The platform fee change effective 17 Feb 2026 indicates the S$6.61 figure
  is current as of that date.

---

### SRC-06 — Driver Performance and Community Standards (Ryde Help Article)

| Field | Value |
|---|---|
| **URL** | https://help.rydesharing.com/hc/en-us/articles/33362721809049-Driver-Performance-and-Community-Standards |
| **Classification** | OFFICIAL (primary) |
| **Verified** | Yes — 2026-10-08 |
| **Description** | Driver performance metrics, community standards, account disablement, and fraud policies. |

**Key facts extracted (verbatim from source):**

**Account disablement conditions:**
- Driver Rating (DR) < 4.80
- Cancellation Rate (CR) > 17.5%
- Adverse ratings for errant behaviour (comments on race, ethnicity,
  national origin, disability, etc.)
- Fraudulent activity (overcharging, completing trips without rider onboard)
- Dormant account (no trip in 1 year)

**Driver ratings:**
- Calculated based on last 100 trips.
- New drivers default to 4.90, adjusted after 11th unique review.

**Cancellation rate:**
- Calculated on most recent trips.
- Rider no-show cancellations do not cause account suspension: "Drivers do
  not have to worry about account suspension from trip cancellations."

**Trip Acceptance and Cancellation Policy (3A):**
- Drivers are **strictly prohibited** from accepting a trip and cancelling
  after the rider has boarded without a valid reason.
- Invalid cancellation reasons include: rider's race/ethnicity/national
  origin, rider's pet type, discriminatory/prejudicial reasons, personal
  preferences unrelated to safety/legal regulations.

**Fraudulent activity (Section 4, 5):**
- Overcharging riders, completing trips without rider onboard,
  misrepresenting trip details, submitting false documents.
- **"Remaining stationary and uncontactable after accepting a ride to
  trigger cancellation or waiting fees"** — explicitly listed as fraudulent
  behaviour.
- Abuse of Cancellation and Waiting Fee Policy — listed as fraudulent.
- Zero-tolerance policy; may report to MOM, LTA, IRAS, CPF Board.
- "Driver-partners will be given the opportunity to respond before final
  decisions are made, except in urgent or high-risk situations."

**In-Vehicle Recording Devices (4A):**
- IVRDs are **not allowed** on the Ryde platform.
- Use may result in immediate account suspension and reporting to LTA.

**Account restoration:**
- S$10 processing fee (excluding GST).
- Ratings reset to 4.90, CR reset to 0%.
- Repeated/severe breaches → permanent suspension.

**Implications for the dispute system:**
- The fraud category "remaining stationary and uncontactable after
  accepting a ride to trigger cancellation or waiting fees" is directly
  relevant to no-show disputes — a driver who fakes arrival to trigger a
  fee is committing fraud. This supports the GPS verification in NS-1.1.
- The discrimination prohibitions support the safety escalation categories
  in S-1.1.
- The "opportunity to respond before final decisions" principle supports
  the human-review escalation in S-1.2.

---

### SRC-07 — Ryde Driver-Partner Handbook 2024

| Field | Value |
|---|---|
| **URL** | https://rydesharing.com/wp-content/uploads/2024/06/Ryde-Driver-Partners-Handbook-2024-V23_4-6.pdf |
| **Classification** | OFFICIAL (secondary) |
| **Verified** | Yes — 2026-10-08 (text extracted via `pdftotext`) |
| **Description** | Official Ryde driver handbook, covering code of conduct, services, earnings, and best practices. Last updated 31 May 2024. |

**Key facts extracted:**

**Code of conduct:**
- Drivers must adhere to driving rules and regulations, speed limits, road
  signs.
- Regular vehicle maintenance required.
- Refrain from using phones while driving.
- "Please travel directly to the passengers' pick-up and dropoff locations
  once you have accepted the trip."
- "Any forms of crimes is not tolerated on our platform."
- No comments on appearance, race, religion, or personal beliefs.
- "Contacting your passenger after the trip has ended is strictly
  prohibited."

**Service types (relevant to fare type in RD-2.5):**
- RydeFLASH — carpool/taxi/private-hire, 1–4 passengers
- RydeX — 4-seater private-hire
- RydePOOL — 1 passenger, drop-off sequence dependent on route
- **RydeTAXI — metered taxi only** (confirms metered fare type exists)
- RydeSEND — on-demand delivery
- RydeXL — 6-seater private-hire
- RydePET — up to 4 pax + pets
- RydeLUXE — 4-seater premium

**Earnings:**
- 0% commission for PDVL/TDVL drivers (until 31 Dec 2025 per handbook;
  may have been extended).
- Standard cash out: S$1 admin fee, 5 working days.
- Instant cash out: S$1 admin fee, max S$225.

**Best practices (safety-relevant):**
- "Safety will always be a priority over time."
- Do not drive if tired or emotional.
- Do not drive under the influence.
- Do not drive erratically (speeding, tailgating, sudden lane cutting).
- Maintain 3-second following distance (9 seconds in rain).

**Implications for the dispute system:**
- RydeTAXI is metered, confirming that metered fares exist and the
  RD-2.5/RD-2.6 refund logic for metered fares is relevant.
- The code of conduct supports the safety escalation categories.
- The "travel directly to pickup/dropoff" instruction supports the route
  deviation review framework.
- The handbook is dated 31 May 2024 — some details (e.g., 0% commission
  expiry, inactive account periods) may have changed since then. The help
  articles (SRC-02 through SRC-06) are more current where they conflict.

---

### SRC-08 — Team Brief

| Field | Value |
|---|---|
| **Path** | `docs/team-brief.md` |
| **Classification** | INTERNAL |
| **Verified** | Yes — 2026-10-08 |
| **Description** | Team planning document for the hackathon. |

**Key facts used:**
- Architecture: evidence tools → advocates in parallel → judge → escalation.
- "Code finds the facts, the LLMs argue about them."
- "Refund amounts come from a policy formula in code, not from the Judge."
- Example clause: "R-3.2: deviation >20% without rider request → refund the
  difference" (basis for RD-2.2 threshold).
- Judge runs at temperature 0 for consistency.
- Safety incidents are never auto-resolved.
- DISP-002 expected ruling: charge upheld.
- Test cases planned (10 cases, see team brief §Test cases).

---

### SRC-09 — Schemas

| Field | Value |
|---|---|
| **Path** | `schemas.md` |
| **Classification** | INTERNAL |
| **Verified** | Yes — 2026-10-08 |
| **Description** | Agreed JSON shapes for dispute input, evidence output, advocate brief, and ruling. |

**Key facts used:**
- Evidence output schema (`facts` + `flags`).
- Advocate brief schema (`position`, `arguments` with `evidence_refs` and
  `clauses`).
- Ruling schema (`outcome`, `amount_sgd`, `confidence`, `clauses_cited`,
  `explanation_rider`, `explanation_driver`, `escalated`,
  `escalation_reason`).
- "Never pass the dataset's 'expected ruling' or evidence summary to the
  agents."
- "amount_sgd is computed in code from the policy formula, never by the
  Judge."
- Route deviation cases need planned route + fare breakdown (TBD with
  Marcus).

---

## 4. Organiser-Provided Sources

Sources provided by the hackathon organisers on 2026-10-13. These are **not**
verified as current public Ryde policy. They are kept separate from
`OFFICIAL`, `DATASET`, and `PROPOSED` classifications.

### SRC-ORG-1 — Ryde Dispute Resolution Policy v2.1

| Field | Value |
|---|---|
| **Path** | `docs/organiser_policy_v2.1.md` (original in `incoming/`) |
| **Classification** | `ORGANISER` |
| **Verified** | Received 2026-10-13 |
| **Description** | Organiser-provided dispute resolution policy with different thresholds, refund matrix, and 3 precedent rulings. Effective date 2026-01-01. |

**Key differences from HACKATHON_2026 profile (used by the prototype):**

| Rule | HACKATHON_2026 | Organiser v2.1 |
|---|---|---|
| No-show wait | 5-min free + 8-min threshold | 5-min free, then cancel |
| Contact attempts | Minimum 2 | 1 message AND 1 call |
| Route deviation | 20% threshold | 1 km refund matrix, 2 km human-review boundary |
| Fare/surge | Not covered | Upfront quote binding, surge notification required |
| Confidence | <0.70 escalate | <$10 final, $10-$50 need 80%, >$50 human; fraud ≥1 → 95% |
| Property damage | Not covered | Cleaning $50, repair needs quote |

**Status:** Reference only. Not merged into the active policy. Switching
profiles requires a decision from Marcus and Damien (Decision Gate A).

---

### SRC-ORG-2 — Route Deviation Dataset DISP-001 (Organiser)

| Field | Value |
|---|---|
| **Path** | `data/DISP-001-ORG.json` (transformed from `incoming/`) |
| **Classification** | `ORGANISER` |
| **Verified** | Received 2026-10-13 |
| **Description** | Organiser route-deviation case: Orchard Central → Changi T3. 4.3 km excess distance, expected S$3.44 partial refund. |

**Transform applied:** Fields renamed for Pydantic compatibility (`message`→`content`,
GPS `status` inferred). All expected-ruling, evidence_summary, recommended_ruling,
traffic_conditions, traffic_analysis, chat_log_analysis, and optimal_route fields
stripped from agent input — stored in `data/DISP-001-ORG.expected.json` only.

**Internal ID:** `DISP-001-ORG` (original `DISP-001` remapped to avoid collision
with repo's existing Tiong Bahru → VivoCity case).

**Policy conflict:** Organiser v2.1 §6.2 requires escalation for deviations >2 km;
this case has 4.3 km deviation but expects auto-refund. Requires Decision Gate A.

---

### SRC-ORG-3 — Fare Dispute Dataset DISP-003

| Field | Value |
|---|---|
| **Path** | `data/DISP-003.json` (transformed from `incoming/`) |
| **Classification** | `ORGANISER` |
| **Verified** | Received 2026-10-13 |
| **Description** | Organiser fare-dispute case: S$12 quote, S$16.50 charged, unnotified surge, expected S$4.50 refund. |

**Status:** Reference fixture only. `dispute_type: "fare_dispute"` is not
supported by the backend (`DisputeType` Literal only allows
`no_show_charge` and `route_deviation`). The case loader skips this file
with a warning. Implementing fare_dispute is a stretch goal requiring
schema, evidence tool, outcome formula, and tests — pending Decision Gate A.

---

## 5. Unverified Sources

None. All five provided Ryde help article URLs were successfully accessed
and verified on 2026-10-08. The driver handbook PDF was also successfully
downloaded and text-extracted.

No source was marked as `UNVERIFIED`.

---

## 6. Discrepancies Between HACKATHON_2026 and RYDE_PUBLIC_REFERENCE

These discrepancies are between the supplied hackathon dataset (DISP-002)
and the verified Ryde public help articles. The prototype uses
HACKATHON_2026 values; the discrepancies are documented for reference only.

### 6.1 Free waiting period

| Profile | Value | Source |
|---|---|---|
| HACKATHON_2026 | 5 minutes | DISP-002 `cancellation_policy.free_wait_time_min` |
| RYDE_PUBLIC_REFERENCE | 3 minutes after "I'm Here" | SRC-02, SRC-03 |

**Discrepancy:** The dataset grants 2 additional minutes of free waiting
compared to the public policy. This is a significant difference — under the
dataset's rules, a rider has more time to appear before a fee can be
charged.

### 6.2 No-show threshold

| Profile | Value | Source |
|---|---|---|
| HACKATHON_2026 | 8 minutes total wait (5 min free + 3 min no-show window) | DISP-002 `cancellation_policy.no_show_threshold_min` |
| RYDE_PUBLIC_REFERENCE | 3 minutes after "I'm Here" (same as free wait; no separate extended threshold) | SRC-02, SRC-03 |

**Discrepancy:** The dataset models a two-stage process (free wait then
no-show window), while the public policy has a single 3-minute threshold.
Under the dataset, a driver must wait 8 minutes; under public policy, 3
minutes. This is the largest discrepancy and directly affects the DISP-002
test case (driver waited 8 minutes — valid under the dataset, but the
public policy would have allowed a fee at 3 minutes).

### 6.3 Cancellation fee amount

| Profile | Value | Source |
|---|---|---|
| HACKATHON_2026 | S$5.00 | DISP-002 `cancellation_policy.cancellation_fee_after_wait` |
| RYDE_PUBLIC_REFERENCE (rider-facing) | S$6.61 | SRC-02, SRC-05 |
| RYDE_PUBLIC_REFERENCE (driver-receiving) | S$4.50 | SRC-03 |

**Discrepancy:** The dataset fee (S$5.00) does not match either the
rider-facing amount (S$6.61) or the driver-receiving amount (S$4.50) in the
public articles. The S$6.61 likely includes platform fees and GST (SRC-05
mentions "platform fee changes effective 17 Feb 2026"). The S$4.50 is the
amount the driver receives. The S$5.00 dataset value appears to be a
simplified round number for the hackathon.

### 6.4 Waiting time fee (for completed trips)

| Profile | Value | Source |
|---|---|---|
| HACKATHON_2026 | Not specified (dataset only covers cancellation fee) | DISP-002 |
| RYDE_PUBLIC_REFERENCE | S$5.00 (SRC-02) / S$4.50 (SRC-03) if driver waits > 3 min and trip completes | SRC-02, SRC-03 |

**Discrepancy:** The dataset does not include a waiting time fee for
completed trips. The public policy includes one. This is not relevant to
the no-show dispute type but is noted for completeness.

### 6.5 Cancellation window for advanced/scheduled trips

| Profile | Value | Source |
|---|---|---|
| HACKATHON_2026 | Not specified | DISP-002 |
| RYDE_PUBLIC_REFERENCE | Cancellations > 15 min before scheduled time are free; 3-min grace if accepted late | SRC-02, SRC-03 |

**Discrepancy:** The dataset does not cover advanced/scheduled trip
cancellation windows. The public policy does. DISP-002 involves a scheduled
pickup time (08:45) but the cancellation occurs after driver arrival, so
this window is not directly relevant to the test case.

### 6.6 Waiver request window

| Profile | Value | Source |
|---|---|---|
| HACKATHON_2026 | Not specified | DISP-002 |
| RYDE_PUBLIC_REFERENCE | 30 days via RydeHELP | SRC-05 |

**Discrepancy:** The dataset does not specify a time limit for filing a
dispute/waiver. The public policy allows 30 days. Marcus could propose
implementing a 30-day check as a pre-condition (PROPOSED, not yet in
clauses — flagged for Damien approval in §6).

### 6.7 Arrival radius / GPS verification

| Profile | Value | Source |
|---|---|---|
| HACKATHON_2026 | 10 m (from `app_events` details in DISP-002) | DISP-002 app_events |
| RYDE_PUBLIC_REFERENCE | Not specified in official sources | — |

**Discrepancy:** No official source specifies the GPS radius that counts as
"arrived." The 10 m value is derived from the dataset's app event details
("Driver GPS within 10m of pickup point"). This is used as a DATASET rule
in the HACKATHON_2026 profile and would be PROPOSED in the
RYDE_PUBLIC_REFERENCE profile.

---

## 7. Open Items Requiring Damien Approval

These are design decisions in the policy that Damien (Backend & Agents)
must review and approve before implementation:

1. **Minimum contact attempts (NS-1.5):** Proposed at 2. Damien must
   confirm this is a reasonable threshold and implement the counting logic
   (messages + calls + driver-called-rider app events).

2. **Arrival radius (NS-1.1):** 10 m for HACKATHON_2026. Damien must
   implement the Haversine distance function and confirm 10 m is the right
   threshold (the dataset's app event says "within 10m" but GPS precision
   in practice may vary).

3. **Route deviation baseline method (RD-2.1):** Proposed as Haversine × 1.3
   road factor for the hackathon. Damien must decide whether to use a
   real routing API or the simplified Haversine method. If using Haversine,
   confirm the 1.3 factor.

4. **20% deviation threshold (RD-2.2):** Proposed. Damien must confirm
   this is implementable and reasonable.

5. **Fare type detection (RD-2.5):** The policy assumes the fare breakdown
   will indicate whether the fare is fixed, metered, or distance/time-based.
   Damien must confirm the schema for fare data (schemas.md notes this as
   TBD: "Route deviation cases will also need planned route + fare
   breakdown").

6. **Speeding threshold (S-1.1):** Proposed at 90 km/h. Damien must
   confirm this is appropriate (Singapore expressway limit is typically
   80–90 km/h). Consider whether the threshold should vary by road type.

7. **Confidence thresholds (E-1.6):** Proposed 0.85 for auto-ruling and
   0.70 for escalation. Damien must implement these in the Judge prompt
   and the escalation routing logic.

8. **30-day dispute filing window (SRC-05):** The public policy specifies a
   30-day window for waiver requests. Damien must decide whether to
   implement a filing-date check as a pre-condition for the prototype
   (PROPOSED, not yet a numbered clause).

9. **Conduct flag for fixed-fare deviation (RD-2.5):** When a fixed-fare
   trip has an unjustified deviation ≥ 20%, the policy produces `no_action`
   with a `conduct_flag`. Damien must decide how to surface this flag
   (e.g., in the ruling output, in a separate field, or in the
   explanation).

10. **Missing evidence handling (NS-1.8):** The policy escalates when
    critical evidence is missing. Damien must confirm the list of
    critical fields and implement the missing-evidence check.

---

## 8. Verification Method

All five Ryde help article URLs were accessed on 2026-10-08 using an
automated web fetch tool. The full text of each article was extracted and
recorded in this document. The driver handbook PDF was downloaded and
converted to text using `pdftotext`.

No source content was invented, paraphrased as quotation, or assumed. Where
a source did not contain expected information (e.g., the route policy
article does not describe dispute handling), this is noted and the gap is
filled with explicitly labelled `PROPOSED` rules.

---

*End of sources document.*
