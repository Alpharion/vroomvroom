"""Policy constants shared across evidence tools and outcome formulas.

These correspond to the ORGANISER_V2_1 profile based on
docs/organiser_policy_v2.1.md. Switching to a different profile should be
a one-line change here.
"""

PROFILE = "ORGANISER_V2_1"

# No-show (Section 2 of organiser policy v2.1)
ARRIVAL_RADIUS_M = 10
FREE_WAIT_TIME_MIN = 5          # §2.1: free wait time of 5 minutes
NO_SHOW_THRESHOLD_MIN = 5       # §2.1: cancellation permitted after 5-min free wait
MINIMUM_CONTACT_ATTEMPTS = 2     # §2.3: at least 1 message AND 1 call (enforced as type check)
CANCELLATION_FEE_SGD = 5.00     # §2.2: $5.00 no-show cancellation fee

# Route deviation (Section 1 + §6.2 of organiser policy v2.1)
ROAD_NETWORK_FACTOR = 1.3
DEVIATION_REVIEW_THRESHOLD_PCT = 20.0
DEVIATION_AUTO_RULE_KM = 2.0     # §6.2: AI ruling only if deviation <= 2km, else escalate
ROUTE_DEVIATION_CONFIDENCE_THRESHOLD = 0.80  # §6.2: AI ruling needs >= 80% confidence

# Safety (S-1.1)
SPEEDING_THRESHOLD_KMH = 90
SAFETY_KEYWORDS = [
    "threat",
    "threaten",
    "assault",
    "hit",
    "attack",
    "harass",
    "abuse",
    "racist",
    "race",
    "discriminat",
    "dangerous",
    "reckless",
    "scared",
    "afraid",
    "unsafe",
    "weapon",
]

# Confidence / escalation (E-1.6)
AUTO_RULING_THRESHOLD = 0.85
SPOT_CHECK_THRESHOLD = 0.70

# Human review queue SLA routing (PROPOSED, team brief: "urgent or
# high-value disputes get prioritised"; Ryde's current turnaround is 24-72 h)
HIGH_VALUE_DISPUTE_SGD = 30.00  # charged fare at or above this is high priority
SLA_HOURS_HIGH = 4  # safety incidents and high-value disputes
SLA_HOURS_NORMAL = 24

# Organiser reference cases. The organiser's own dataset rules DISP-001-ORG a partial refund of
# the excess distance fare (4.3 km x $0.80 = $3.44, clauses ORG-RD-1.2 and ORG-RD-1.3) although
# the excess is over the 2 km automatic-ruling limit, which its policy section 6.2 says should
# escalate. The team decided on 14 Oct to follow the organiser's ruling for this one trip, so
# for these case IDs the route tool uses the platform's recorded distances and the outcome
# formula returns that refund. No other case is affected.
ORGANISER_REFERENCE_CASES = frozenset({"DISP-001-ORG"})
