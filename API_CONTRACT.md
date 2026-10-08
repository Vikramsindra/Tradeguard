# TradeGuard application API contract

Version 1.0 | Proposed FastAPI interface | Base path /api/v1

**These are TradeGuard routes, not verified 021 endpoints.** The broker adapter is private to the protected execution boundary. All fields and states must agree with [DATA_MODEL.md](DATA_MODEL.md) and [INVARIANTS.md](INVARIANTS.md).

## 1 Global conventions

- JSON over HTTPS when hosted. UUID IDs, UTC ISO 8601 timestamps, decimal strings for prices/money and integer quantity_units.
- Server authenticates an HttpOnly, Secure session cookie with appropriate SameSite settings. Cookie-authenticated mutations require X-CSRF-Token and permitted Origin. WebSocket handshake validates session and Origin.
- Account paths select an account but do not authorize it. Check session membership and role on every object and stream. Return 404 for inaccessible object references to avoid exposing their existence.
- Strict request models reject extra fields. Client actor IDs, raw broker payloads and replacement terms in approval requests are prohibited.
- GET is read-only. Explicit authenticated controls authorize trading or policy changes; chat does not.
- Idempotency-Key is required on POST mutations and retained at least for the resource life in this prototype. Scope it to actor, account, route and request body digest. Same key/body returns original result; changed body returns IDEMPOTENCY_CONFLICT. Approval and parent uniqueness also prevent duplicates with different keys.
- Bound request sizes, chat text length and rate limits. Page list results using opaque cursor and a documented max limit; do not expose raw database queries.
- Include account mode and object versions in responses. Idempotent response replay is followed by a state reload if status has evolved.

### Errors

```json
{
  "error": {
    "code": "APPROVAL_EXPIRED",
    "message": "Review a fresh proposal before approving.",
    "request_id": "9c98f582-c04a-414b-95f6-d7506306978b",
    "details": {"proposal_version": 1}
  }
}
```

HTTP mapping: 401 unauthenticated; 403 CSRF/role/control denial; 404 missing or inaccessible resource; 409 version, state or idempotency conflict; 422 invalid or unsupported request; 429 rate limit; 503 dependency/data unavailable. Do not leak secret-bearing broker responses in errors. An asynchronous rejected trade is an operation outcome, not a retroactive HTTP approval failure.

## 2 Session and capabilities

| Method and route | Behaviour |
|---|---|
| GET /session | Authenticated actor, authorized account summaries, CSRF token and session expiry; Cache-Control no-store |
| POST /session/logout | Revoke session; protected against CSRF |
| GET /accounts/{account_id}/capabilities | Current mode, supported actions/types/products/validities, feed quality and verification status |

Authentication login depends on the chosen provider and is deliberately not invented here. A development demo identity must be simulator-only, inaccessible in live mode and visibly labelled. Capability response separates VERIFIED, SIMULATED and UNAVAILABLE, with evidence references where applicable. Unsupported modify/cancel capability is not silently emulated as a different action.

## 3 Read-only data and chat

| Route | Response meaning |
|---|---|
| GET /accounts/{account_id}/summary | Funds, reservations, positions, P&L availability and basis |
| GET /accounts/{account_id}/positions?loss_basis=AVG_ENTRY&down_more_than_pct=5 | Supported holdings with threshold basis and timestamps |
| GET /accounts/{account_id}/instruments?query=... | Catalogue identities and metadata; escaped display text |
| GET /accounts/{account_id}/option-chain?underlying=NIFTY&expiry=YYYY-MM-DD | Actual contracts near the money, chosen expiry and quote quality |
| GET /accounts/{account_id}/orders | Paginated broker-order projections, separate filled and remaining quantities |
| GET /accounts/{account_id}/orders/{order_id} | Current target version, actual terms, fills and evidence quality |
| POST /accounts/{account_id}/chat/messages | Store original message; return answer, clarification or approvable proposal reference |

Chat request contains conversation_id (nullable for a new conversation) and text. No executable terms or approvals are accepted. The response type is READ_RESULT, CLARIFICATION or PROPOSAL. An approved action cannot be created by “yes” in text.

READ_RESULT contains query_type, result, basis, source, as_of, quality and unavailable_reason where needed. CLARIFICATION contains question and parser_report with disagreement/unsupported fields. PROPOSAL contains proposal_id and version. Multi-step text returns one CREATE_PLAN proposal, not several individually approved cards.

## 4 Proposal retrieval and revision

