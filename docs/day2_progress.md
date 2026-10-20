# Day 2 Progress Report: Conversational Sales Assistant

**Submission Date**: 20 October 2026  
**Project**: Electronics Sales Assistant (AI Engineer Assessment)  
**Status**: Day 2 Milestone Delivered & Verified  

---

## 1. Executive Summary

Today we transitioned the Day 1 foundation into a functional, end-to-end conversational sales assistant. The system processes customer messages in natural language, updates structured requirement memory in PostgreSQL, clarifies ambiguous or incomplete requests, enforces strict eligibility filters against 36 synthetic catalogue items, computes deterministic category-specific ranking, and returns grounded product recommendations with explicit reasons and trade-offs.

Automated testing covers 58 backend tests with 100% passing status, frontend TypeScript validation and production bundling succeeded without errors, and end-to-end smoke checks passed against both PostgreSQL and the Google Gemini Developer API.

---

## 2. Completed Features

| Milestone Item | Status | Verification Detail |
|---|---|---|
| **External LLM Integration** | Completed | Google Gemini Developer API using free tier with verified model `gemini-3.1-flash-lite`. Structured output constrained by schema. Server-side key only. |
| **Structured Conversation Memory** | Completed | Persistent `Requirements` model in PostgreSQL JSONB/SQLite JSON: tracks category, intended uses, mandatory constraints, soft preferences, explicit no-preference answers, and unresolved ambiguities. |
| **State Merge Engine** | Completed | Omission retains existing state; non-null sets/replaces; explicit null/empty clears; category switching removes incompatible specifications while retaining budget and brand. |
| **Conversation Controller** | Completed | `POST /api/v1/conversations/{id}/messages` fully implemented. External LLM called outside database transactions. Optimistic concurrency control via timestamp check. |
| **Clarification Policy** | Completed | Focuses on material gaps (missing category, vague requests lacking budget/use, or conflicting constraints). Complete requests search immediately on turn 1. |
| **Eligibility & Ranking Engine** | Completed | Parameterized SQL query + strict in-memory specification checks. Missing required specifications (`LAP-023`) never satisfy constraints. Deterministic heuristic ranking with stable tie-breaking. |
| **Grounded Responses** | Completed | Product cards generated strictly from database fields. Up to 2 recommendations, 1 if only one qualifies, or an honest no-match explanation with proposed adjustment. |
| **React Interface** | Completed | Chat history, active requirements summary chips, grounded recommendation cards with reasons/trade-offs, clarification/no-match banners, loading state, duplicate submission prevention, and retry on error. |
| **Failure Recovery** | Completed | Controlled HTTP 422, 404, 409, 429, 502, 503, 504 error envelopes. Preserves database state on LLM failure without saving fabricated turns. |

---

## 3. Architecture & How the System Works

```
[React Frontend]
       │
       ▼ (REST / JSON)
[FastAPI Controller] ──(1. Load state & version)──► [PostgreSQL / SQLite]
       │                                                    │ (Connection released)
       ├──(2. HTTPS Structured Call)──► [Google Gemini Developer API]
       │                                (`gemini-3.1-flash-lite` Free Tier)
       │◄─(3. RequirementUpdate JSON)───┘
       │
       ├──(4. Memory Merge) ──────────► [State Engine] (retain/replace/clear)
       │
       ├──(5. Clarify or Search?)
       │      ├── If missing/conflicting ──► Returns ClarificationResponse
       │      └── If sufficient ───────────► [Ranking Engine]
       │                                           │ (Parameterized SQL)
       │                                           ▼
       │                                    [Eligibility Filter]
       │                                    (Category, max price, min specs)
       │                                           │
       │                                           ▼
       │                                    [Deterministic Scoring]
       │                                    (Use fit, preferences, capabilities)
       │                                           │
       │                                           ▼
       │                                    [Grounded Explanations]
       │
       └──(6. Atomic Concurrency Check & Commit)──► [PostgreSQL Database]
              (Save user turn, assistant turn, updated requirements)
```

### Critical Reliability Guarantees
1. **No Open Transactions during LLM Calls**: Database read connection is released before calling Google Gemini, avoiding connection pool exhaustion and transaction lock timeouts.
2. **Optimistic Concurrency Control**: When writing turns, the controller validates the record's `updated_at` timestamp. If a concurrent turn committed during model inference, HTTP 409 `concurrency_conflict` is returned.
3. **No Hallucinated Products or Specs**: Product cards and facts are extracted exclusively from retrieved database rows. No-match responses state facts honestly rather than inventing inventory.
4. **Strict Eligibility Boundary**: Hard constraints are never relaxed silently. LAP-015 at exactly ₹70,000 (7,000,000 paise) qualifies under `max_price_paise=7000000`, but is excluded under `6999999`. Missing specifications (such as `LAP-023` weight null) are treated as unknown, not satisfied.

