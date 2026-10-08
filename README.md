# TradeGuard — AI Trading Copilot

**SYRUS 7.0 · PS-04 · Prototype** | Mode: **SIMULATOR only** (no live-broker connection established)

> "The model proposes; deterministic code validates; the trader approves exact terms; only a protected worker writes to the broker."

---

## 1. Project Overview

TradeGuard is a web-based AI trading copilot that lets a trader query their 021 brokerage account and act on it through a guarded chat interface. Every order action — placement, modification, or cancellation — requires an explicit approval of the exact displayed terms before the system touches the broker.

**Problem statement (PS-04 requirements):**

| # | Requirement |
|---|---|
| FR-01 | Read-only queries: today's P&L, positions down >5%, average purchase price, NIFTY option chains |
| FR-02 | Order actions (place / modify / cancel) only after exact trader approval of a displayed card |
| FR-03 | Persistent standing instructions evaluated against a live price feed; each condition fires once |
| FR-04 | Whole-plan approval with truthful partial-fill and rejection reporting per leg |
| FR-05 | Web chat interface connecting the trader to all of the above |

---

## 2. Implementation Status

> **Current state:** The repository contains project structure scaffolding and complete design documents. No application code has been written yet. All feature rows below are **Planned**.

| Feature | Status | Notes |
|---|---|---|
| Project scaffold (folders, config files) | ✅ Done | `backend/`, `frontend/`, `docs/` created |
| Design documentation (PRD, ARCHITECTURE, etc.) | ✅ Done | Documents in docs/ and repo root |
| FastAPI application skeleton | 🔲 Planned | `backend/app/main.py` is empty |
| PostgreSQL schema / Alembic migrations | 🔲 Planned | `backend/alembic/versions/` is empty |
| Session and authentication | 🔲 Planned | |
| Chat endpoint and Gemini integration | 🔲 Planned | |
| Independent deterministic parser | 🔲 Planned | |
| Proposal creation and approval flow | 🔲 Planned | |
| Protected execution worker | 🔲 Planned | |
| Simulator adapter | 🔲 Planned | |
| UNKNOWN-state reconciliation | 🔲 Planned | |
| Price feed and standing rules | 🔲 Planned | |
| Multi-leg plan execution | 🔲 Planned | |
| Trade Impact Preview | 🔲 Planned | |
| Independent Order Check | 🔲 Planned | |
| Emergency stop | 🔲 Planned | |
| React frontend / web chat UI | 🔲 Planned | `frontend/src/` scaffold only |
| WebSocket event stream | 🔲 Planned | |
| Safety Arena | 🔲 Planned | |
| Pytest integration tests | 🔲 Planned | `backend/tests/` folders created |

*Simulator results alone do not establish real broker integration. No 021 credentials or endpoints have been verified.*

---

## 3. Core Features (Intended Design)

### Read-only queries
Deterministic backend code runs all calculations. The AI model selects and explains the query but does not compute the result. Every answer carries its calculation basis, source timestamps, and data-quality indicators. Missing data returns `UNAVAILABLE` — never a fabricated value.

### Exact order approval
A proposal card displays: account, action, instrument, side, quantity (in integer instrument units), LIMIT price, product, validity, quote snapshot, and drift policy. The trader approves this card through a protected UI control. Plain chat text such as "yes" **does not** authorize execution. Editing any term creates a new immutable proposal version requiring fresh approval.

### Persistent standing rules
Each rule stores: condition, reference basis, trigger mode (`IMMEDIATE_IF_TRUE` or `FUTURE_CROSSING`), action, quantity, LIMIT, per-rule cap, start/expiry. A qualifying fresh price tick atomically consumes the rule and creates exactly one operation or alert. A rule that fires once cannot fire again without explicit re-approval.

### Multi-step plans
Two-leg plans are approved in full before any leg executes. Leg 2 waits for leg 1 to be confirmed fully filled (`FULL_FILL_REQUIRED`). Partial fills, rejections, and UNKNOWN outcomes hold dependent legs. The system never silently resizes, adds compensating trades, or claims a rollback.

---

## 4. Two Differentiators

### Independent Order Check
When the trader sends a natural-language instruction, the system runs **two independent parsers** in parallel:
- **Gemini structured output** — produces a typed proposal object.
- **Deterministic parser** — re-reads the original instruction text independently.

The system compares action, instrument, side, quantity (units vs. money budget), price, and relevant conditions. Disagreements are shown explicitly and require clarification before a proposal is created. "Buy 10,000 shares" and "buy ₹10,000 worth" are treated as distinct and never silently merged. Pydantic validates structure; it does not replace this independent parse.

### Trade Impact Preview
Before approval, the system displays:
- Maximum approved LIMIT notional
- Estimated fees (assumptions disclosed; not a guaranteed all-in cost)
- Reserved funds
- Estimated remaining funds
- Projected holding quantity
- Concentration relative to account

