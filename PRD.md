# TradeGuard product requirements

Version 1.0 | Proposed prototype specification | 8 October 2026

## 1 Product goal

TradeGuard lets a trader query their 021 account and propose financial actions through web chat. It separates language interpretation from authorization and execution. Every mutation must be covered by an exact authenticated approval, including a previously approved bounded standing rule or complete plan.

The scope of this safety property is TradeGuard's trusted execution boundary, assuming its application, session, database and worker controls remain intact. It does not cover external account activity, compromised trusted infrastructure, investment outcomes or broker violations. The prototype must demonstrate controls rather than advertise an absolute guarantee.

## 2 Requirements from PS 04

| ID | Requirement | Required behaviour |
|---|---|---|
| FR-01 | Read-only queries | Today's P&L, positions down over 5%, average purchase price and nearby NIFTY options for a selected expiry |
| FR-02 | Order actions | Place, modify and cancel only after display and approval of the exact action |
| FR-03 | Standing instructions | Fresh feed evaluation, persistence across restart and one logical firing per approved condition |
| FR-04 | Multi-step plans | Whole-plan approval and truthful per-leg partial-fill and rejection reporting |
| FR-05 | Web chat | Connected trader interface for conversation, approvals and persistent outcomes |

## 3 Trader experience

The workspace contains chat, the selected account, data-mode indicator, account summary and tabs for orders, rules, plans and Safety Arena. Emergency stop and feed health remain visible. The trader can distinguish proposal, approval, submission, acknowledgement and fill.

### Read queries

Calculations and instrument filtering run in deterministic backend code. The model may choose the query and explain its results. Each answer carries its calculation basis, source, timestamps, data quality and fee assumptions.

For positions down more than 5%, default to current price versus average entry price and show the basis. Only apply this formula to supported long holdings with a valid positive entry price; unsupported positions are identified separately. Today's P&L needs a defined trading-day baseline and cash-flow/charge treatment. Missing inputs produce UNAVAILABLE, not a fabricated value or relabelled cumulative P&L.

NIFTY results must refer to a chosen expiry and actual catalogue contracts, with strike, option type, expiry, tradable units and quote age. Use verified metadata, not assumed calendars or lot sizes.

### Exact order actions

Resolve a stable instrument and, for modify/cancel, a specific existing order. Unsupported wording, missing fields or ambiguous targets require clarification. Initial support is LIMIT orders in a disclosed instrument universe. Broker-dependent products and validity types are supported only after verification.

The card displays account, action, instrument identity, side, quantity in instrument units, lot interpretation where relevant, LIMIT price, supported product and validity, execution deadline, quote snapshot and drift policy. Modification shows old and new terms plus the target revision. Cancellation displays the exact target and unfilled quantity observed at preview; an intervening target change holds the action for renewed review.

The trader approves this card through a protected control. Ordinary chat text such as “yes” does not authorize execution. Editing terms creates a new immutable proposal version. Expired or changed cards cannot be approved. Repeated approval returns the original authorization result.

### Persistent standing instructions

A rule card includes condition, instrument, reference basis, action, quantity, LIMIT, per-rule cap, start/expiry and trigger mode. Support BUY below a price and alert on a percentage fall. Percentage alerts pin an explicit positive reference value and timestamp.

Trigger modes are IMMEDIATE_IF_TRUE or FUTURE_CROSSING. For FUTURE_CROSSING, the first fresh observation establishes a baseline; firing requires a later false-to-true transition. Rule evaluation never infers a crossing during an unobserved feed gap. Expired, paused or stopped trading rules cannot admit work.

An approved rule survives restart. A qualifying event consumes it once and creates a durable operation or alert atomically. A risk-blocked firing remains consumed with a visible blocked result; it does not retry indefinitely. FIRED means consumed, not filled. Re-arming requires a new approval. Informational alerts remain enabled during the trading emergency stop, and the UI displays that policy.

### Whole-plan approval

Support two-leg plans with exact terms, no cycles and a declared dependency policy. The prototype default is sequential execution: leg 2 waits for leg 1 to be confirmed fully filled. Reserve the entire supported buy commitment conservatively without counting projected sale proceeds. Unsupported financing or margin assumptions require clarification.

Show every leg and the full policy before one plan approval. Partial fill, rejection or UNKNOWN holds dependent work. Never silently resize, add a compensating trade or claim rollback. A changed plan needs a new full approval; already filled legs remain real history and cannot be replayed as part of revision.

## 4 Two primary differentiators

### Independent Order Check

Compare Gemini's proposal with a separate deterministic parser reading the original instruction. Compare action, instrument, side, share units versus money budget, quantity, price and relevant condition/target/expiry. Pydantic validates structure; it is not this independent parse.

Show both readings and disagreement fields. “Buy 10,000 shares” and “buy ₹10,000 worth” must remain distinct. A supported budget request is converted into a proposed exact quantity using disclosed price and lot assumptions; the trader then approves those exact terms. Unsupported grammar fails to clarification. Both checks can still share faulty catalogue data and neither establishes universal language correctness.

### Trade Impact Preview

Show maximum approved LIMIT notional, estimated fees, reserved funds, estimated remaining funds, projected holding quantity and concentration before approval. Display full-fill and valuation assumptions. Sale proceeds remain projected until confirmed and usable. Actual holdings update from fills rather than approved quantities. Estimates are not guaranteed all-in costs under an unverified fee contract.

## 5 Supporting safety features

- Enforce quantity, per-order value, rule budgets and conservative funds or inventory reservations on the server.
- Check quote freshness and displayed drift tolerance at dispatch; retain broker-enforced LIMIT bounds separately.
- Persist emergency stop, prevent new dispatch admissions while active and never imply reversal of existing fills.
- Reconcile UNKNOWN responses without blind resubmission.
- Enforce session ownership, credential separation, CSRF and safe rendering.
- Provide approval-linked receipts with truthful execution and order states.
- Safety Arena uses isolated simulated faults and observed outcomes through the same backend services.

## 6 Verification expectations

| Property | Evidence expected |
|---|---|
| Exact approval | Missing, expired, altered and wrong-account requests produce no admitted mutation |
| Interpretation check | Unit/budget disagreement produces clarification, not an order |
| Duplicate defence | Concurrent replay creates one logical operation per authorized action |
| Failure recovery | Simulator accepts then loses reply; reconciliation finds original action without resend |
| Rule persistence | Restart and repeated ticks do not create another firing |
| Plan truthfulness | Partial/rejected leg remains visible and dependent leg is held |
| Stop persistence | Stop remains active after API and worker restart |
| UI correctness | Refresh/reconnect shows authoritative state and explicit mode |

Report tested cases and denominators. Zero observed failures in a finite test suite is not proof of universal safety or broker exactly-once execution.

## 7 Scope and open dependencies

Excluded from initial scope: investment advice, autonomous strategies, profit prediction, leverage assumptions, automatic liquidation, arbitrary English execution and unverified order types. Security controls do not establish legal or regulatory approval.

021 authentication, sandbox access, read fields, instrument catalogue, feed ordering, idempotency, status lookup, modification and cancellation behaviour remain unverified. Disable unsupported capabilities. Simulator results alone do not satisfy verified live-feed or real-account integration; organizer acceptance must be established.
