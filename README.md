# Ask FEMA: an LLM Q&A agent over OpenFEMA data

[![CI](https://github.com/cbogdewi/fema-qa-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/cbogdewi/fema-qa-agent/actions/workflows/ci.yml)
[![Deploy](https://github.com/cbogdewi/fema-qa-agent/actions/workflows/deploy.yml/badge.svg)](https://github.com/cbogdewi/fema-qa-agent/actions/workflows/deploy.yml)

Ask plain-English questions about U.S. disaster declarations, such as *"How many hurricane disasters has
Florida had since 2010?"*. The agent writes a SQL query, runs it on a fresh copy of FEMA's public data, and
answers **only from the rows it got back**. The SQL and the data behind each answer are shown with it.

**Stack:** FastAPI · DuckDB · gpt-oss-120b on Groq (free tier) · Docker · AWS Lambda (container image + function URL) ·
GitHub Actions with OIDC · golden-set eval suite as a deploy gate. **Running cost: $0** at demo traffic.

## How it works

```
question ──► LLM plans SQL ──► SQL guard ──► DuckDB (read-only) ──► LLM writes answer from rows ──► answer + SQL + rows + chart
              │                    │
              └ off-topic? refuse  └ single SELECT, known tables only, no file/system functions, row-limited
```

| Piece | Where |
|---|---|
| Agent (plan → validate → query → answer, one repair retry) | `app/agent.py` |
| SQL safety guard | `app/sql_guard.py` |
| Provider adapter (Groq / Gemini / offline fake) | `app/llm.py` |
| API: `POST /api/ask`, `GET /api/stats`, `GET /api/evals`, `GET /health` | `app/main.py` |
| Dashboard UI (also embedded at dashboard.bogdewic.com) | `app/static/index.html` |
| OpenFEMA loader (nightly) | `etl/load_openfema.py` |
| Eval suite (30 golden questions) | `evals/` |
| AWS bootstrap (OIDC, ECR, IAM) | `infra/bootstrap.yaml` |

## Evals

`evals/cases.yaml` holds 30 golden questions in seven categories: counting, geography, ranking, named events,
dollars, out-of-scope refusals, and prompt-injection attempts. Expected answers are **not hard-coded**. Each case has a
reference SQL query that runs against the same freshly loaded data, so the suite stays correct as FEMA updates it.

A numeric case passes only if the number is **grounded** (it appears in the agent's query result) **and
stated** (it appears in the answer). Every push to `main` and the nightly refresh run the suite with the real model.
A pass rate below 80% fails the pipeline and blocks the deploy. The latest report is shown on the dashboard.

Unit tests (`tests/`) run offline against a synthetic database with a deterministic fake LLM.

## Security notes

- The user's question is treated as untrusted. It is fenced in tags, the model is told to ignore any
  instructions inside it, and the injection cases in the eval suite test this.
- The SQL guard allows only a single `SELECT`/`WITH` over two known tables, with file, system and `COPY`/`ATTACH`
  functions blocked. The database is opened **read-only** with external access disabled.
- Per-IP rate limiting protects the free LLM quota. The Groq free tier returns 429 errors instead of billing.
- GitHub Actions reaches AWS through **OIDC**, so no long-lived AWS keys exist. The deploy role can only be
  assumed from `main` of this repository, and it can only touch this one function and image repository.

## Run locally

```bash
pip install -r requirements-dev.txt
python etl/load_openfema.py                  # builds data/fema.duckdb (~1 min)
export GROQ_API_KEY=...                       # free key from console.groq.com
uvicorn app.main:app --reload                 # http://localhost:8000
pytest -q                                     # offline unit tests
python -m evals.run_evals                     # full eval suite against the real model
docker compose up --build                     # or run the Lambda image locally
```

## Deploy your own (one-time setup)

1. **Groq key:** in the repo, go to Settings → Secrets and variables → Actions → *Secrets* and add `GROQ_API_KEY`.
2. **AWS bootstrap:** in the AWS console, open **CloudShell** (the `>_` icon) and run:
   `curl -fsSL https://raw.githubusercontent.com/cbogdewi/fema-qa-agent/main/infra/bootstrap.sh | bash`
3. **Role:** copy the printed role ARN into Settings → Secrets and variables → Actions → *Variables* as `AWS_ROLE_ARN`.
4. Re-run the **Deploy** workflow. The job summary prints the live URL.

## Data

[OpenFEMA](https://www.fema.gov/about/openfema/data-sets): *Disaster Declarations Summaries (v2)* and
*FEMA Web Disaster Summaries (v1)*. This product uses the FEMA OpenFEMA API but is not endorsed by FEMA.
Note that declarations have one row per designated area (county), so the agent counts `DISTINCT disaster_number`.

Design decisions are recorded in [`docs/decisions.md`](docs/decisions.md).
