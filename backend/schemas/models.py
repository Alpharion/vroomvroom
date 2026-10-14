"""Pydantic models for the 4 shared JSON shapes. Must match ../../schemas.md."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DisputeType = Literal["no_show_charge", "route_deviation"]
Side = Literal["rider", "driver"]


class _Open(BaseModel):
    """Dataset models: tolerate extra keys Ryde may add to new cases."""

    model_config = ConfigDict(extra="allow")


class _Strict(BaseModel):
    """Agent output models: reject anything outside the agreed shape."""

    model_config = ConfigDict(extra="forbid")


# ---------- 1. Dispute input (based on data/DISP-002.json) ----------


class DisputeTicket(_Open):
    dispute_id: str
    trip_id: str
    filed_by: Side
    dispute_type: DisputeType
    description: str
    filed_at: datetime
    status: str


class RiderDisputeHistory(_Open):
    total_disputes: int
    upheld: int
    rejected: int


class DriverDisputeHistory(_Open):
    total_disputes: int
    upheld_against: int
    rejected: int


class RiderProfile(_Open):
    rider_id: str
    name: str
    account_age_days: int
    total_trips: int
    avg_rating: float
    dispute_history: RiderDisputeHistory
    fraud_flags: int
    fraud_flag_details: str | None = None
    payment_method: str | None = None


class DriverProfile(_Open):
    driver_id: str
    name: str
    account_age_days: int
    total_trips: int
    avg_rating: float
    dispute_history: DriverDisputeHistory
    fraud_flags: int
    fraud_flag_details: str | None = None
    vehicle: str | None = None


class Location(_Open):
    name: str
    lat: float
    lng: float


class TripData(_Open):
    trip_id: str
    rider_id: str
    driver_id: str
    pickup_location: Location
    dropoff_location: Location
    scheduled_time: datetime
    # No-show fields
    driver_arrival_time: datetime | None = None
    driver_wait_start: datetime | None = None
    cancellation_time: datetime | None = None
    cancellation_fee: float | None = None
    cancellation_reason: str | None = None
    # Route deviation fields (TBD with Marcus)
    planned_route: list[dict[str, Any]] | None = None
    fare_breakdown: dict[str, Any] | None = None


class GpsPoint(_Open):
    timestamp: datetime
    lat: float
    lng: float
    speed_kmh: float
    status: str


class ChatMessage(_Open):
    timestamp: datetime
    sender: Literal["rider", "driver", "system"]
    type: str  # message | call | system
    content: str


class AppEvent(_Open):
    timestamp: datetime
    event_type: str
    details: str


class CancellationPolicy(_Open):
    free_wait_time_min: float
    cancellation_fee_after_wait: float
    no_show_threshold_min: float
    fee_goes_to: str


class DisputeCase(_Open):
    dispute_ticket: DisputeTicket
    rider_profile: RiderProfile
    driver_profile: DriverProfile
    trip_data: TripData
    gps_telemetry: list[GpsPoint]
    chat_logs: list[ChatMessage]
    app_events: list[AppEvent]
    cancellation_policy: CancellationPolicy | None = None


# ---------- 2. Evidence output (from plain-code tools) ----------


class EvidenceOutput(_Strict):
    dispute_id: str
    tool: str  # no_show_check | route_deviation | fare_validate | history_lookup
    facts: dict[str, Any]
    flags: list[str] = []


# ---------- 3. Advocate brief (same schema + cap for both sides) ----------

MAX_ARGUMENTS = 5
MAX_POINT_CHARS = 400


class Argument(_Strict):
    point: str = Field(max_length=MAX_POINT_CHARS)
    evidence_refs: list[str] = Field(min_length=1)  # e.g. "no_show_check.total_wait_min"
    clauses: list[str] = Field(min_length=1)  # e.g. "NS-1.6"


class AdvocateBrief(_Strict):
    dispute_id: str
    side: Side
    position: str = Field(max_length=200)
    arguments: list[Argument] = Field(min_length=1, max_length=MAX_ARGUMENTS)
    weaknesses_acknowledged: list[str] = []


# ---------- 4. Ruling ----------

Outcome = Literal[
    "refund",
    "compensation",
    "no_action",
    "charge_upheld",
    "charge_reversed",
    "escalate",
]


ClaimVerdict = Literal["consistent", "contradicted", "unverifiable"]


class ClaimCheck(_Strict):
    """One factual claim from the filer's description, checked against records."""

    claim: str  # what the filer says, e.g. "I paid $50"
    record: str  # what Ryde's records show, e.g. "Charged S$5.00 (cancellation fee)"
    evidence_refs: list[str] = []  # e.g. "fare_validate.actual_fare_sgd"
    verdict: ClaimVerdict


class Ruling(_Strict):
    dispute_id: str
    outcome: Outcome
    amount_sgd: float = Field(ge=0)  # set by code from the policy formula, never the Judge
    confidence: float = Field(ge=0, le=1)
    clauses_cited: list[str]
    explanation_rider: str
    explanation_driver: str
    conduct_flag: bool = False
    escalated: bool = False
    escalation_reason: str | None = None
    # The filer's claims checked against the records by the Judge. Reported
    # only: outcome and amount always come from the records via code.
    claim_checks: list[ClaimCheck] = []

    @model_validator(mode="after")
    def _escalation_consistent(self):
        if (self.outcome == "escalate") != self.escalated:
            raise ValueError("outcome 'escalate' and escalated=True must go together")
        if self.escalated and not self.escalation_reason:
            raise ValueError("escalated rulings need an escalation_reason")
        return self


# ---------- Agent log message (UI stream) ----------


class AgentLogMessage(_Strict):
    seq: int
    agent: Literal["rider_advocate", "driver_advocate", "judge", "system"]
    type: Literal["evidence", "argument", "rebuttal", "ruling"]
    content: str
    timestamp: datetime
