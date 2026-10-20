# Electronics Sales Assistant - Day 2 Progress

A three-day AI Engineer assessment project. This delivery contains the **Day 2 working end-to-end conversational sales assistant**, featuring structured requirement memory, Google Gemini Developer API integration on the free tier, deterministic eligibility filtering and ranking, and grounded catalogue responses.

---

## 1. Scope & Feature Progress

| Feature | Day 1 Status | Day 2 Status | Implementation Details |
|---|---|---|---|
| **FastAPI + React Foundation** | Implemented | Implemented | REST contracts, CORS, responsive layout, type-safe API client |
| **Synthetic Catalogue (36 records)** | Implemented | Implemented | 24 laptops + 12 headphones, integer paise pricing (1 INR = 100 paise) |
| **Idempotent Database Seeding** | Implemented | Verified (PostgreSQL) | Preserves existing records, 0 duplicates inserted on rerun |
| **Conversation Store & Isolation** | Implemented | Verified | Conversations own messages and requirements; isolated per UUID |
| **External LLM Integration** | Interfaces only | **Implemented & Verified** | Google Gemini Developer API (`gemini-3.1-flash-lite` Free Tier), structured JSON schema |
| **Conversation Memory & Merge** | Planned | **Implemented & Verified** | Omission retains; value replaces; explicit null/empty removes; category switch clears incompatible fields |
| **Conversation Controller** | HTTP 501 | **Implemented & Verified** | `POST /api/v1/conversations/{id}/messages` active; no DB transaction held during LLM call; concurrency control |
| **Clarification Policy** | Planned | **Implemented & Verified** | Asks only when critical info is missing or conflicting; complete requests search immediately |
| **Controlled Search & Ranking** | Planned | **Implemented & Verified** | Parameterized SQL + strict in-memory spec filters; missing specs (`LAP-023`) never satisfy; stable tie-breaking |
| **Grounded Responses** | Planned | **Implemented & Verified** | Up to 2 recommendations with reasons, trade-offs, and unknowns; honest no-match recovery |
| **React Interactive Chat** | Static placeholder | **Implemented & Verified** | Live chat feed, current requirements summary chips, grounded recommendation cards, duplicate prevention, retry on error |
| **Automated Test Coverage** | 40 foundation tests | **58 total tests (100% pass)** | 18 new Day 2 behavioral and failure-recovery tests |

---

## 2. External AI Service & Model Verification

### Provider & Model Identifier
- **Provider**: Google Gemini Developer API (via Google AI Studio).
- **Verified Active Model**: `gemini-3.1-flash-lite` (model identifier: `gemini-3.1-flash-lite`).
- **Cost**: 100% Free Tier ($0). Paid billing is explicitly disabled.

### Model Investigation & Availability Findings
During live verification with Google AI Studio, account access and official endpoints were tested:
1. **`gemini-3.8-flash`**: Originally proposed in Day 1 planning. Real API calls repeatedly timed out (>30s) or failed with `HTTP 503: No capacity available for model gemini-3.8-flash on the server`.
2. **`gemini-2.5-flash`**: Returned `HTTP 404` with provider notice: *"This model models/gemini-2.5-flash is no longer available to new users."*
3. **`gemini-3.5-flash`**: Functional with structured output schema, but occasionally experienced 503 capacity limits during peak hours.
4. **`gemini-3.1-flash-lite`** (Selected & Verified): Available with zero-cost free quota, responds in ~1.5 to 2.8 seconds, and strictly enforces our Pydantic JSON schema.

### Free-Tier Quota & Reliability Safeguards
- **Quota Limitations**: Free tier projects have requests-per-minute (RPM) and requests-per-day (RPD) limits.
- **Offline / Deterministic Testing**: All automated tests use `FakeLLMAdapter` so tests never consume API quota and execute in <4 seconds.
- **Server-Side Key**: `GEMINI_API_KEY` is loaded from the backend `.env` only. React and the client browser never receive the key.
- **Structured Task**: The model is strictly an extractor that proposes requirement updates; it has zero authority to execute SQL, invent products, or mutate the database directly.

---