---

## 4. Model Selection & Investigation Findings

During Day 2 model validation against Google AI Studio, account access and official endpoints were tested:
- **`gemini-3.8-flash`**: Originally documented in Day 1 planning. Real API calls repeatedly timed out (>30s) or failed with `HTTP 503: No capacity available for model gemini-3.8-flash on the server`.
- **`gemini-2.5-flash`**: Returned `HTTP 404` with provider notice: *"This model models/gemini-2.5-flash is no longer available to new users."*
- **`gemini-3.5-flash`**: Fully functional with structured output schema, but occasionally experienced temporary 503 capacity limits during peak hours.
- **`gemini-3.1-flash-lite`** (Selected & Verified): Active on the Developer API Free Tier, returns valid structured output in ~1.5 to 2.8 seconds, and zero cost.

---

## 5. Tests Actually Executed & Verification Record

All tests were executed on 20 October 2026 in the delivery workspace:

| Test Category | Suite / Command | Execution Status | Details |
|---|---|---|---|
| **Day 1 & Foundation** | `pytest tests/test_api.py` | **32 / 32 Passed** | Catalogue pagination, boundaries, invalid input, conversation isolation, health. |
| **Contract Schemas** | `pytest tests/test_contracts.py` | **8 / 8 Passed** | Schema validation, duplicate field detection, explicit null removal vs omitted. |
| **Day 2 Behaviour & Edge Cases** | `pytest tests/test_day2.py` | **18 / 18 Passed** | Vague clarification, complete search, budget revision, preference removal, no-preference retention, category switching, contradictory requirements, exact boundary, missing specs (`LAP-023`), factual matching, malformed LLM response (502), timeout (504), rate-limit (429), concurrency conflict (409), database error separation (503). |
| **Full Backend Suite** | `pytest -q` | **58 / 58 Passed** | All 58 backend tests passing with zero failures. |
| **Frontend TypeScript** | `npm run typecheck` | **Passed** | `tsc --noEmit` passed with 0 errors. |
| **Frontend Production Build** | `npm run build` | **Passed** | Vite bundled production assets cleanly. |
| **PostgreSQL Foundation** | `verify_pg_seed.py` | **Passed** | Connected to local PostgreSQL instance, 36 products present, 0 duplicates inserted on second run. |
| **PostgreSQL E2E Smoke Test** | `test_e2e_pg.py` | **Passed** | Real database transaction, conversation creation, message processing, message persistence, requirement persistence, cleanup. |
| **Real Gemini Model Smoke Check** | `test_lite_model.py` | **Passed** | Live API call with `gemini-3.1-flash-lite` returning 4 structured changes and answered no-preference in 2.1s. |

---

## 6. Outstanding Issues & Limitations

1. **PostgreSQL Test Database Privileges**: The default local user `electronics` has full schema privileges (`CREATE/DROP SCHEMA`) inside database `electronics`, but lacks server-level `CREATE DATABASE` superuser permissions to spawn a separate `electronics_test` database. Automated tests run against isolated SQLite instances, while PostgreSQL integration was verified via the dedicated smoke test scripts.
2. **Free Tier Quota Latency & Bursts**: Gemini Free Tier is subject to per-minute rate limits. In automated testing, `FakeLLMAdapter` is used exclusively to guarantee deterministic execution without consuming quota.
3. **Single Store Currency**: INR paise only; foreign currencies are rejected by contract.

---

## 7. Work Remaining for Day 3

1. **Rehearsal & Live Demo Polish**: Practice the required evaluation sequence:
   - Start vague ("I need a laptop for college") -> Observe clarification question.
   - Provide use and budget ("Programming under ₹70,000") -> Observe 2 grounded recommendations with reasons and trade-offs.
   - Revise budget ("Actually ₹60,000") -> Confirm retained programming use and updated price ceiling.
   - Remove preference ("Weight doesn't matter") -> Verify preference removal in memory.
   - Impossible constraint ("Laptop under ₹10,000") -> Observe honest no-match recovery explaining conflict and proposing ₹29,990 adjustment.
2. **Production Bundle Preview Verification**: Validate live UI with `npm run preview`.
3. **Interview Preparation**: Rehearse architectural rationale, concurrency handling, and deterministic filtering guarantees.