| Method and route | Behaviour |
|---|---|
| GET /accounts/{account_id}/proposals/{proposal_id} | Stored exact terms, parser report, preview, version, state and approval expiry |
| POST /accounts/{account_id}/proposals/{proposal_id}/revisions | Create immutable replacement from original-text clarification and expected_version; old READY proposal becomes SUPERSEDED |
| POST /accounts/{account_id}/operations/{operation_id}/review | For provably unsent HELD work only, create fresh proposal and retire old operation atomically; new approval required |

Proposal revision request contains expected_version and clarification_text. It does not mutate approved terms in place. Revision of a CONSUMED proposal returns STATE_CONFLICT; use a new request and explicit supported review flow. UNKNOWN or SUBMITTING work cannot be retired through review.

Illustrative simulator proposal, not a real quote:

```json
{
  "proposal_id": "38aa5d86-9305-4ed0-b82e-85c20d064e69",
  "version": 1,
  "kind": "PLACE_ORDER",
  "state": "READY",
  "mode": "SIMULATOR",
  "terms": {
    "terms_schema_version": 1,
    "account_id": "bb8acdf9-9cde-4be3-9804-0e867cc19bbd",
    "mode": "SIMULATOR",
    "action": "PLACE_ORDER",
    "instrument_id": "c59386db-a180-49b0-bf25-6053a0a99615",
    "side": "BUY",
    "quantity_units": 6,
    "order_type": "LIMIT",
    "limit_price": "1500.00",
    "product": "SIM_CASH",
    "time_in_force": "SIM_DAY",
    "valid_until": "2026-10-09T04:30:00Z",
    "quote_policy": {
      "reference_kind": "SNAPSHOT",
      "snapshot_quote_id": "8f31721a-f038-4d80-9713-f00d739ffb77",
      "max_quote_age_ms": 5000,
      "max_drift_bps": 50
    }
  },
  "parser_report": {"status": "MATCH", "disagreement_fields": []},
  "preview": {
    "maximum_notional": "9000.00",
    "currency": "INR",
    "fees_included": false,
    "assumes_full_fill": true,
    "source": "SIMULATOR"
  },
  "approval_challenge": "opaque-server-generated-value",
  "approval_expires_at": "2026-10-08T16:00:00Z"
}
```

SIM_CASH and SIM_DAY are simulator-only labels. Quote-age and drift values above are examples, not verified market recommendations. Quote reference, full fee assumptions and portfolio data are included in a complete preview response. Server stores the challenge hash; the challenge is not sufficient authority without a valid session and ownership. Standing trades use reference_kind=RULE_THRESHOLD with their approved reference_price instead of a snapshot_quote_id, as defined in DATA_MODEL.md.

## 5 Exact approval

POST /accounts/{account_id}/proposals/{proposal_id}/approve

```json
{
  "expected_version": 1,
  "approval_challenge": "opaque-server-generated-value"
}
```

The server reloads immutable terms; validates actor/account, challenge, expiry, version, supported capability and policy; consumes the proposal once; then commits approval and the bounded result with reservations and audit evidence. It accepts no client order terms or actor ID.

Return 202 with approval_id, proposal_id, proposal_version, resource_type, resource_id, mode and status_url. resource_type is OPERATION for direct actions, RULE for standing instructions or PLAN for plans. 202 means accepted for processing/activation, not broker acceptance or fill.

Same proposal approval returns the same resource even if the client changes its idempotency key. Validate ownership before returning an existing result. A different expected version or altered challenge returns conflict. Error codes include APPROVAL_EXPIRED, PROPOSAL_VERSION_CONFLICT, APPROVAL_INVALID, INTERPRETATION_UNVERIFIED, RISK_LIMIT_EXCEEDED, STOP_ACTIVE and CAPABILITY_UNAVAILABLE.

Plan approval pins the full plan and reserves conservative capacity. Rule activation pins its one bounded action but reserves trading capacity at firing. Alerts may activate during stop. Trading rules, plans and direct mutations cannot activate/admit while stop is active.

## 6 Operations and receipts

| Method and route | Behaviour |
|---|---|
| GET /accounts/{account_id}/operations/{operation_id} | Operation state, authorization reference, hold/reject reason and linked broker-order state |
| GET /accounts/{account_id}/operations/{operation_id}/receipt | Sanitized approval, terms, checks, attempts and outcomes |
| POST /accounts/{account_id}/operations/{operation_id}/reconcile | Request lookup of original UNKNOWN/SUBMITTING outcome; never direct resubmission |