## 3. Configuration & Environment Variables

Create `.env` at the project root (never commit `.env`):

```bash
# PostgreSQL connection (default local assessment setup)
POSTGRES_DB=electronics
POSTGRES_USER=electronics
POSTGRES_PASSWORD=local_demo_only
DATABASE_URL=postgresql+psycopg://electronics:local_demo_only@localhost:5432/electronics
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

# External LLM Configuration (Google Gemini Developer API - Free tier)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
LLM_TIMEOUT_SECONDS=15

# Optional SQLite Preview fallback (no PostgreSQL or Docker required)
# DATABASE_URL=sqlite:///./preview.db
```

| Variable | Where | Description |
|---|---|---|
| `DATABASE_URL` | Root `.env` | Primary database URL (`postgresql+psycopg://...` or `sqlite:///./preview.db`) |
| `GEMINI_API_KEY` | Root `.env` | Google AI Studio free-tier API key (server-side only) |
| `GEMINI_MODEL` | Root `.env` | Active Gemini model (default: `gemini-3.1-flash-lite`) |
| `LLM_TIMEOUT_SECONDS` | Root `.env` | Max duration for external LLM request before raising 504 (default: `15.0`) |
| `CORS_ORIGINS` | Root `.env` | JSON list of allowed frontend origins |
| `VITE_API_BASE_URL` | `frontend/.env` | Backend URL for React client (default: `http://127.0.0.1:8000`) |

---

## 4. Setup, Seed, Startup, and Test Commands

### 4.1 Prerequisites
- Python 3.12 (or 3.10+)
- Node.js 22.12+ (or Node 24) and npm
- PostgreSQL running locally on port 5432, or use the SQLite preview mode

### 4.2 Windows PowerShell Setup

```powershell
# 1. Backend environment setup
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

# 2. Database initialization and seeding (PostgreSQL or SQLite)
cd backend
..\.venv\Scripts\python.exe -m app.seed
```

### 4.3 Running the Application

**Terminal 1 (Backend):**
```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 (Frontend):**
```powershell
cd frontend
npm ci
npm run dev -- --port 5173
```

Open:
- Application: http://localhost:5173
- Swagger API Docs: http://127.0.0.1:8000/docs
- Health Status: http://127.0.0.1:8000/api/v1/health

### 4.4 Automated Testing

```powershell
# Run all 58 backend tests (using isolated SQLite per test; 0 quota consumed)
cd backend
..\.venv\Scripts\python.exe -m pytest -q

# Run frontend typecheck and production build
cd frontend
npm run typecheck
npm run build
```

---

## 5. API Reference & All 6 Endpoints

Interactive documentation is available at `/docs`; OpenAPI 3.1 JSON is served at `/openapi.json`.

### 1. `GET /api/v1/products`
Filter catalogue items by category and inclusive maximum budget.
- **Query Params**: `category=laptop|headphones`, `max_price_paise`, `page`, `page_size`
- **Response** (HTTP 200):
```json
{
  "items": [
    {
      "id": "LAP-023",
      "name": "Nexa Everyday 15",
      "category": "laptop",
      "price_paise": 2999000,
      "currency": "INR",
      "specifications": {
        "ram_gb": 8,
        "storage_gb": 256,
        "cpu": "Synthetic C4 processor (4 cores)",
        "gpu": "Synthetic integrated graphics",
        "vram_gb": null,
        "weight_kg": null,
        "operating_system": "Linux"
      },
      "intended_uses": ["general_coursework"],
      "features": ["SSD storage"]
    }
  ],
  "total": 36,
  "page": 1,
  "page_size": 12,
  "total_pages": 3
}
```

### 2. `GET /api/v1/products/{product_id}`
Retrieve a single stored catalogue product by ID.
- **Path Param**: `product_id` (e.g. `LAP-001`)
- **Response** (HTTP 200): Stored `ProductOut` object; HTTP 404 if absent.

### 3. `POST /api/v1/conversations`
Initialize a new conversation session with empty requirement state.
- **Request Body**: None required.
- **Response** (HTTP 201):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "requirements": {
    "category": null,
    "intended_uses": [],
    "hard_constraints": {
      "max_price_paise": null,
      "min_ram_gb": null,
      "max_weight_kg": null,
      "required_features": []
    },
    "preferences": {
      "lightweight": null,
      "brand": null
    },
    "answered_no_preference": [],
    "unresolved_questions": []
  },
  "status": "awaiting_agent",
  "created_at": "2026-10-20T12:00:00Z",
  "updated_at": "2026-10-20T12:00:00Z",
  "messages": []
}
```

