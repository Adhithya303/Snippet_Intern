# External AI API decision - Day 1 architecture

Decision date: 19 October 2026. Status: selected for Day 2 integration; no real API call or account quota has been verified yet.

## Selected service

- Provider: Google Gemini Developer API.
- Planned model: Gemini 3.8 Flash (`gemini-3.8-flash`).
- Access: a Google AI Studio API key belonging to a Free-tier project.
- Cost requirement: no paid billing and no automatic paid fallback.

Google's current pricing page lists standard input/output tokens for this model as free on the Free tier. Its model documentation lists structured outputs as supported. Actual account/model eligibility and available quota must be checked in AI Studio before integration; free access is not an unlimited-capacity promise.

## Role in this project

The hosted pretrained model will interpret a customer message together with relevant saved requirements and propose a structured requirements update. Pydantic checks the output shape; application business rules check its meaning. The model does not execute SQL, directly change state, or choose invented product facts.

The local FastAPI application maintains state, decides when clarification is needed, enforces confirmed hard constraints, queries PostgreSQL, ranks eligible products and assembles grounded comparisons. Factual explanations can use templates and stored fields to reduce calls and avoid unsupported claims.

There is no local training, fine-tuning, GPU setup or model download. The 36 synthetic products are database records, not model-training data.

## Planned request flow

React message -> FastAPI -> saved requirements -> backend Gemini API adapter -> structured proposed changes -> validation and merge -> clarify or database search -> mandatory filtering -> deterministic ranking -> grounded response -> persisted turn/state.

## Configuration for Day 2

Set `GEMINI_API_KEY` privately in the backend environment and `GEMINI_MODEL=gemini-3.8-flash`. Never put the key in React, a `VITE_*` variable, Git, a screenshot, a prompt or a log. The current Day 1 application does not consume these settings or call Gemini; they are a documented integration plan.

Use a project that remains on the Free tier. Do not link/enable paid billing to work around quota limits. Do not assume an application flag alone prevents charges if a paid project/key is used. Confirm the project's tier in AI Studio.

## Quota and reliability plan

- Target one extraction call per user turn; use templates for factual comparison text.
- Send only necessary message/context fields and bound the response size.
- Use a timeout and at most one bounded retry for recoverable failures, respecting provider retry guidance.
- Treat quota errors as temporary unavailability; never silently relax requirements or manufacture a recommendation.
- Use deterministic mocked responses for automated tests so they consume no API quota.
- Check active requests-per-minute, tokens-per-minute and requests-per-day limits in AI Studio. Quotas are project-level, may change and are not guaranteed.
- Perform a small real-key test before the demo; preserve quota for the meeting.
- If free access is unavailable or insufficient, report it and re-evaluate another free option rather than activating paid usage.

No web-search grounding, shopping API or other paid add-on is needed; the catalogue remains the sole product source.

## Data consideration

Google's Free-tier pricing states submitted content may be used to improve its products. Use synthetic demonstration requests and minimal necessary state. Never send PostgreSQL credentials, API keys or personal customer information to the model.

## Day 1 status

This change updates architecture and documentation only. The message endpoint remains HTTP 501 until the actual agent is implemented. Existing backend/frontend verification belongs to the foundation build and does not establish working Gemini integration.

## Updating an already-open local project

The refreshed ZIP contains the same application code with updated documentation. If you have already modified your local project in Antigravity, do not replace that folder wholesale. Copy the revised docs/ files and review README.md, START_HERE.md, the architecture generation script and the commented .env.example additions. Preserve your real .env and all local code changes.
