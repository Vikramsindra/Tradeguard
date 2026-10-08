"""
Structured error helpers matching API_CONTRACT.md §1 error envelope.

All error responses use the shape:
  { "error": { "code": str, "message": str, "request_id": str, "details": dict } }

Never include secret values in error details.
"""
from __future__ import annotations
from typing import Any
from fastapi import Request, status
from fastapi.responses import JSONResponse

# ── Canonical error codes (API_CONTRACT §1) ──────────────────────────────────
APPROVAL_EXPIRED          = "APPROVAL_EXPIRED"
PROPOSAL_VERSION_CONFLICT = "PROPOSAL_VERSION_CONFLICT"
APPROVAL_INVALID          = "APPROVAL_INVALID"
INTERPRETATION_UNVERIFIED = "INTERPRETATION_UNVERIFIED"
RISK_LIMIT_EXCEEDED       = "RISK_LIMIT_EXCEEDED"
STOP_ACTIVE               = "STOP_ACTIVE"
CAPABILITY_UNAVAILABLE    = "CAPABILITY_UNAVAILABLE"
STATE_CONFLICT            = "STATE_CONFLICT"
IDEMPOTENCY_CONFLICT      = "IDEMPOTENCY_CONFLICT"
INTERNAL_SERVER_ERROR     = "INTERNAL_SERVER_ERROR"
VALIDATION_ERROR          = "VALIDATION_ERROR"
UNAUTHORIZED              = "UNAUTHORIZED"
FORBIDDEN                 = "FORBIDDEN"
NOT_FOUND                 = "NOT_FOUND"
RATE_LIMITED              = "RATE_LIMITED"
DEPENDENCY_UNAVAILABLE    = "DEPENDENCY_UNAVAILABLE"


def _request_id(request: Request | None) -> str:
    if request is None:
        return "unknown"
    return getattr(request.state, "request_id", "unknown")


def error_response(
    status_code: int,
    code: str,
    message: str,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Return a JSON error response matching API_CONTRACT §1."""
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": _request_id(request),
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


# ── Convenience constructors ──────────────────────────────────────────────────

def approval_expired(request: Request | None = None, **details: Any) -> JSONResponse:
    return error_response(
        status.HTTP_409_CONFLICT, APPROVAL_EXPIRED,
        "The approval window has expired. Review a fresh proposal before approving.",
        request, details or None,
    )

def proposal_version_conflict(expected: int, actual: int, request: Request | None = None) -> JSONResponse:
    return error_response(
        status.HTTP_409_CONFLICT, PROPOSAL_VERSION_CONFLICT,
        "Proposal version mismatch. Reload the proposal before retrying.",
        request, {"expected_version": expected, "actual_version": actual},
    )

def approval_invalid(reason: str, request: Request | None = None) -> JSONResponse:
    return error_response(
        status.HTTP_403_FORBIDDEN, APPROVAL_INVALID,
        f"Approval is invalid: {reason}.",
        request,
    )

def risk_limit_exceeded(field: str, limit: str, request: Request | None = None) -> JSONResponse:
    return error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY, RISK_LIMIT_EXCEEDED,
        f"Risk limit exceeded for {field}. Maximum allowed: {limit}.",
        request, {"field": field, "limit": limit},
    )

def stop_active(request: Request | None = None) -> JSONResponse:
    return error_response(
        status.HTTP_403_FORBIDDEN, STOP_ACTIVE,
        "Emergency stop is active. No new trading actions are permitted.",
        request,
    )

def validation_error(reason: str, field: str | None = None, request: Request | None = None) -> JSONResponse:
    details: dict[str, Any] = {"reason": reason}
    if field:
        details["field"] = field
    return error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY, VALIDATION_ERROR,
        reason, request, details,
    )

def not_found(resource: str, request: Request | None = None) -> JSONResponse:
    return error_response(
        status.HTTP_404_NOT_FOUND, NOT_FOUND,
        f"{resource} not found or inaccessible.",
        request,
    )

def dependency_unavailable(dep: str, request: Request | None = None) -> JSONResponse:
    return error_response(
        status.HTTP_503_SERVICE_UNAVAILABLE, DEPENDENCY_UNAVAILABLE,
        f"Required dependency unavailable: {dep}.",
        request,
    )
