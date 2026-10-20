# Day 1 verification record

Verified on 19 October 2026 in the delivery workspace. This report distinguishes executed checks from planned features.

| Check | Result | Scope |
|---|---|---|
| Backend automated tests | **40 passed** | Fresh isolated SQLite databases; API, catalogue, persistence and contracts |
| TypeScript type check | **Passed** | Executed by the production build script |
| Vite production build | **Passed** | React application bundled successfully |
| Browser smoke checks | **11 passed** | Chromium against the production frontend preview and live FastAPI backend |
| PDF layout review | **Passed** | Six pages rendered and visually inspected |
| PostgreSQL/Docker execution | **Not run** | No usable PostgreSQL server or Docker in the delivery environment |
| Real-model conversations and ranking | **Not implemented** | Day 2 work; no LLM API calls claimed |

## Automated backend coverage

- Correct catalogue counts and category filtering.
- Inclusive budget boundary and one-paise-below exclusion.
- Zero-budget empty result.
- Stable pagination and out-of-range pages.
- Invalid filters, malformed IDs, absent records and invalid messages.
- Conversation persistence, ordered history and separation of conversations.
- The 501 agent endpoint leaves messages and state unchanged.
- Database outage responses and sanitized errors.
- Idempotent seeding that preserves an existing record edit.
- Required API paths and explicit 501 documentation.
- Category-specific sample-data validation and update contracts.
- Explicit preference removal versus omitted change.
- Unknown versus not-applicable battery information.

One non-failing dependency deprecation warning was emitted by Starlette's TestClient about httpx. All 40 assertions/tests passed; no failing tests were suppressed. This can be addressed when upgrading the test client dependency in subsequent work.

## Browser checks executed

1. Initial catalogue loads 36 records and six cards per page.
2. Laptop category and inclusive INR 70,000 budget work.
3. Invalid budget input shows a validation message.
4. No-match catalogue state and clearing filters work.
5. Pagination changes displayed records.
6. Conversation creation persists and reload restores the saved ID.
7. Stored specification disclosure opens.
8. Simulated catalogue service failure shows an error; retry recovers.
9. A 390-pixel mobile viewport has no horizontal page overflow.
10. No uncaught browser page errors occurred.
11. The interactive API documentation endpoint is reachable.

Browser smoke checks verify the Day 1 interface only. They do not establish conversational intelligence, recommendation suitability, PostgreSQL compatibility at runtime, or production readiness.

## Re-run commands

See README.md for environment setup. From backend/, run the virtual environment's `python -m pytest -q`. From frontend/, run `npm run build` (includes TypeScript checking).

The same backend suite can target PostgreSQL using a dedicated `TEST_DATABASE_URL` ending in `_test`. The fixture isolates each test in a generated schema. This PostgreSQL path is provided but was not executed here.

## Required follow-up

Verify the PostgreSQL path on the target machine, implement the real agent, run behavioural/failure tests, and test the final submission from a clean setup before the Day 3 demonstration.

Documentation-only update: the selected free-tier Gemini API is now described in the six-page architecture. Application code is unchanged; earlier application test results are retained, not represented as new Gemini tests.