### 4. `GET /api/v1/conversations/{conversation_id}`
Retrieve current requirement state and chronological message history.
- **Path Param**: `conversation_id` (UUID)
- **Response** (HTTP 200): Stored `ConversationOut` with ordered user and assistant turns.

### 5. `POST /api/v1/conversations/{conversation_id}/messages`
Process customer message, update structured memory, and return grounded recommendations or clarification.
- **Request**: `{"content": "I need a programming laptop under 75000 rupees, any brand is fine"}`
- **Response Example 1 - Recommendations** (HTTP 200):
```json
{
  "type": "recommendations",
  "requirements": {
    "category": "laptop",
    "intended_uses": ["programming"],
    "hard_constraints": {
      "max_price_paise": 7500000,
      "min_ram_gb": null,
      "max_weight_kg": null,
      "required_features": []
    },
    "preferences": {
      "lightweight": null,
      "brand": null
    },
    "answered_no_preference": ["brand"],
    "unresolved_questions": []
  },
  "products": [
    {
      "product": {
        "id": "LAP-015",
        "name": "Nexa Pro 16",
        "category": "laptop",
        "price_paise": 7000000,
        "currency": "INR",
        "specifications": {
          "ram_gb": 16,
          "storage_gb": 512,
          "cpu": "Synthetic C8 processor (8 cores)",
          "gpu": "Synthetic discrete graphics",
          "vram_gb": 4,
          "weight_kg": 1.9,
          "operating_system": "Windows"
        },
        "intended_uses": ["programming", "gaming"],
        "features": ["SSD storage", "Dedicated GPU"]
      },
      "reasons": [
        "Suitable for programming with Synthetic C8 processor (8 cores) and 16 GB RAM.",
        "Priced at ₹70,000, within your budget ceiling of ₹75,000."
      ],
      "trade_offs": [
        "At 1.9 kg, it is heavier than ultraportable alternatives."
      ],
      "unknowns": []
    }
  ]
}
```

- **Response Example 2 - Clarification** (HTTP 200):
```json
{
  "type": "clarification",
  "question": "What primary tasks will you use the laptop for (such as general coursework, programming, or gaming), and do you have a target budget?",
  "requirements": {
    "category": "laptop",
    "intended_uses": ["general_coursework"],
    "hard_constraints": { "max_price_paise": null },
    "preferences": {},
    "answered_no_preference": [],
    "unresolved_questions": []
  }
}
```

- **Response Example 3 - No Match** (HTTP 200):
```json
{
  "type": "no_match",
  "explanation": "Your budget ceiling of ₹15,000 is below our lowest-priced laptop (Nexa Everyday 15 at ₹29,990).",
  "proposed_adjustment_question": "Would you be open to adjusting your budget to ₹29,990?",
  "requirements": { ... }
}
```

### 6. `GET /api/v1/health`
Check database connectivity and assistant readiness.
- **Response** (HTTP 200):
```json
{
  "status": "ok",
  "database": "connected",
  "database_engine": "postgresql",
  "agent": "active",
  "build_stage": "day2"
}
```

---

## 6. Core System Logic

### Memory Update Rules (`backend/app/memory.py`)
- **Omission means retain**: If an update does not mention a field, the existing value remains unchanged.
- **Value means replace**: A non-null value updates or replaces that specific requirement.
- **Explicit null/empty means clear**: Providing `None` or `[]` explicitly clears that requirement.
- **Explicit no-preference**: If customer states "no budget limit" or "any brand is fine", `"budget"` or `"brand"` is stored in `answered_no_preference`. Setting a future explicit budget automatically removes `"budget"` from `answered_no_preference`.
- **Category switching**: Switching between `laptop` and `headphones` automatically clears incompatible fields (e.g. laptop RAM and weight when switching to headphones; ANC and battery hours when switching to laptop), while preserving category-agnostic constraints like budget ceiling and brand.

