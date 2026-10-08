# TradeGuard safety invariants

Version 1.0 | Mandatory properties for intended implementation

These invariants define application behaviour under intact trusted components. Tests provide evidence for specified cases, not an unlimited guarantee. See [DATA_MODEL.md](DATA_MODEL.md) for separate operation and broker-order states.

## 1 Authorization and interpretation

| ID | Invariant | Enforcement and verification consequence |
|---|---|---|
| INV-01 | Only the protected worker can mutate the broker | Mutation credentials and adapter access are unavailable to API, model, client and coordinators |
| INV-02 | Every dispatched mutation has a matching exact authorization | Require direct approval, consumed rule authorization or eligible approved plan leg; the FK alone is insufficient |
| INV-03 | Approval is identity and account specific | Server-derived actor, account membership and object ownership are checked at approval and dispatch |
| INV-04 | Approved terms are immutable | Bind canonical terms, proposal version, target identity, mode and policy; changes require a new version and approval |
| INV-05 | Approval is not model output | Only the authenticated approval endpoint can create an approval; plain chat never does |
| INV-06 | Unsupported or conflicting action interpretation cannot execute | Independent parser reads original text, agreement is validated and unsupported fields require clarification |
| INV-07 | Reads never create trading authority | Account answers have no executable side effects or inherited approval |
| INV-08 | Budget and units cannot be confused | Money requests are visibly converted to exact supported quantity and LIMIT terms before approval |

Canonical terms include schema version, account, mode, action, instrument, side, quantity in units, order type, limit, product/validity, execution deadline, quote/drift policy and action-specific target/rule/plan terms. Exclude mutable UI wording. A hash detects differences; session authentication and a stored authorization establish authority.

The proposal challenge is random, short-lived and bound to the proposal. Activation must occur before approval_expires_at. Later rule and plan execution uses the approved valid_until and exact parent authorization, not an expired challenge as a reason to infer new permission.

## 2 Durability and duplicate effects

| ID | Invariant | Enforcement and verification consequence |
|---|---|---|
| INV-09 | One proposal version is consumed at most once | Unique approval identity and atomic proposal consumption; replay returns existing result |
| INV-10 | One authorized action has at most one logical operation | Unique action identity for direct proposal, rule or plan leg |
| INV-11 | Authorization and work are committed together | Approval/activation, pending work, reservation and evidence form one transaction |
| INV-12 | Dispatch is recorded before the network call | Persist SUBMITTING with immutable attempt identity first |
| INV-13 | Uncertain submission is never treated as definite failure | SUBMITTING crash or ambiguous timeout becomes UNKNOWN; no blind resend |
| INV-14 | Reconciliation refers to the original action | Use verified account-scoped broker evidence; missing/inconsistent lookup retains UNKNOWN |
| INV-15 | Broker acceptance and filling are separate | ACKNOWLEDGED operation links order state; holdings derive from verified fills |
| INV-16 | Duplicate fill evidence does not double accounting | Verified fill ID or validated monotonic cumulative snapshot; uncertain evidence pauses projection |

Exactly-once local admission does not imply exactly-once broker effects. A second submission is allowed only under verified retry semantics that preserve the same remote action identity, or authoritative proof that the original cannot have been accepted. Absence of a record in an eventually consistent lookup is not that proof. The prototype default performs no automatic retry of UNKNOWN mutations.

## 3 Price funds and stop

| ID | Invariant | Enforcement and verification consequence |
|---|---|---|
| INV-17 | Quantity and financial calculations are exact | Integer tradable units and decimal money; validate catalogue lot and tick rules |
| INV-18 | Trading uses valid fresh evidence | Check feed health, timestamps, approved drift policy and current target revision |
| INV-19 | LIMIT remains the approved bound | Worker sends identical LIMIT; quote check cannot replace broker enforcement |
| INV-20 | Capacity cannot be spent twice | Lock account budget; reserve pending/UNKNOWN buy funds and sell inventory conservatively |
| INV-21 | Reservations do not disappear on timeout | Release only on proven unused capacity or authoritative terminal evidence |
| INV-22 | Persistent stop prevents new dispatch admission | Serialize stop/control revision with final gate; pause trading rules and plan advancement |
| INV-23 | Stop does not manufacture cancellation or liquidation permission | Existing fills/orders and in-flight requests remain visible; this scope blocks cancel/modify too |
| INV-24 | HELD never silently resumes | Fresh review and approval are required; resume control does not revive held operations |

