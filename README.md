# Civic Lantern

**Illuminating dark money flows in American politics.**

Civic Lantern is a campaign finance transparency platform that ingests data from the [Federal Election Commission (FEC) API](https://api.open.fec.gov/developers/) and exposes it through a clean REST API. It tracks both inside spending (official candidate disbursements) and outside spending (independent expenditures from Super PACs and dark money groups), making it easy to see who is funding — or targeting — a candidate.

---

## Why This Exists

Campaign finance data is public, but the FEC's raw data is enormous, inconsistently structured, and hard to query. Civic Lantern pipelines that data into a structured PostgreSQL database and surfaces it through queryable endpoints. The goal is to make influence patterns visible — which candidates depend heavily on outside money, which face the most opposition spending, and how election cycles compare.

---

## Architecture

```
civic-lantern/
├── backend/        # FastAPI + PostgreSQL data pipeline and REST API
└── frontend/       # Next.js UI — election spending dashboard
```

### Backend Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| Database | PostgreSQL 15 |
| ORM | SQLAlchemy 2.0 (async) |
| Validation | Pydantic v2 |
| Migrations | Alembic |
| HTTP client | httpx (async) |
| Rate limiting | aiolimiter |
| Retry logic | tenacity |
| Package manager | Poetry |

### Frontend Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router) |
| Language | TypeScript 5 |
| UI library | React 19 |
| Styling | Tailwind CSS 4 |
| Build tool | Next.js Turbo |
| Package manager | npm |

---

## Key Features

### Election Spending Dashboard

The frontend surfaces campaign finance data as a readable, newspaper-style UI. For a given election cycle it displays:

- **Direct Campaign Spending** — total official candidate disbursements (inside money), with plain-language context explaining donation limits and candidate accountability
- **Independent Expenditures** — total outside spending from Super PACs and dark money groups (support + oppose combined), with context on the absence of contribution caps

Data is fetched server-side via Next.js React Server Components and streamed to the client using `<Suspense>` boundaries, so each metric loads independently without blocking the page.

### Resilient Data Ingestion Pipeline

- Fetches paginated data from the FEC API with a rate limiter respecting the 900 req/hr cap
- Validates every record through Pydantic schemas at ingestion boundaries — malformed records are logged and skipped without halting the pipeline
- Idempotent batch upserts (`INSERT ... ON CONFLICT DO UPDATE`) mean the pipeline is safe to re-run at any time
- On batch failure, falls back to row-by-row inserts to isolate the bad record rather than dropping the whole batch

### Analytics via Materialized Views

A PostgreSQL materialized view (`mv_election_spending_summary`) pre-computes election-level metrics:

- **Influence ratio** — outside spending (support + oppose) relative to the candidate's own disbursements
- **Vulnerability factor** — opposition spending relative to the candidate's disbursements

These are refreshed `CONCURRENTLY` so reads are never blocked during an update.

### Automatic Timestamps via PostgreSQL Triggers

All models use a `TimestampMixin` backed by a server-side PostgreSQL trigger. `created_at` is set at insert time and excluded from upsert updates; `updated_at` is managed entirely by the database, eliminating application clock skew.

---

## API Overview

Base path: `/api/v1`

### Candidates

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/candidates` | List candidates — filterable by state, office, election cycle; sortable and paginated |
| `GET` | `/candidates/{candidate_id}` | Full detail for a single candidate |
| `GET` | `/candidates/spending` | All candidate spending totals, paginated |
| `GET` | `/candidates/{candidate_id}/spending` | Spending history across cycles for one candidate |

### Elections

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/elections/spending` | All election-level spending summaries |
| `GET` | `/elections/spending/{cycle}` | Spending summary for a specific election cycle |

Interactive docs available at `/docs` (Swagger UI) when the server is running.

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- [Poetry](https://python-poetry.org/)
- Docker (for PostgreSQL)
- An [FEC API key](https://api.data.gov/signup/) (free)

### Backend

```bash
# 1. Clone the repo
git clone https://github.com/your-username/civic-lantern.git
cd civic-lantern/backend

# 2. Install dependencies
poetry install

# 3. Start PostgreSQL
docker-compose up -d

# 4. Configure environment
cp .env.example .env
# Add your FEC_API_KEY and database connection strings to .env

# 5. Apply migrations
poetry run alembic upgrade head

# 6. Start the server
poetry run uvicorn civic_lantern.main:app --reload
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the interactive API explorer.

### Running the Ingestion Pipeline

```bash
poetry run python -m civic_lantern.jobs.ingestion
```

### Frontend

```bash
cd civic-lantern/frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The UI will be available at `http://localhost:3000`. It expects the backend API to be running at `http://localhost:8000`.

---

## Testing

```bash
poetry run pytest                     # All tests
poetry run pytest -m unit             # Unit tests only (no DB required)
poetry run pytest -m integration      # Integration tests (requires running DB)
poetry run pytest --cov=civic_lantern # With coverage report
```

Tests are organized into unit tests (mocked dependencies, httpx via `respx`) and integration tests (real PostgreSQL, real SQLAlchemy sessions). Async support via `pytest-asyncio`.

---

## Data Model

The core tables:

| Table | Description |
|---|---|
| `candidates` | Candidate records keyed on FEC `candidate_id` |
| `candidate_spending_totals` | Official disbursements and receipts per candidate per cycle |
| `schedule_e` | Individual independent expenditure records |
| `committees` | PAC and committee registrations |
| `elections` | Election metadata |
| `election_candidates` | Many-to-many join of candidates to elections |
| `mv_election_spending_summary` | Materialized view — election-level analytics |

---

## Project Status

The backend data pipeline and REST API are functional. The frontend is live with an election spending dashboard for the 2024 cycle. Current development is focused on expanding ingestion coverage, adding deeper analytical endpoints, and building out additional frontend views.

---

## License

This project is open source. See [LICENSE](LICENSE) for details.