All estimates are labelled with their assumptions. Sale proceeds remain projected until confirmed by a verified fill.

---

## 5. Architecture

```mermaid
flowchart TD
    UI["Web workspace\n(React + TypeScript)"]
    API["Authenticated FastAPI\n/api/v1"]
    INT["Interpretation service\nGemini + deterministic parser"]
    PRE["Validated proposal\n+ Impact preview"]
    DB["PostgreSQL\nDurable state"]
    FEED["Price feed\n(validated ticks)"]
    RULE["Rule evaluator"]
    PLAN["Plan coordinator"]
    WORK["Protected execution worker\n(separate process)"]
    GATE["Final auth + risk gate"]
    BROKER["Simulator adapter\n(no live broker verified)"]
    REC["Reconciliation\n+ fill processing"]
    EVT["Account-scoped\nevent notifications"]

    UI -->|"HTTPS + CSRF"| API
    API --> INT
    INT --> PRE
    PRE --> DB
    UI -->|"Approval reference only"| API
    API -->|"Exact approval"| DB
    FEED --> RULE
    RULE --> DB
    PLAN --> DB
    DB -->|"READY operations"| WORK
    WORK --> GATE
    GATE -->|"SUBMITTING persisted first"| BROKER
    BROKER --> REC
    REC --> DB
    DB --> EVT
    EVT -->|"WebSocket"| UI
```

**Key boundaries:**
- The API layer has no broker mutation credentials.
- The frontend sends proposal references, not order terms.
- The worker is the only path to the broker and runs admission checks on every dispatch.
- Model output, display names, and feed metadata are treated as untrusted data throughout.

---

## 6. End-to-End Trader Workflow

```
1. Trader types: "Buy 6 shares of Infosys at ₹1500 limit"
      │
2. Backend runs Gemini parser + independent deterministic parser in parallel
      │
3. Both parsers agree → proposal created with immutable terms and approval challenge
      │
4. Frontend displays approval card:
      Account | BUY | INFY | 6 units | LIMIT ₹1500 | SIM_CASH | Expiry: ...
      Impact: max notional ₹9000 | fees: disclosed | reserved funds: ₹9000
      │
5. Trader clicks the protected "Approve" button (not chat)
      │
6. Server: validates session, challenge, version, stop, risk limits → commits
      Approval + Operation (READY) + Reservation in one transaction
      │
7. Protected worker claims operation exclusively
      Rechecks: stop, authorization, deadline, quote freshness, bounds
      Persists SUBMITTING + caller reference BEFORE network call
      │
8. Simulator adapter called → ACKNOWLEDGED / REJECTED / UNCERTAIN
      If uncertain → operation becomes UNKNOWN; reconciliation required
      │
9. Fill evidence ingested → reservations adjusted → UI notified via WebSocket
      ACKNOWLEDGED ≠ filled; fills derive from verified fill evidence only
```

**UNKNOWN-state recovery:** If a network timeout occurs after dispatch, the operation is persisted as `UNKNOWN`. Reconciliation looks up the original caller reference against the broker. A missing lookup result is not treated as definite rejection. No automatic retry is performed for UNKNOWN mutations — a human-initiated reconcile request triggers a bounded lookup.

---

## 7. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React, TypeScript, Tailwind CSS | Typed approval cards, trader workspace, responsive UI |
| Application | Python 3.11+, FastAPI, Pydantic | Strict request validation, deterministic service contracts |
| AI Model | Google Gemini (structured output) | Constrained proposal generation; independent checks validate it |
| Persistence | PostgreSQL | Transactions, row-level locking, durable pending work |
| ORM / Migrations | SQLAlchemy, Alembic | Type-safe queries, versioned schema migrations |
| Execution | Python worker (separate process) | Sole path to broker; polls PostgreSQL for READY work |
| Realtime | WebSockets + HTTP reload | Fast status notifications with HTTP as the authoritative source |
| Testing | Pytest | Approval, concurrency, and failure-recovery scenarios |

**Excluded by design:** Redis, Celery, Kafka, in-process background tasks as durable execution storage.

---

## 8. Security and Safety Controls

> Controls listed as **Planned** are described in design documents but not yet implemented.

