# Architecture decisions

## ADR-1: Text-to-SQL over DuckDB instead of vector RAG
**Context:** FEMA declaration data is structured, and most questions are counts, rankings and trends.
**Decision:** The LLM writes SQL against a local DuckDB file, and a second call phrases the answer from the result rows.
**Consequences:** Numbers are exact and auditable, because the SQL and rows are shown to the user. Free-text questions
about narratives are out of scope.

## ADR-2: Free LLM (Groq, Llama 3.3 70B) behind a provider adapter
**Context:** The project must run at $0.
**Decision:** Use the Groq free tier through its OpenAI-compatible API. Gemini's free tier is configured as an
alternative, and a deterministic fake is used for tests.
**Consequences:** Rate limits cap throughput, and the API returns 429 errors rather than billing. Switching to
Claude or another provider is a one-file change. FEMA data is public, so free-tier data terms are acceptable.

## ADR-3: AWS Lambda container image + function URL (not App Runner/ECS)
**Context:** The project needs to run continuously at $0 while keeping Docker as the deployment unit.
**Decision:** Package the app as a Lambda container image with Mangum, exposed through a function URL.
**Consequences:** The always-free allowance (1M requests and 400k GB-seconds a month) covers demo traffic. Cold starts
take about 1–3 seconds. The same image runs locally with uvicorn.

## ADR-4: Data baked into the image, refreshed nightly
**Context:** OpenFEMA is the source of truth, and the data is small (tens of MB).
**Decision:** CI pulls from the API each night, rebuilds the DuckDB file, runs evals, and ships a new image.
**Consequences:** No database server is needed, so there is nothing to pay for or patch. Data can be up to 24 hours old.

## ADR-5: Evals as a deployment gate, with reference SQL instead of fixed answers
**Context:** LLM quality can regress silently, and FEMA data changes daily.
**Decision:** Each golden case computes its expected value from reference SQL at run time. The deploy fails
if the pass rate is below 80%.
**Consequences:** The suite never goes stale. Quality regressions from a model or prompt change block the deploy.
