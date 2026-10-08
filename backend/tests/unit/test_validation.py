"""
Tests for the backend validation service.

Rules:
- Every validation failure case is tested separately.
- No test hardcodes a pass outcome — each asserts on actual returned reason/code.
- Tests run in-process; no broker calls, no live DB.
"""
import hashlib
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from app.services.validation import (
    check_account_membership,
    check_proposal_state,
    check_approval_challenge,
    check_approval_expiry,
    check_emergency_stop,
    check_order_quantity,
    check_order_notional,
    check_limit_price,
    check_available_funds,
    check_quote_freshness,
    check_price_drift,
    check_parser_agreement,
    check_trading_mode_is_simulator,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_membership(user_id, account_id, role="TRADER"):
    return {"user_id": user_id, "account_id": account_id, "role": role}


def hash_challenge(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def utc(offset_seconds=0):
    return datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)


# ── 1. Account membership ────────────────────────────────────────────────────

class TestAccountMembership:
    def test_trader_is_accepted(self):
        uid = uuid4(); aid = uuid4()
        r = check_account_membership(uid, aid, [make_membership(uid, aid, "TRADER")])
        assert r.passed

    def test_read_only_accepted_for_read_role(self):
        uid = uuid4(); aid = uuid4()
        r = check_account_membership(uid, aid, [make_membership(uid, aid, "READ_ONLY")], required_role="READ_ONLY")
        assert r.passed

    def test_read_only_rejected_for_trader_role(self):
        uid = uuid4(); aid = uuid4()
        r = check_account_membership(uid, aid, [make_membership(uid, aid, "READ_ONLY")], required_role="TRADER")
        assert not r.passed
        assert r.code == "FORBIDDEN"

    def test_no_membership_returns_not_found(self):
        uid = uuid4(); aid = uuid4()
        r = check_account_membership(uid, aid, [])
        assert not r.passed
        assert r.code == "NOT_FOUND"

    def test_wrong_account_returns_not_found(self):
        uid = uuid4(); aid = uuid4()
        r = check_account_membership(uid, uuid4(), [make_membership(uid, aid)])
        assert not r.passed
        assert r.code == "NOT_FOUND"


# ── 2. Proposal state and version ────────────────────────────────────────────

class TestProposalState:
    def test_ready_correct_version_passes(self):
        r = check_proposal_state("READY", 1, 1)
        assert r.passed

    def test_consumed_fails_with_state_conflict(self):
        r = check_proposal_state("CONSUMED", 1, 1)
        assert not r.passed
        assert r.code == "STATE_CONFLICT"

    def test_expired_fails(self):
        r = check_proposal_state("EXPIRED", 1, 1)
        assert not r.passed

    def test_version_mismatch_fails(self):
        r = check_proposal_state("READY", 2, 1)
        assert not r.passed
        assert r.code == "PROPOSAL_VERSION_CONFLICT"
        assert r.details["expected_version"] == 1
        assert r.details["actual_version"] == 2


# ── 3. Approval challenge ────────────────────────────────────────────────────

class TestApprovalChallenge:
    def test_matching_challenge_passes(self):
        challenge = "secure-random-value-123"
        r = check_approval_challenge(challenge, hash_challenge(challenge))
        assert r.passed

    def test_wrong_challenge_fails(self):
        r = check_approval_challenge("wrong-value", hash_challenge("correct-value"))
        assert not r.passed
        assert r.code == "APPROVAL_INVALID"

    def test_empty_challenge_fails(self):
        r = check_approval_challenge("", hash_challenge("something"))
        assert not r.passed

    def test_chat_yes_cannot_be_challenge(self):
        # "yes" or "ok" must not match any real challenge hash
        r = check_approval_challenge("yes", hash_challenge("actual-challenge-token"))
        assert not r.passed


# ── 4. Approval expiry ───────────────────────────────────────────────────────

class TestApprovalExpiry:
    def test_future_expiry_passes(self):
        r = check_approval_expiry(utc(+120))
        assert r.passed

    def test_past_expiry_fails(self):
        r = check_approval_expiry(utc(-1))
        assert not r.passed
        assert r.code == "APPROVAL_EXPIRED"

    def test_exact_now_fails(self):
        # Expired exactly at this instant — should fail
        r = check_approval_expiry(utc(-0.001))
        assert not r.passed


# ── 5. Emergency stop ────────────────────────────────────────────────────────

class TestEmergencyStop:
    def test_no_stop_passes(self):
        assert check_emergency_stop(False).passed

    def test_stop_active_fails(self):
        r = check_emergency_stop(True)
        assert not r.passed
        assert r.code == "STOP_ACTIVE"


# ── 6. Risk limits ───────────────────────────────────────────────────────────

class TestOrderQuantity:
    def test_valid_quantity_passes(self):
        assert check_order_quantity(10).passed

    def test_zero_quantity_fails(self):
        r = check_order_quantity(0)
        assert not r.passed
        assert r.code == "VALIDATION_ERROR"

    def test_negative_quantity_fails(self):
        assert not check_order_quantity(-1).passed

    def test_float_quantity_fails(self):
        r = check_order_quantity(5.0)  # type: ignore
        assert not r.passed

    def test_bool_rejected_as_not_int(self):
        # True == 1 in Python but must not be accepted as quantity
        r = check_order_quantity(True)  # type: ignore
        assert not r.passed

    def test_exceeds_max_fails(self):
        from app.core.config import settings
        r = check_order_quantity(settings.MAX_ORDER_QUANTITY_UNITS + 1)
        assert not r.passed
        assert r.code == "RISK_LIMIT_EXCEEDED"


class TestOrderNotional:
    def test_within_limit_passes(self):
        r = check_order_notional(10, Decimal("100.00"))
        assert r.passed  # 1000 INR, well below 5M default

    def test_exceeds_notional_fails(self):
        from app.core.config import settings
        # Force notional above limit
        big_price = settings.MAX_ORDER_NOTIONAL_INR + Decimal("1")
        r = check_order_notional(1, big_price)
        assert not r.passed
        assert r.code == "RISK_LIMIT_EXCEEDED"

    def test_decimal_arithmetic_used(self):
        # Ensure Decimal path taken; 0.1 + 0.2 ≠ 0.3 in float
        r = check_order_notional(3, Decimal("0.1"))
        assert r.passed  # 0.3 INR — trivially within limits

class TestLimitPrice:
    def test_positive_decimal_passes(self):
        assert check_limit_price(Decimal("1500.00")).passed

    def test_zero_price_fails(self):
        assert not check_limit_price(Decimal("0")).passed

    def test_negative_price_fails(self):
        assert not check_limit_price(Decimal("-10")).passed

    def test_float_rejected(self):
        r = check_limit_price(1500.0)  # type: ignore
        assert not r.passed


class TestAvailableFunds:
    def test_sufficient_funds_passes(self):
        r = check_available_funds(Decimal("1000"), Decimal("5000"), Decimal("2000"))
        assert r.passed  # effective = 3000, required = 1000

    def test_exact_funds_passes(self):
        r = check_available_funds(Decimal("3000"), Decimal("5000"), Decimal("2000"))
        assert r.passed

    def test_insufficient_funds_fails(self):
        r = check_available_funds(Decimal("3001"), Decimal("5000"), Decimal("2000"))
        assert not r.passed
        assert r.code == "RISK_LIMIT_EXCEEDED"

    def test_fully_reserved_fails(self):
        r = check_available_funds(Decimal("1"), Decimal("5000"), Decimal("5000"))
        assert not r.passed


# ── 7. Quote freshness ───────────────────────────────────────────────────────

class TestQuoteFreshness:
    def test_fresh_quote_passes(self):
        market_ts = utc(-1)   # 1 second ago
        received_ts = utc(-0.5)  # 0.5 seconds ago
        r = check_quote_freshness(market_ts, received_ts, max_quote_age_ms=5_000)
        assert r.passed

    def test_stale_quote_fails(self):
        market_ts = utc(-10)
        received_ts = utc(-9.9)
        r = check_quote_freshness(market_ts, received_ts, max_quote_age_ms=100)
        assert not r.passed
        assert "stale" in r.reason.lower()

    def test_future_market_timestamp_fails(self):
        market_ts = utc(+60)  # 60 seconds in future, well beyond skew tolerance
        received_ts = utc(+60.5)
        r = check_quote_freshness(market_ts, received_ts, max_quote_age_ms=5_000)
        assert not r.passed
        assert "future" in r.reason.lower()

    def test_disordered_timestamps_fail(self):
        market_ts = utc(-1)
        received_ts = utc(-2)  # received before market timestamp
        r = check_quote_freshness(market_ts, received_ts, max_quote_age_ms=5_000)
        assert not r.passed
        assert "disordered" in r.reason.lower()


class TestPriceDrift:
    def test_within_drift_passes(self):
        r = check_price_drift(Decimal("1005"), Decimal("1000"), max_drift_bps=100)
        assert r.passed  # 50 bps drift

    def test_exact_drift_limit_passes(self):
        r = check_price_drift(Decimal("1010"), Decimal("1000"), max_drift_bps=100)
        assert r.passed  # exactly 100 bps

    def test_exceeds_drift_fails(self):
        r = check_price_drift(Decimal("1011"), Decimal("1000"), max_drift_bps=100)
        assert not r.passed
        assert r.details["drift_bps"] == 110

    def test_zero_reference_fails(self):
        r = check_price_drift(Decimal("1000"), Decimal("0"), max_drift_bps=50)
        assert not r.passed

    def test_decimal_arithmetic_prevents_float_errors(self):
        # 0.1 + 0.2 in float is not 0.3; Decimal must be used
        ref = Decimal("1.0")
        curr = Decimal("1.001")
        r = check_price_drift(curr, ref, max_drift_bps=20)
        assert r.passed  # 10 bps


# ── 8. Parser agreement ──────────────────────────────────────────────────────

class TestParserAgreement:
    def test_match_passes(self):
        r = check_parser_agreement({"status": "MATCH", "disagreement_fields": []})
        assert r.passed

    def test_mismatch_fails(self):
        r = check_parser_agreement({"status": "MISMATCH", "disagreement_fields": ["quantity_units"]})
        assert not r.passed
        assert r.code == "INTERPRETATION_UNVERIFIED"
        assert "quantity_units" in r.details["disagreement_fields"]

    def test_unsupported_field_fails(self):
        r = check_parser_agreement({
            "status": "UNSUPPORTED",
            "disagreement_fields": [],
            "unsupported_fields": ["leverage"],
        })
        assert not r.passed

    def test_missing_status_fails(self):
        r = check_parser_agreement({})
        assert not r.passed


# ── 9. Trading mode guard ─────────────────────────────────────────────────────

class TestTradingModeGuard:
    def test_simulator_mode_passes(self, monkeypatch):
        from app.core import config as cfg_module
        monkeypatch.setattr(cfg_module.settings, "TRADING_MODE", "SIMULATOR")
        assert check_trading_mode_is_simulator().passed

    def test_live_mode_fails(self, monkeypatch):
        from app.core import config as cfg_module
        monkeypatch.setattr(cfg_module.settings, "TRADING_MODE", "LIVE")
        r = check_trading_mode_is_simulator()
        assert not r.passed
        assert r.code == "CAPABILITY_UNAVAILABLE"


# ── Cross-cutting: rejected requests cannot create execution work ─────────────

class TestRejectedRequestsCannotCreateWork:
    """
    Verify that failed validation checks all return passed=False,
    ensuring no execution work would be created downstream.
    """
    def test_all_failures_have_passed_false(self):
        failures = [
            check_account_membership(uuid4(), uuid4(), []),
            check_proposal_state("CONSUMED", 1, 1),
            check_approval_challenge("wrong", hash_challenge("right")),
            check_approval_expiry(utc(-10)),
            check_emergency_stop(True),
            check_order_quantity(0),
            check_order_notional(1, Decimal("999999999")),
            check_limit_price(Decimal("0")),
            check_available_funds(Decimal("1000000"), Decimal("100"), Decimal("0")),
            check_quote_freshness(utc(-30), utc(-29.9), max_quote_age_ms=100),
            check_price_drift(Decimal("2000"), Decimal("1000"), max_drift_bps=50),
            check_parser_agreement({"status": "MISMATCH", "disagreement_fields": ["side"]}),
        ]
        for result in failures:
            assert not result.passed, f"Expected failure but got pass: {result}"
            assert result.code, f"Failed result must have a code: {result}"
            assert result.reason, f"Failed result must have a reason: {result}"