### Clarification Policy (`backend/app/controller.py`)
- Clarification is triggered ONLY if critical information is missing or conflicting:
  1. Category is unknown.
  2. Request is overly vague (e.g. college laptop with no budget and no specific use).
  3. Contradictory constraints were specified.
- A complete request (e.g. "Gaming laptop under ₹1,00,000") searches immediately without mandatory filler questions.
- If customer stated "no budget limit", the assistant remembers and does not re-ask for budget.

### Eligibility and Ranking Rules (`backend/app/ranking.py`)
1. **Eligibility before scoring**:
   - Correct product category.
   - Price ceiling (`price_paise <= max_price_paise`).
   - Minimum specifications (`ram_gb >= min_ram_gb`).
   - Maximum weight (`weight_kg <= max_weight_kg`).
   - **Missing specification rule**: A missing specification (`None` or `null`, such as `LAP-023` weight) is treated as unknown and **never** satisfies a constraint.
2. **Deterministic Heuristic Scoring**:
   - Matching intended uses: +35 points per match.
   - Stated preferences: +15 to +25 points for lightweight, +30 for preferred brand, +20 for ANC.
   - Capabilities: RAM scaling, dedicated GPU for demanding workloads (+30).
   - Price efficiency: Normalized bonus for remaining well within budget.
3. **Stable Tie-breaking**:
   - Sorted by `(-score, price_paise, product_id)`.
   - Highest score first; if equal, lower price first; if equal, alphabetical ID first.
4. **Candidate Count**:
   - Up to 2 recommendations if >= 2 qualify.
   - Exactly 1 recommendation if only 1 qualifies.
   - `NoMatchResponse` if 0 qualify. Mandatory constraints are never silently relaxed.

### Error Handling & Reliability
- **HTTP 422 (`validation_error`)**: Malformed inputs or payloads exceeding bounds (1-4000 characters).
- **HTTP 404 (`conversation_not_found`)**: Non-existent conversation UUID.
- **HTTP 409 (`concurrency_conflict`)**: Overlapping concurrent message attempted on stale conversation version.
- **HTTP 429 (`rate_limit_exceeded`)**: External LLM rate limit or quota exceeded.
- **HTTP 502 (`llm_invalid_response`)**: Model returned unparseable output. State is preserved untouched.
- **HTTP 503 (`database_unavailable` / `llm_unavailable`)**: Database connection failure or unconfigured API key.
- **HTTP 504 (`llm_timeout`)**: External LLM exceeded bounded timeout. State is preserved untouched.

---

## 7. Verification Results Summary

| Verification Area | Result | Notes |
|---|---|---|
| **Backend Automated Tests** | **58 passed, 0 failed** | 32 API + 8 Contract + 18 Day 2 Behavioural tests |
| **Frontend TypeScript** | **Passed** | `tsc --noEmit` exited with code 0 |
| **Frontend Production Build** | **Passed** | Vite bundled production assets in 870ms |
| **PostgreSQL Foundation** | **Verified** | 36 products stored; 0 duplicate inserts on second seed run |
| **PostgreSQL E2E Smoke Test** | **Verified** | Live transaction, conversation creation, message turn, persistence |
| **Real Gemini API Check** | **Verified** | `gemini-3.1-flash-lite` returned valid structured extraction in 2.1s |

---

## 8. Known Limitations & Remaining Work for Day 3

- **Single Store Currency**: Prices are strictly INR paise.
- **Test Database Isolation**: User `electronics` does not have superuser privileges to create new databases (`CREATE DATABASE`), so unit tests use isolated SQLite databases with identical schemas while PostgreSQL was verified via dedicated scripts.
- **Day 3 Focus**: Live rehearsal of the demonstration script, Google Meet presentation rehearsal, and fine-tuning response latency.
#   S n i p p e t _ I n t e r n  
 