For modification, reserve any approved additional exposure without releasing existing uncertain exposure before broker evidence. Pending sell reservations prevent overselling a supported long holding. The prototype does not model unsupported short selling, leverage or derivatives margin as ordinary cash purchases.

For a positive approved reference price, drift_bps equals 10000 times the absolute difference between current price and reference price divided by reference price. Use decimal arithmetic and hold if this exceeds max_drift_bps. Validate both source time and receive time with configured clock-skew tolerance; future, stale, disordered or unverifiable quotes are not actionable. Reference and tolerance are approved terms. Configuration values must be displayed and justified for the verified feed, not presented as universal safe market limits.

Cancel checks target identity and revision, not a price quote. Place/modify require applicable quote evidence. If a fill changes the target between approval and dispatch, hold the action rather than altering the cancellation or modification silently. External changes after the last check remain a broker-contract race and must be reported truthfully.

## 4 Standing rules and plans

| ID | Invariant | Enforcement and verification consequence |
|---|---|---|
| INV-25 | A consumed rule cannot fire again | Unique firing row; atomic rule consume and operation/alert or blocked outcome |
| INV-26 | No crossing is inferred from missing data | Fresh accepted ticks establish and update crossing state; gaps pause evaluation |
| INV-27 | Firing respects approved boundaries | Exact action, reference basis, valid_until, trigger mode and cap are pinned |
| INV-28 | FIRED does not mean FILLED | Rule lifecycle, operation state and order fill state are shown separately |
| INV-29 | Plan authority covers every leg and policy | Full immutable plan approval; no unapproved legs or changed dependencies |
| INV-30 | Dependent legs follow confirmed outcomes | Default FULL_FILL_REQUIRED; PARTIAL, REJECTED and UNKNOWN hold dependents |
| INV-31 | Plan restart cannot repeat an admitted leg | Unique plan-leg operation identity and persisted progress |
| INV-32 | A plan is not an atomic exchange transaction | No false rollback claim, silent quantity resize or compensating trade |

Rules that are paused/stopped/stale retain their condition without firing. When a fresh eligible trigger reaches the risk gate and is denied, record one consumed blocked firing. Explicitly approved re-arming produces a new rule identity. Alerts remain informational and enabled during trading stop.

## 5 Application security and evidence

| ID | Invariant | Enforcement and verification consequence |
|---|---|---|
| INV-33 | Account boundaries apply to all reads and writes | Scope chat, proposals, rules, orders, plans, receipts and event streams |
| INV-34 | Credentials remain outside untrusted zones | Worker/gateway-only secrets, separate modes, redacted prompts/logs and controlled rotation |
| INV-35 | Browser mutation controls are protected | HTTPS, secure sessions, CSRF, restricted origins and authorization; GET routes are side-effect free |
| INV-36 | Untrusted content cannot create UI authority | Safe rendering and explicit approval controls separate from generated text |
| INV-37 | Arena cannot reach a live adapter | Server mode restriction, isolated accounts, no live fault endpoints |
| INV-38 | Reports follow committed evidence | Notifications and receipts expose actual status; no hardcoded pass outcomes |
| INV-39 | Audit claims match implemented protection | Append-only intent is not tamper-proof; optional HMAC/hash chain discloses trust and deletion limits |

## 6 What a database constraint cannot prove

Unique keys can prevent duplicate local approvals, rule firings and leg operations. Foreign keys can require an existing authorization record. Neither proves that the authenticated human approved correct displayed terms, that the worker checked stop, or that a remote broker applied the mutation only once. Service authorization, privilege separation, transactions and verified broker evidence must work together.

## 7 Evaluation interpretation

Measure exact supported-field interpretation accuracy, disagreement detection, unsupported-input rejection, approval bypasses, concurrent logical duplicates, observed remote accepted actions, duplicate fill accounting, restart rule firings and dependent-leg violations. Report denominators, scenario coverage and mode. A blocked malicious-name example does not establish universal prompt-injection resistance; simulator acceptance counts do not establish 021 semantics.
