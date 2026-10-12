"""Policy constants shared across evidence tools and outcome formulas.

These correspond to the HACKATHON_2026 profile in docs/ryde_dispute_policy.md §7.1.
Switching to a different profile should be a one-line change here.
"""

PROFILE = "HACKATHON_2026"

# No-show (NS-1.x)
ARRIVAL_RADIUS_M = 10
FREE_WAIT_TIME_MIN = 5
NO_SHOW_THRESHOLD_MIN = 8
MINIMUM_CONTACT_ATTEMPTS = 2
CANCELLATION_FEE_SGD = 5.00

# Route deviation (RD-2.x)
ROAD_NETWORK_FACTOR = 1.3
DEVIATION_REVIEW_THRESHOLD_PCT = 20.0

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
