"""
Backend validation service for TradeGuard.

All checks described here enforce invariants from INVARIANTS.md.
No check is hardcoded to pass. Each function returns a dataclass
describing whether the check passed and, if not, the machine-readable
reason to return to the frontend.

Validation order at approval (INV-02, INV-03, INV-04, INV-09, INV-11):
  1. Session / actor membership          (INV-03, INV-33)
  2. Proposal state and version          (INV-04, INV-09)
  3. Approval challenge hash             (INV-04, INV-05)
  4. Approval window expiry             (INV-04)
  5. Emergency stop                     (INV-22)
  6. Risk limits                        (INV-17, INV-20)
  7. Quote freshness                    (INV-18)
  8. Interpretation agreement            (INV-06)
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from app.core.config import settings


# ── Result container ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    code: str = ""
    reason: str = ""
    details: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", self.details or {})

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(passed=True)

    @classmethod
    def fail(cls, code: str, reason: str, **details) -> "ValidationResult":
        return cls(passed=False, code=code, reason=reason, details=details)


# ── 1. Account membership / role check (INV-03, INV-33) ──────────────────────

def check_account_membership(
    user_id: UUID,
    account_id: UUID,
    memberships: List[dict],  # [{"user_id": UUID, "account_id": UUID, "role": str}]
    required_role: str = "TRADER",
) -> ValidationResult:
    """
    Verify the actor has the required role in the account.
    Actor identity derives from the server session — never from client payload.
    Returns NOT_FOUND (to avoid existence leak) when inaccessible.
    """
    for m in memberships:
        if m["user_id"] == user_id and m["account_id"] == account_id:
            if required_role == "READ_ONLY":
                return ValidationResult.ok()  # TRADER also satisfies READ_ONLY
            if m["role"] == required_role:
                return ValidationResult.ok()
            return ValidationResult.fail(
                "FORBIDDEN",
                f"Actor does not have role {required_role} on this account.",
                required_role=required_role,
                actual_role=m["role"],
            )
    # Return NOT_FOUND to avoid leaking account existence (API_CONTRACT §1)
    return ValidationResult.fail("NOT_FOUND", "Account not found or inaccessible.")


# ── 2. Proposal state and version (INV-04, INV-09) ───────────────────────────

def check_proposal_state(
    proposal_state: str,
    proposal_version: int,
    expected_version: int,
) -> ValidationResult:
    """
    Proposal must be READY and versions must match.
    A CONSUMED proposal means a duplicate approval attempt (INV-09).
    """
    if proposal_state != "READY":
        return ValidationResult.fail(
            "STATE_CONFLICT",
            f"Proposal is {proposal_state}, not READY.",
            proposal_state=proposal_state,
        )
    if proposal_version != expected_version:
        return ValidationResult.fail(
            "PROPOSAL_VERSION_CONFLICT",
            "Proposal version mismatch; reload the proposal before retrying.",
            expected_version=expected_version,
            actual_version=proposal_version,
        )
    return ValidationResult.ok()


# ── 3. Approval challenge hash (INV-04, INV-05) ──────────────────────────────

def check_approval_challenge(
    submitted_challenge: str,
    stored_challenge_hash: str,
) -> ValidationResult:
    """
    The server stores a hash of the challenge; the client submits the plaintext.
    We verify with a constant-time comparison to prevent timing attacks.
    (INV-05: only the approval endpoint creates approvals; chat never does.)
    """
    expected_hash = hashlib.sha256(submitted_challenge.encode()).hexdigest()
    if not hmac.compare_digest(expected_hash, stored_challenge_hash):
        return ValidationResult.fail(
            "APPROVAL_INVALID",
            "Approval challenge does not match.",
        )
    return ValidationResult.ok()


# ── 4. Approval expiry (INV-04) ──────────────────────────────────────────────

def check_approval_expiry(approval_expires_at: datetime) -> ValidationResult:
    """
    The proposal challenge must be activated before approval_expires_at.
    Uses UTC; clock-skew tolerance is NOT applied here — the server is authoritative.
    """
    now = datetime.now(timezone.utc)
    if now > approval_expires_at:
        return ValidationResult.fail(
            "APPROVAL_EXPIRED",
            "The approval window has expired. Review a fresh proposal.",
            expired_at=approval_expires_at.isoformat(),
            now=now.isoformat(),
        )
    return ValidationResult.ok()


# ── 5. Emergency stop (INV-22, INV-23) ───────────────────────────────────────

def check_emergency_stop(stop_active: bool) -> ValidationResult:
    """
    If stop_active is True, no new trading mutations are permitted.
    Alerts remain allowed. Stop does not cancel in-flight work.
    """
    if stop_active:
        return ValidationResult.fail(
            "STOP_ACTIVE",
            "Emergency stop is active. No new trading actions are permitted.",
        )
    return ValidationResult.ok()


# ── 6. Risk limits (INV-17, INV-20) ─────────────────────────────────────────

def check_order_quantity(quantity_units: int) -> ValidationResult:
    """
    Quantity must be a positive integer within the configured limit.
    Integer units — never lots; never floating point (INV-17).
    """
    if not isinstance(quantity_units, int) or isinstance(quantity_units, bool):
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            "quantity_units must be a positive integer (instrument units, not lots).",
            field="quantity_units",
        )
    if quantity_units < 1:
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            "quantity_units must be at least 1.",
            field="quantity_units",
            value=quantity_units,
        )
    if quantity_units > settings.MAX_ORDER_QUANTITY_UNITS:
        return ValidationResult.fail(
            "RISK_LIMIT_EXCEEDED",
            f"quantity_units {quantity_units} exceeds the maximum {settings.MAX_ORDER_QUANTITY_UNITS}.",
            field="quantity_units",
            limit=settings.MAX_ORDER_QUANTITY_UNITS,
        )
    return ValidationResult.ok()


def check_order_notional(quantity_units: int, limit_price: Decimal) -> ValidationResult:
    """
    Maximum notional = quantity_units × limit_price must not exceed configured cap.
    Decimal arithmetic only (INV-17).
    """
    notional = Decimal(quantity_units) * limit_price
    if notional > settings.MAX_ORDER_NOTIONAL_INR:
        return ValidationResult.fail(
            "RISK_LIMIT_EXCEEDED",
            f"Maximum notional {notional} exceeds the configured limit {settings.MAX_ORDER_NOTIONAL_INR}.",
            field="notional",
            limit=str(settings.MAX_ORDER_NOTIONAL_INR),
            computed=str(notional),
        )
    return ValidationResult.ok()


def check_limit_price(limit_price: Decimal) -> ValidationResult:
    """Limit price must be positive decimal. Never float. (INV-17)"""
    if not isinstance(limit_price, Decimal):
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            "limit_price must be a Decimal, not float. Use a string representation.",
            field="limit_price",
        )
    if limit_price <= Decimal("0"):
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            "limit_price must be greater than zero.",
            field="limit_price",
        )
    return ValidationResult.ok()


def check_available_funds(
    required_amount: Decimal,
    available_funds: Decimal,
    reserved_funds: Decimal,
) -> ValidationResult:
    """
    Capacity cannot be spent twice (INV-20).
    effective_available = available_funds - reserved_funds
    """
    effective = available_funds - reserved_funds
    if required_amount > effective:
        return ValidationResult.fail(
            "RISK_LIMIT_EXCEEDED",
            f"Insufficient funds. Required {required_amount}, effective available {effective}.",
            required=str(required_amount),
            effective_available=str(effective),
        )
    return ValidationResult.ok()


# ── 7. Quote freshness (INV-18) ───────────────────────────────────────────────

def check_quote_freshness(
    quote_market_timestamp: datetime,
    quote_received_at: datetime,
    max_quote_age_ms: int,
) -> ValidationResult:
    """
    A quote is actionable only if:
    - market_timestamp is not in the future (within clock-skew tolerance)
    - received_at - market_timestamp <= max_quote_age_ms

    Future, stale, disordered or unverifiable quotes are not actionable (INV-18).
    """
    now = datetime.now(timezone.utc)
    skew_tolerance_secs = settings.CLOCK_SKEW_TOLERANCE_SECONDS

    # Check market timestamp is not too far in the future
    if (quote_market_timestamp - now).total_seconds() > skew_tolerance_secs:
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            "Quote market timestamp is in the future; not actionable.",
            field="quote_market_timestamp",
        )

    # Check quote age
    age_ms = (quote_received_at - quote_market_timestamp).total_seconds() * 1000
    if age_ms < 0:
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            "Quote received_at is before market_timestamp; disordered evidence.",
            field="quote_received_at",
        )
    if age_ms > max_quote_age_ms:
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            f"Quote is stale: age {age_ms:.0f} ms exceeds limit {max_quote_age_ms} ms.",
            age_ms=int(age_ms),
            max_quote_age_ms=max_quote_age_ms,
        )
    return ValidationResult.ok()


def check_price_drift(
    current_price: Decimal,
    reference_price: Decimal,
    max_drift_bps: int,
) -> ValidationResult:
    """
    drift_bps = 10000 * |current - reference| / reference
    Decimal arithmetic only. Hold if drift exceeds max_drift_bps (INV-18/INV-19).
    """
    if reference_price <= Decimal("0"):
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            "Reference price must be positive to compute drift.",
            field="reference_price",
        )
    drift_bps = (Decimal("10000") * abs(current_price - reference_price) / reference_price).quantize(Decimal("1"))
    if drift_bps > max_drift_bps:
        return ValidationResult.fail(
            "VALIDATION_ERROR",
            f"Price drift {drift_bps} bps exceeds approved limit {max_drift_bps} bps.",
            drift_bps=int(drift_bps),
            max_drift_bps=max_drift_bps,
        )
    return ValidationResult.ok()


# ── 8. Interpretation agreement (INV-06) ─────────────────────────────────────

def check_parser_agreement(parser_report: dict) -> ValidationResult:
    """
    Both Gemini and the deterministic parser must agree before a proposal is admissible.
    Disagreement fields must be surfaced for clarification — never silently merged (INV-06).
    """
    status = parser_report.get("status")
    if status != "MATCH":
        disagreement_fields = parser_report.get("disagreement_fields", [])
        unsupported_fields  = parser_report.get("unsupported_fields",  [])
        return ValidationResult.fail(
            "INTERPRETATION_UNVERIFIED",
            "Gemini and deterministic parsers disagree. Clarify before approving.",
            disagreement_fields=disagreement_fields,
            unsupported_fields=unsupported_fields,
        )
    return ValidationResult.ok()


# ── 9. Trading mode guard ─────────────────────────────────────────────────────

def check_trading_mode_is_simulator() -> ValidationResult:
    """
    This prototype only supports SIMULATOR mode (AGENTS.md rule 8).
    Fail explicitly if misconfigured to prevent accidental live trades.
    """
    if settings.TRADING_MODE != "SIMULATOR":
        return ValidationResult.fail(
            "CAPABILITY_UNAVAILABLE",
            f"This prototype only supports SIMULATOR mode. Current mode: {settings.TRADING_MODE}.",
        )
    return ValidationResult.ok()
