# TradeGuard repository instructions

## Purpose and status

This file guides human developers and coding assistants working on TradeGuard, the PS-04 AI Trading Copilot prototype. The accompanying documents describe intended behaviour, not completed implementation. No codebase or organizer-provided 021 contract has been verified for this pack.

Read [PRD.md](PRD.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [INVARIANTS.md](INVARIANTS.md) before changing trading behaviour. Use [DATA_MODEL.md](DATA_MODEL.md) and [API_CONTRACT.md](API_CONTRACT.md) for shared types and boundaries.

## Document authority

- PRD owns product requirements and trader-facing behaviour.
- ARCHITECTURE owns component boundaries and responsibilities.
- INVARIANTS owns mandatory safety properties and failure behaviour.
- DATA_MODEL owns persisted entities, state names and integrity rules.
- API_CONTRACT owns the proposed TradeGuard HTTP and event interface.
- AGENTS owns repository working practices and human task ownership.

If these disagree, preserve the more restrictive safety behaviour, identify the conflict and update the affected documents together. A newer document date alone cannot authorize a trade or override an invariant. Explicit organizer requirements and verified broker contracts may require a documented design revision.

## Team ownership

| Member | Primary area | Review partner |
|---|---|---|
| 1 | React workspace, approval cards, impact and interpretation panels, status and Arena UI | 2 for approval; 4 for data |
| 2 | Gemini proposals, independent parser, validation, sessions, ownership and exact approval | 3 |
| 3 | PostgreSQL changes, operation admission, risk reservations, worker, broker adapter, reconciliation and plans | 2 and 4 |
| 4 | Account queries, instruments, feed normalization, persistent rules and Arena scenarios | 3 and 1 |

Member numbers are skill-based role slots, not assigned names. Every member tests their own area. Member 3 coordinates migrations; Member 2 coordinates canonical approved terms. Avoid multiple incompatible definitions of the same state or payload.

## Fixed implementation direction

Use React, TypeScript and Tailwind CSS; Python and FastAPI; Gemini structured proposals; Pydantic validation plus separate deterministic parsing of the original instruction; PostgreSQL with versioned migrations; one protected Python worker; WebSockets for notifications and HTTP for authoritative reloads. Use Pytest for meaningful backend tests. SQLAlchemy and Alembic are suitable implementation choices for persistence and migrations, but lock supported versions when the repository is initialized.

Persist pending work in PostgreSQL. Do not introduce Redis, Celery, Kafka or additional execution services without a concrete need. FastAPI in-process background tasks are not durable execution storage.

## Nonnegotiable working rules

1. The model may propose and explain. It may not approve, submit, modify, cancel, change risk policy or read broker credentials.
2. All broker mutations originate in the protected worker through the same admission checks. No route, rule evaluator, plan coordinator or Arena helper writes directly to the broker.
3. The frontend sends references to exact proposals, not authoritative order terms. The server loads stored terms and derives actor identity from the session.
4. Treat model output, stock display names and feed metadata as untrusted data. Never render untrusted raw HTML or execute generated code.
5. Use decimal arithmetic for money and price; use integer instrument units for quantities. Never use binary floating point for financial accounting.
6. A network timeout is not a rejection. Persist UNKNOWN and reconcile before any retry that could duplicate an accepted action.
7. Never log secrets or place them in browser assets, prompts, fixtures, commits or screenshots. Credentials belong in server secret configuration, separated by mode and account.
8. Do not make real-money calls, alter real accounts or expose a live trading mode as a consequence of coding or tests. Use the simulator or an explicitly authorized organizer sandbox. Live operation requires separately established access and authorization.
9. Label SIMULATOR, ORGANIZER_SANDBOX and LIVE honestly. Never switch between them silently. Fault injection is unavailable outside SIMULATOR.
10. Do not claim a control is implemented or a test passed without observed evidence. Do not claim guaranteed fills, universal injection immunity or broker exactly-once effects.

## Change and verification discipline

Keep changes small enough to review. Changes to terms, states, approval, retry, reservations, rules or plans must update relevant contracts and receive review from the other owner of that boundary. Use parameterized database access and strict request models that reject extra fields.

Meaningful safety checks include altered or expired approval, account isolation, concurrent replay, timeout after acceptance, worker restart, duplicate ticks, held dependent legs, stale quotes and persistent stop. Use the same services in tests and Arena as in normal operation. Do not replace a failing control with a UI-only check or a hardcoded pass badge.

Where a broker feature is unavailable, disable the affected action and explain it. Do not invent 021 endpoints, status meanings, option conventions or idempotency semantics. Record verified capability evidence in the adapter configuration and maintain separate simulator evidence.

## Completion reporting

Report what changed, which requirement it satisfies, tests actually run, results and remaining limits. Say explicitly if the current mode is simulated. Preserve unrelated work and never rewrite teammates' shared contracts without coordination.
