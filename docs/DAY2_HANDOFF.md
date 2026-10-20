# Day 2 implementation handoff

Continue this repository; do not rebuild the foundation. Read README.md, architecture.md, agent_contracts.py, and the tests first.

## Goal

Turn the explicit 501 messages placeholder into a real conversational recommendation agent. Preserve all required endpoints and existing passing tests, updating placeholder-specific tests to match implemented behaviour.

## Implementation order

1. Use the selected Google Gemini Developer API free tier with `gemini-3.8-flash`; first confirm model access and active free quota in AI Studio. Read EXTERNAL_API_DECISION.md. Do not enable paid billing or paid fallback. Keep credentials server-side in environment variables. Do not hard-code or expose them.
2. Implement the LLMAdapter.extract contract with a bounded timeout, validated output and a bounded recovery policy. The model proposes changes; it does not receive authority to execute SQL or modify the database directly.
3. Extend typed changes for category-specific hard constraints/preferences. Add strict update typing, duplicate-field detection and handling of genuinely ambiguous/conflicting requests. Omission means retain; explicit null/list clearing means remove; a new value means replace. Track no-preference answers separately.
4. Implement state merge and category-change handling. Remove or clarify incompatible laptop fields when switching to headphones. Preserve unrelated requirements. Do not silently convert inferred uses to mandatory specifications.
5. Implement a small clarification policy. Ask only about information that materially changes the candidate set or suitability. A fully specified request can search on the first turn. "No budget limit" is answered, not missing. "Around INR 70,000" is not necessarily a hard ceiling.
6. Expand the controlled catalogue query interface with allowlisted fields/operators. Mandatory constraints exclude products before scoring. Unknown required fields do not qualify as verified matches. No model-generated SQL.
7. Implement deterministic category-specific ranking with documented feature normalization and weights. Avoid calling the heuristic an objective probability or benchmark. Use stable tie-breaking.
8. Build response cards from selected database IDs/fields. Validate all model-generated prose or use evidence-based templates. Never invent facts. Return at most two; one if only one matches. No-match recovery asks permission to adjust a constraint before applying it.
9. Persist successful user/assistant turns and requirement state consistently. Define what is stored after timeouts/failed processing. Add a per-conversation concurrency policy (version check or serialization) so simultaneous turns cannot overwrite each other.
10. Enable the React chat composer, requirement summary and comparison cards. Show user-relevant facts, not private reasoning or fabricated confidence.
11. Test complete conversations with deterministic model substitutes, then execute a small real-model smoke set. Record which model and cases were actually tested.
12. Update README.md with actual progress, remaining work, limitations and run instructions before the Day 2 9:00 PM check-in.

## Acceptance scenarios

- Vague college laptop request prompts an appropriate use-case question.
- A complete request searches without mandatory filler questions.
- Reduced budget replaces the old ceiling without forgetting use or preferences.
- Explicit preference removal stops influencing ranking.
- Hard budget is never violated, including exact-boundary cases.
- Mandatory missing specs prevent a product being represented as a verified match.
- One or zero eligible records are reported accurately.
- Different conversations remain isolated.
- Malformed model output, timeouts and database errors preserve valid state.
- Out-of-scope requests and injected SQL/tool instructions cannot broaden tool authority.
- Local-ML advice is qualified by workload and stored GPU/VRAM data; no unsupported performance promises.

## Demo sequence

Start vague -> clarify use and budget -> show two grounded products -> lower budget -> demonstrate retained preferences -> add an impossible condition -> show honest no-match recovery. Then explain one test and the deterministic filtering code.

## Keep scope under control

No login, cart, payments, voice, scraping, multi-agent system or vector database is needed. Finish core reliability before visual embellishments. Reserve Day 3 for verification, documentation and rehearsal; the meeting time is not supplied in the brief.