| Control | Status | Notes |
|---|---|---|
| Session-bound actor identity | 🔲 Planned | Server derives actor from session; client actor IDs rejected |
| HttpOnly Secure session cookie + CSRF token | 🔲 Planned | Required on all mutations |
| Immutable proposal terms + version hash | 🔲 Planned | Changes require new version and approval |
| Proposal challenge (short-lived, random) | 🔲 Planned | Bound to proposal; not reusable |
| Protected worker credential separation | 🔲 Planned | Mutation credentials unavailable to API, model, or frontend |
| Decimal arithmetic for money/prices | 🔲 Planned | Binary float prohibited for financial accounting |
| Integer units for quantities | 🔲 Planned | Lot-size confusion prevented by display separation |
| UNKNOWN persisted on timeout (no blind retry) | 🔲 Planned | See INV-12, INV-13 |
| Persistent emergency stop | 🔲 Planned | Blocks new dispatch; does not cancel in-flight or existing fills |
| Account-scoped event streams | 🔲 Planned | Cross-account data never exposed |
| Safe rendering (no raw HTML from model) | 🔲 Planned | Model output treated as untrusted text |
| Audit event log | 🔲 Planned | Append-only; optional HMAC chain |
| Arena isolated from live adapters | 🔲 Planned | SIMULATOR accounts only |

**Emergency stop limits:** Activating stop prevents new operations from crossing the final dispatch gate. It does not cancel orders already sent to the broker, reverse existing fills, or affect informational alerts. Resuming requires explicit authenticated action and does not revive HELD work.

**Broker acknowledgement ≠ fill.** `ACKNOWLEDGED` means the broker accepted the mutation request. Holdings are updated only from verified fill evidence, not from acknowledgement.

---

## 9. Repository Structure

```
TradeGuard/
├── README.md                    ← This file
├── AGENTS.md                    ← Team working rules
├── .gitignore
├── .env.example                 ← Root-level env placeholder
├── docker-compose.yml           ← (empty, to be defined)
│
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI entry point (empty)
│   │   ├── api/v1/endpoints/    ← Route handlers (empty)
│   │   ├── core/
│   │   │   ├── config.py        ← Settings (empty)
│   │   │   └── security.py      ← Auth helpers (empty)
│   │   ├── models/              ← SQLAlchemy models (empty)
│   │   ├── schemas/             ← Pydantic schemas (empty)
│   │   ├── services/            ← Business logic (empty)
│   │   ├── db/database.py       ← DB connection (empty)
│   │   └── utils/
│   ├── alembic/
│   │   └── versions/            ← Migrations (none yet)
│   ├── tests/
│   │   ├── unit/                ← (empty)
│   │   └── integration/         ← (empty)
│   ├── scripts/                 ← Utility scripts (empty)
│   ├── requirements.txt         ← (empty — to be populated)
│   ├── .env.example
│   └── Dockerfile               ← (empty)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              ← Root component (empty)
│   │   ├── main.jsx             ← Entry point (empty)
│   │   ├── components/
│   │   │   ├── common/
│   │   │   └── layout/
│   │   ├── pages/
│   │   ├── context/AuthContext.jsx
│   │   ├── hooks/
│   │   ├── services/authService.js
│   │   ├── utils/api.js
│   │   └── styles/
│   ├── public/index.html
│   ├── package.json             ← (empty — to be populated)
│   ├── .env.example
│   └── Dockerfile               ← (empty)
│
└── docs/
    ├── PRD.md                   ← Product requirements
    ├── ARCHITECTURE.md          ← Component design
    ├── INVARIANTS.md            ← Mandatory safety properties
    ├── DATA_MODEL.md            ← PostgreSQL entities and state machines
    ├── API_CONTRACT.md          ← FastAPI routes and payloads
    ├── api/
    ├── architecture/
    └── guides/
        ├── setup.md
        └── deployment.md
```

---

## 10. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| PostgreSQL | 15+ | Primary datastore |
| Git | Any recent | Version control |

> **Note:** `backend/requirements.txt` is populated and verified. `frontend/package.json` remains to be initialized.

---

## 11. Environment Configuration

**Backend** — copy `backend/.env.example` to `backend/.env` and fill in:

```env
# Application
APP_ENV=development
SECRET_KEY=replace-with-a-long-random-string

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tradeguard

# Gemini
GEMINI_API_KEY=your-gemini-api-key-here

# Mode (never switch silently)
TRADING_MODE=SIMULATOR

# Worker
WORKER_POLL_INTERVAL_SECONDS=2
```

**Frontend** — copy `frontend/.env.example` to `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_BASE_URL=ws://localhost:8000/api/v1
VITE_APP_MODE=SIMULATOR
```

> **Security rules:** Never commit real secrets, API keys, or credentials. Never place broker credentials in frontend assets or model prompts. Separate SIMULATOR and LIVE credentials completely.

---

## 12. Local Setup

### Backend

```bash
# 1. Create and activate a virtual environment (if not already created)
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and fill environment file (if not done)
# Note: The .env file is located at the project root
copy ..\.env.example ..\.env

# 4. Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
# 1. Install dependencies
cd frontend
# ⚠️  package.json is currently empty — populate before running
npm install

# 2. Copy and fill environment file
copy .env.example .env

# 3. Start the development server
npm run dev
```

### Protected Execution Worker

```bash
# Run as a separate process (not a background task in FastAPI)
cd backend
# ⚠️  Worker module not yet created
python -m app.worker
```

