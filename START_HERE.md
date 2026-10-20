# Your Day 1 delivery

## 1. Submit the architecture

Open **docs/Day1_Architecture.pdf**. It is the six-page submission document containing:

1. System architecture and component responsibilities.
2. Planned agent decision flow.
3. Database and requirement-state design.
4. Required API endpoints and reliability controls.
5. The three-day delivery plan and verification limits.
6. Selected free-tier external API: Google Gemini Developer API with Gemini 3.8 Flash.

The brief lists **19 October, 9:00 PM** for the architecture check-in. Use the organizer's confirmed timezone and submission channel. Aim to submit before 8:30 PM to leave a buffer.

The accompanying docs/architecture.html works offline. Editable Markdown, SVG diagrams and their generation script are also included.

## 2. Know what has been built

- FastAPI backend with five working required routes.
- An explicitly unavailable AI message route (HTTP 501).
- React catalogue interface and persistent conversation setup.
- 36 synthetic products, validated schema and repeatable seeding.
- PostgreSQL setup configuration plus a tested SQLite preview mode.
- Automated tests, dependency files and setup instructions.

**This is a Day 1 foundation, not the final AI assistant.** It does not yet ask intelligent follow-up questions, update requirements from natural language or generate recommendations.

## 3. Run it locally

Open README.md and follow **Quick preview on Windows PowerShell**. This route needs Python and Node.js but no Docker or LLM API key. Use the PostgreSQL section when Docker/PostgreSQL is available.

Keep one terminal running the backend and another running the frontend. Open http://localhost:5173. Do not open frontend/index.html directly: the application needs the build server and backend.

## 4. Check the foundation

1. Choose Laptops and apply a maximum budget of 70000 rupees.
2. Check that displayed products do not exceed that amount.
3. Try a budget of 1 rupee; the catalogue should show an empty state.
4. Clear filters and view a product's stored specifications.
5. Create a conversation, refresh the page and confirm the same ID reloads.
6. Open http://127.0.0.1:8000/docs to inspect the API.
7. Read docs/VERIFICATION.md for tests and platform limitations.

## 5. Be ready to explain these five answers

**Why FastAPI + React + PostgreSQL?** FastAPI is mandatory; React satisfies the additional FARM requirement. PostgreSQL fits structured catalogue and conversation records.

**What will the LLM do?** Interpret natural-language messages and propose structured requirement changes. The application validates and applies those changes.

**What stops an over-budget recommendation?** Mandatory constraints are applied in database/application filtering before the ranking step. Prompt instructions alone are insufficient.

**How will the assistant remember changes?** It stores current structured requirements per conversation. A new value replaces a field, an explicit removal clears it, and an omitted field leaves the old value intact.

**What is unfinished today?** Real LLM calls, state merging, clarification decisions, suitability ranking and grounded recommendation generation. PostgreSQL execution also needs verification on a suitable machine.

## Next working session

Use docs/DAY2_HANDOFF.md as the implementation brief. Finish the working AI path on Day 2, with behavioural and failure tests, and submit the progress README by the listed 9:00 PM deadline. Reserve Day 3 for verification, explanation and the Google Meet demonstration.

The supplied README contains the precise run commands. No additional AI tool is required just to run these files.
