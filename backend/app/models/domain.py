import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, String, Integer, DateTime, Numeric, Boolean, ForeignKey, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_provider_subject = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, nullable=False)
    csrf_secret_ref = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_connection_ref = Column(String, nullable=False)
    mode = Column(String, nullable=False) # SIMULATOR, ORGANIZER_SANDBOX, LIVE
    currency = Column(String, nullable=False)
    account_display_label = Column(String, nullable=False)

class AccountMembership(Base):
    __tablename__ = "account_memberships"
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    role = Column(String, nullable=False) # TRADER, READ_ONLY

class AccountControl(Base):
    __tablename__ = "account_controls"
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), primary_key=True)
    stop_active = Column(Boolean, default=False, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    reason = Column(String, nullable=True)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), default=utc_now)

class Instrument(Base):
    __tablename__ = "instruments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_instrument_ref = Column(String, nullable=False)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    asset_type = Column(String, nullable=False)
    underlying = Column(String, nullable=True)
    expiry = Column(DateTime(timezone=True), nullable=True)
    option_type = Column(String, nullable=True)
    strike = Column(Numeric, nullable=True)
    lot_size = Column(Integer, nullable=False)
    tick_size = Column(Numeric, nullable=False)
    catalogue_version = Column(Integer, nullable=False, default=1)

class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    source_revision = Column(String, nullable=False)
    as_of = Column(DateTime(timezone=True), nullable=False)
    cash_available = Column(Numeric, nullable=False)
    source = Column(String, nullable=False)
    quality = Column(String, nullable=False)
    basis = Column(String, nullable=False)

class Proposal(Base):
    __tablename__ = "proposals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    message_id = Column(UUID(as_uuid=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    kind = Column(String, nullable=False) # PLACE_ORDER, MODIFY_ORDER, CANCEL_ORDER, CREATE_RULE, CREATE_PLAN
    state = Column(String, nullable=False) # READY, CONSUMED, SUPERSEDED, EXPIRED
    terms_schema_version = Column(Integer, nullable=False, default=1)
    canonical_terms = Column(JSONB, nullable=False)
    terms_hash = Column(String, nullable=False)
    parser_report = Column(JSONB, nullable=False)
    preview = Column(JSONB, nullable=False)
    approval_challenge_hash = Column(String, nullable=False)
    approval_expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, unique=True)
    proposal_version = Column(Integer, nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    terms_hash = Column(String, nullable=False)
    approved_at = Column(DateTime(timezone=True), default=utc_now)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    state = Column(String, nullable=False) # ACTIVE, REVOKED

class Operation(Base):
    __tablename__ = "operations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("approvals.id"), nullable=False)
    action_identity = Column(String, nullable=False, unique=True)
    action = Column(String, nullable=False)
    immutable_terms = Column(JSONB, nullable=False)
    state = Column(String, nullable=False) # READY, SUBMITTING, UNKNOWN, ACKNOWLEDGED, REJECTED, HELD, BLOCKED, SUPERSEDED
    hold_code = Column(String, nullable=True)
    rule_firing_id = Column(UUID(as_uuid=True), nullable=True)
    plan_leg_id = Column(UUID(as_uuid=True), nullable=True)
    broker_order_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    version = Column(Integer, nullable=False, default=1)

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("approvals.id"), nullable=False)
    operation_id = Column(UUID(as_uuid=True), ForeignKey("operations.id"), nullable=True)
    plan_id = Column(UUID(as_uuid=True), nullable=True)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=True)
    kind = Column(String, nullable=False) # FUNDS, INVENTORY
    amount = Column(Numeric, nullable=True)
    quantity_units = Column(Integer, nullable=True)
    state = Column(String, nullable=False) # ACTIVE, TRANSFERRED, RELEASED