---

## 13. Database Initialization and Migrations

```bash
cd backend

# Initialize Alembic (first time only — alembic.ini not yet present)
alembic init alembic

# Create a new migration after model changes
alembic revision --autogenerate -m "describe change"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

> **Note:** No migrations exist yet. `alembic/versions/` is empty. Member 3 coordinates all schema changes.

---

## 14. Testing

```bash
cd backend

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with coverage report
pytest --cov=app --cov-report=term-missing
```

> **Note:** Initial health and configuration unit tests are implemented. You can run them to verify the backend foundation.

Meaningful scenarios to implement (per INVARIANTS.md):
- Expired / altered / wrong-account approval returns no admitted mutation
- Concurrent replay creates one logical operation per authorized action
- UNKNOWN outcome from simulator is not automatically retried
- Rule does not fire twice after restart
- Dependent plan leg is held on partial fill

---

## 15. Simulator Usage

All development and testing **must** use `TRADING_MODE=SIMULATOR`. The simulator adapter:
- Accepts and rejects synthetic orders without touching any real account
- Can inject fault scenarios (lost reply, stale tick, duplicate delivery) for Safety Arena
- Uses `SIM_CASH` and `SIM_DAY` as product and validity labels

**Safety Arena scenarios** (to be implemented):
`INTERPRETATION_MISMATCH`, `APPROVAL_REPLAY`, `LOST_BROKER_REPLY`, `MALICIOUS_DISPLAY_NAME`, `RULE_RESTART`, `PARTIAL_PLAN`

> Simulator acceptance counts do not establish 021 semantics or real broker behavior. Organizer sandbox access requires separately verified credentials and authorization. Live mode (`TRADING_MODE=LIVE`) must never be activated as a consequence of coding or tests.

---

## 16. Known Limitations and Unverified Capabilities

| Item | Status |
|---|---|
| 021 authentication mechanism | **Unverified** — no organizer contract received |
| 021 sandbox / live endpoint URLs | **Unverified** |
| Available order types beyond LIMIT | **Unverified** — only LIMIT assumed |
| Supported products and validity types | **Unverified** — SIM_CASH/SIM_DAY are simulator labels |
| Modify / cancel idempotency semantics | **Unverified** |
| Fill evidence format and deduplication | **Unverified** |
| Option lot sizes and expiry calendars | **Unverified** — must use verified catalogue metadata |
| Feed timestamp ordering guarantees | **Unverified** |
| Broker exactly-once execution | **Not claimed** — local deduplication is separate from broker idempotency |
| Universal prompt-injection resistance | **Not claimed** — a blocked example does not prove universal immunity |
| Guaranteed fills | **Not claimed** — acknowledgement ≠ fill |

Unsupported capabilities are disabled and explained to the trader; they are not silently emulated.

---

## 17. Project Documentation

| Document | Purpose |
|---|---|
| [PRD.md](docs/PRD.md) | Product requirements and trader-facing behaviour (v1.0) |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component boundaries, trust zones, and data flow |
| [INVARIANTS.md](docs/INVARIANTS.md) | 39 mandatory safety properties and their enforcement |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | PostgreSQL entities, state machines, and transaction boundaries |
| [API_CONTRACT.md](docs/API_CONTRACT.md) | FastAPI routes, payloads, error codes, and event types |
| [AGENTS.md](AGENTS.md) | Team working rules, ownership map, and nonnegotiable constraints |

If any two documents disagree, preserve the more restrictive safety behaviour and document the conflict.

---

## 18. Team Contributions

| Member | Primary area | Review partner |
|---|---|---|
| **Member 1** | React workspace, approval cards, impact panel, interpretation panel, status bar, Arena UI | Member 2 (approval flow), Member 4 (data display) |
| **Member 2** | Gemini proposals, independent parser, Pydantic validation, sessions, ownership, exact approval endpoint | Member 3 |
| **Member 3** | PostgreSQL schema, Alembic migrations, operation admission, risk reservations, execution worker, broker adapter, reconciliation, plan coordination | Members 2 and 4 |
| **Member 4** | Account queries, P&L calculations, instrument catalogue, feed normalization, standing rules, Arena scenarios | Members 3 and 1 |

Member numbers are role slots, not names. Every member writes tests for their own area. Member 3 coordinates all migrations. Member 2 coordinates canonical approved terms. Incompatible definitions of the same state or payload must be resolved before merging.

---

## Reporting Discipline

When submitting a PR or closing a task, state:
1. What changed.
2. Which requirement or invariant it satisfies.
3. Tests actually run and their results (not assumed).
4. Whether the current run used SIMULATOR, ORGANIZER_SANDBOX, or LIVE.
5. Remaining limits or open questions.

Do not claim a control is implemented or a test passed without observed evidence.