Reconcile requires TRADER role, CSRF and rate limiting; returns 202 for a bounded reconciliation request. It cannot change approved terms or reset UNKNOWN to READY. READY operation status is separate from broker_order.status. Cancel/modify operations reference the original broker order rather than fabricate a new order.

## 7 Rules and plans

| Route | Behaviour |
|---|---|
| GET /accounts/{account_id}/rules | Persisted rules, conditions, last usable tick and firing/outcome references |
| GET /accounts/{account_id}/rules/{rule_id} | Exact authorization, lifecycle and distinct execution/fill state |
| POST /accounts/{account_id}/rules/{rule_id}/pause | expected_version; restrict unsent future firing |
| POST /accounts/{account_id}/rules/{rule_id}/resume | expected_version; only PAUSED, unconsumed, unexpired authorized rule; stop blocks trading resume |
| GET /accounts/{account_id}/plans | Full approved plans with leg and dependency outcomes |
| GET /accounts/{account_id}/plans/{plan_id} | All exact legs, reservations and actual fills |

Create/change rule or plan terms only through chat proposal and exact approval. Resume never re-arms CONSUMED rules. Rule pause serializes with firing; an already consumed operation may remain in flight. Plans held on partial/unknown results do not auto-resume. A recovery action is a new exact proposal. This version provides no blanket plan-cancel route that could silently cancel open broker orders.

## 8 Risk and emergency stop

GET /accounts/{account_id}/risk-profile returns current immutable version, caps, reservation accounting policy and supported position limits.

POST /accounts/{account_id}/controls/emergency-stop accepts reason and immediately persists stop_active=true. It intentionally requires no optimistic version so a stale screen cannot prevent stopping; repeated requests are idempotent. The response contains control_version, effective_at and in_flight_operation_ids.

POST /accounts/{account_id}/controls/resume-trading accepts expected_control_version and explicit acknowledgement of outstanding exposure. It requires a currently authenticated TRADER, CSRF and recent authentication under the selected provider. It sets stop_active=false, not approval for new trades. HELD work stays held.

No prototype endpoint silently weakens risk limits. Versioned risk policy changes require a separately reviewed administrative process. Stop blocks new broker mutations including cancel/modify; informational alerts remain active. Stop cannot retract already admitted network work or reverse fills.

## 9 Event stream

GET /accounts/{account_id}/events?after_sequence=N returns durable sanitized events for authorized catch-up. WS /api/v1/accounts/{account_id}/events sends the same envelopes after authenticated handshake. Credentials and challenge values are excluded.

Envelope fields: event_id, account_id, sequence, type, object_id, object_version, committed_at and payload. Types include proposal.created, approval.consumed, operation.updated, order.updated, rule.updated, plan.updated, alert.created and control.updated.

Delivery is at least once where available, not a guaranteed transport contract. Duplicate event_id is ignored. A sequence gap or reconnect triggers HTTP reload/catch-up. Events never approve transactions and browser acknowledgment is not broker acknowledgment. Close subscriptions when authorization or session is revoked.

## 10 Safety Arena

POST /accounts/{account_id}/arena/runs accepts scenario from an allowlist; GET /accounts/{account_id}/arena/runs/{run_id} returns evidence and observed results. Both are restricted to authenticated SIMULATOR accounts with explicit Arena permission; inaccessible in sandbox/live mode.

Supported scenario names: INTERPRETATION_MISMATCH, APPROVAL_REPLAY, LOST_BROKER_REPLY, MALICIOUS_DISPLAY_NAME, RULE_RESTART and PARTIAL_PLAN. A run references isolated objects and any explicit approvals required for its synthetic trader flow. It cannot forge approval on behalf of a real user or call a real broker.

Results include injected_faults, expected_result, observed_result, assertion_results, accepted_action_count and status RUNNING/PASSED/FAILED/INCONCLUSIVE. Mark a missing dependency INCONCLUSIVE rather than green. Scenario orchestration exercises ordinary services and may not bypass their gates.

## 11 Private adapter interface

Application services use internal read_snapshot, resolve_instrument, read_quote, submit_exact_action, lookup_original_action and read_order_evidence capabilities. These are conceptual method responsibilities, not asserted 021 endpoints. Only verified implementations may map them to broker calls.

submit_exact_action outcomes are ACKNOWLEDGED, DEFINITIVELY_REJECTED or UNCERTAIN, supported by evidence. Reconciliation records lookup consistency and original caller identity. Capability gaps keep the action unavailable or UNKNOWN; local application enums must not overwrite different broker meanings.
