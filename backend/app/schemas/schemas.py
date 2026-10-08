"""
Pydantic request / response schemas for the TradeGuard API.

All fields match API_CONTRACT.md and DATA_MODEL.md:
- Prices and money as Decimal strings (never float).
- Quantities as positive integers (instrument units, never lots).
- Timestamps as datetime with timezone.
- Extra fields are forbidden on request models (strict).
- Secrets (challenge hashes, session tokens) never appear in responses.
"""
from __future__ import annotations
from decimal import Decimal
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enumerations (grounded in DATA_MODEL.md) ─────────────────────────────────

class TradingMode(str, Enum):
    SIMULATOR         = "SIMULATOR"
    ORGANIZER_SANDBOX = "ORGANIZER_SANDBOX"
    LIVE              = "LIVE"

class ProposalKind(str, Enum):
    PLACE_ORDER  = "PLACE_ORDER"
    MODIFY_ORDER = "MODIFY_ORDER"
    CANCEL_ORDER = "CANCEL_ORDER"
    CREATE_RULE  = "CREATE_RULE"
    CREATE_PLAN  = "CREATE_PLAN"

class ProposalState(str, Enum):
    READY      = "READY"
    CONSUMED   = "CONSUMED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED    = "EXPIRED"

class OrderSide(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    LIMIT = "LIMIT"

class OperationState(str, Enum):
    READY       = "READY"
    SUBMITTING  = "SUBMITTING"
    UNKNOWN     = "UNKNOWN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED    = "REJECTED"
    HELD        = "HELD"
    BLOCKED     = "BLOCKED"
    SUPERSEDED  = "SUPERSEDED"

class MemberRole(str, Enum):
    TRADER    = "TRADER"
    READ_ONLY = "READ_ONLY"


# ── Shared base models ────────────────────────────────────────────────────────

class StrictModel(BaseModel):
    """Base that forbids extra fields on all request models (API_CONTRACT §1)."""
    model_config = {"extra": "forbid"}


# ── Quote policy ──────────────────────────────────────────────────────────────

class QuotePolicy(StrictModel):
    """Describes how the worker validates the live quote before dispatch."""
    reference_kind: str = Field(..., pattern="^(SNAPSHOT|RULE_THRESHOLD)$")
    snapshot_quote_id: Optional[UUID] = None
    reference_price: Optional[Decimal] = None   # RULE_THRESHOLD only
    max_quote_age_ms: int = Field(..., ge=100, le=60_000)
    max_drift_bps: int    = Field(..., ge=0,   le=2_000)

    @model_validator(mode="after")
    def validate_reference_fields(self) -> "QuotePolicy":
        if self.reference_kind == "SNAPSHOT" and self.snapshot_quote_id is None:
            raise ValueError("snapshot_quote_id is required for SNAPSHOT reference_kind")
        if self.reference_kind == "RULE_THRESHOLD" and self.reference_price is None:
            raise ValueError("reference_price is required for RULE_THRESHOLD reference_kind")
        return self


# ── Canonical order terms (DATA_MODEL §4) ────────────────────────────────────

class PlaceOrderTerms(StrictModel):
    terms_schema_version: int    = Field(1, ge=1)
    account_id:           UUID
    mode:                 TradingMode
    action:               str    = Field("PLACE_ORDER", pattern="^PLACE_ORDER$")
    instrument_id:        UUID
    side:                 OrderSide
    quantity_units:       int    = Field(..., ge=1, description="Integer instrument units; never lots")
    order_type:           OrderType = OrderType.LIMIT
    limit_price:          Decimal = Field(..., gt=Decimal("0"))
    product:              str    = Field(..., min_length=1)
    time_in_force:        str    = Field(..., min_length=1)
    valid_until:          datetime
    quote_policy:         QuotePolicy

    @field_validator("limit_price", mode="before")
    @classmethod
    def coerce_decimal(cls, v: Any) -> Decimal:
        try:
            return Decimal(str(v))
        except Exception:
            raise ValueError(f"limit_price must be a decimal string, got {v!r}")


# ── Approval request (API_CONTRACT §5) ───────────────────────────────────────

class ApprovalRequest(StrictModel):
    """
    Client sends only the expected_version and challenge.
    Server derives actor and account from the authenticated session.
    Client actor IDs and replacement terms are explicitly forbidden.
    """
    expected_version:    int  = Field(..., ge=1)
    approval_challenge:  str  = Field(..., min_length=8)


# ── Proposal revision request (API_CONTRACT §4) ───────────────────────────────

class ProposalRevisionRequest(StrictModel):
    expected_version:   int = Field(..., ge=1)
    clarification_text: str = Field(..., min_length=1, max_length=2_000)


# ── Chat request (API_CONTRACT §3) ────────────────────────────────────────────

class ChatRequest(StrictModel):
    conversation_id: Optional[UUID] = None   # None means new conversation
    text: str = Field(..., min_length=1, max_length=2_000)


# ── Emergency stop (API_CONTRACT §8) ─────────────────────────────────────────

class EmergencyStopRequest(StrictModel):
    reason: str = Field(..., min_length=1, max_length=500)


class ResumeTradingRequest(StrictModel):
    expected_control_version:     int  = Field(..., ge=1)
    acknowledge_outstanding_exposure: bool = Field(...)

    @field_validator("acknowledge_outstanding_exposure")
    @classmethod
    def must_acknowledge(cls, v: bool) -> bool:
        if not v:
            raise ValueError("acknowledge_outstanding_exposure must be true to resume trading")
        return v


# ── Responses (no secrets in any response) ───────────────────────────────────

class ProposalPreview(BaseModel):
    maximum_notional: str    # Decimal as string
    currency: str
    fees_included: bool
    assumes_full_fill: bool
    source: str


class ProposalResponse(BaseModel):
    proposal_id:         UUID
    version:             int
    kind:                ProposalKind
    state:               ProposalState
    mode:                TradingMode
    terms:               dict         # canonical_terms JSONB
    parser_report:       dict
    preview:             ProposalPreview
    # The approval_challenge itself (not its hash) is sent to the client for submission
    approval_challenge:  str
    approval_expires_at: datetime
    created_at:          datetime


class ApprovalResponse(BaseModel):
    approval_id:      UUID
    proposal_id:      UUID
    proposal_version: int
    resource_type:    str   # OPERATION | RULE | PLAN
    resource_id:      UUID
    mode:             TradingMode
    status_url:       str


class OperationResponse(BaseModel):
    operation_id:       UUID
    account_id:         UUID
    state:              OperationState
    action:             str
    hold_code:          Optional[str] = None
    broker_order_id:    Optional[UUID] = None
    version:            int
    created_at:         datetime


class HealthResponse(BaseModel):
    status: str
    mode:   str
    environment: str
