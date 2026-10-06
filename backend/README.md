# The Civic Lantern — Backend

## Overview

The Civic Lantern is a campaign finance transparency platform that tracks
outside spending (independent expenditures) alongside candidates' own
fundraising, using data ingested from the FEC (Federal Election Commission)
API. The backend is a FastAPI service backed by PostgreSQL, exposing
read-only endpoints over candidate, committee, and campaign-spending data.

## Tech Stack

- **Language / Framework:** Python 3.11+, FastAPI
- **Database:** PostgreSQL 17
- **ORM / Migrations:** SQLAlchemy 2.0 (async) + Alembic
- **Validation:** Pydantic v2 / pydantic-settings
- **HTTP client:** httpx, with `aiolimiter` (rate limiting) and `tenacity` (retries)
- **Dependency management:** Poetry
- **Containerization:** Docker / Docker Compose (database only)

## Project Structure

```
civic_lantern/
├── core/            # Settings (pydantic-settings), loaded from .env via get_settings()
├── api/
│   ├── deps.py      # get_db() session dependency, PaginationParams
│   └── routers/     # candidates, candidate_spending, election_spending
├── schemas/         # Pydantic models: ingestion (*In) + API response models
├── db/
│   ├── models/      # SQLAlchemy models, mixins, enums, two declarative bases
│   └── session.py   # Async engine + AsyncSessionLocal factory
├── services/
│   ├── data/        # BaseService[T] (generic upsert) + API query services
│   ├── committee_corrections.py  # Overrides and splits FEC's candidate totals miss
│   ├── fec_client.py     # FECClient: paginated, rate-limited, retrying HTTP client
│   └── fec_exceptions.py # FEC error hierarchy
├── jobs/            # pipeline.py, ingestors/ (one declaration per entity), manager, CLI
├── utils/           # logging setup
└── main.py          # FastAPI app + router registration
alembic/             # DB migrations (source of truth for schema history)
tests/                # unit/ and integration/ suites
```

## Local Setup

1. **Clone the repository and enter the backend directory**

   ```bash
   git clone https://github.com/yourusername/civic_lantern.git
   cd civic_lantern/backend
   ```

2. **Install dependencies**

   ```bash
   poetry install
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   ```

   Fill in a free FEC API key from https://api.data.gov/signup/ and adjust
   DB credentials if needed (see [Configuration](#configuration) below).

4. **Start PostgreSQL via Docker Compose**

   ```bash
   docker-compose up -d
   ```

5. **Run Alembic migrations**

   ```bash
   poetry run alembic upgrade head
   ```

6. **Start the FastAPI server**

   ```bash
   poetry run uvicorn civic_lantern.main:app --reload
   ```

   The API is served under `http://localhost:8000/api/v1`. Interactive docs
   at `http://localhost:8000/docs`.

## Configuration

Settings are defined in `civic_lantern/core/config.py` (`Settings`, a
pydantic-settings model) and loaded from `backend/.env`. `get_settings()` is
`lru_cache`d — one instance per process.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL_ASYNC` | yes | Async (asyncpg) connection string used by the app |
| `TEST_DATABASE_URL_ASYNC` | tests only | Async connection string for integration tests; never set it in deployed jobs |
| `FEC_API_KEY` | no (needed for ingestion) | API key for api.open.fec.gov, sent as an `api_key` query param |
| `ENVIRONMENT` | no (default `development`) | Environment label |
| `DEBUG` | no (default `True`) | Debug flag |

## Database

PostgreSQL, managed via Alembic migrations (`backend/alembic/versions/`).
Two SQLAlchemy declarative bases are used: `Base` for real, migration-managed
tables, and `ViewBase` for materialized views — kept separate so Alembic
autogenerate and test `create_all()/drop_all()` never try to manage the views
as ordinary tables.

### Tables

- **`candidates`** (PK `candidate_id`) — one row per FEC candidate: name, office/party/state/district, status, filing dates, and the `cycles`/`election_years` they've run in.
- **`committees`** (PK `committee_id`) — one row per FEC committee (PACs, party committees, etc.), including its type, affiliated candidate IDs, and filing metadata.
- **`inside_totals_by_candidate`** (composite PK `candidate_id, cycle`, FK → `candidates`) — a candidate's own fundraising totals (`receipts`, `disbursements`) per cycle.
- **`schedule_e_totals_by_candidate`** (composite PK `candidate_id, cycle, support_oppose_indicator`, FK → `candidates`) — independent-expenditure ("outside spending") totals per candidate/cycle, split by support (`S`) vs. oppose (`O`).

All four tables carry `created_at`/`updated_at` via `TimestampMixin` (see [Triggers](#triggers)). See `civic_lantern/db/models/` for exact columns/types, and `alembic/versions/` for schema history.

### Materialized views

**`mv_candidate_spending_summary`** — per-candidate, per-cycle inside vs. outside spending, with a unique index on `(candidate_id, cycle)` (required for concurrent refresh). Aggregates `inside_totals_by_candidate` and `schedule_e_totals_by_candidate` (LEFT JOINed so a candidate appears even with only one side of data), then computes:
- `influence_ratio = (outside_support + outside_oppose) / inside_disbursements`
- `vulnerability_factor = outside_oppose / inside_disbursements`

**`mv_election_spending_summary`** — cycle-level rollup, unique index on `(cycle)`. Aggregates `mv_candidate_spending_summary` into per-cycle totals (`candidate_count`, summed inside/outside totals) plus a `global_influence_ratio`.

Both views are refreshed by application code, not a DB trigger or cron:
`IngestionManager.refresh_spending_stats()` (`civic_lantern/jobs/manager.py`)
runs `REFRESH MATERIALIZED VIEW CONCURRENTLY` on `mv_candidate_spending_summary`
first, then `mv_election_spending_summary` (order matters — the latter reads
from the former). This runs automatically after any ingestion batch that
included `inside_totals_by_candidate` or `schedule_e_totals_by_candidate`.

### Enums

- `OfficeTypeEnum` (`office_enum`): `HOUSE="H"`, `SENATE="S"`, `PRESIDENT="P"`
- `SupportOpposeEnum` (`support_oppose_enum`): `SUPPORT="S"`, `OPPOSE="O"`
- `CommitteeTypeEnum` (`committee_type_enum`): 16 single-letter FEC committee-type codes

### Triggers

Every table with `TimestampMixin` gets a `set_updated_at_<table>` BEFORE
UPDATE trigger calling a shared `set_updated_at()` PL/pgSQL function, which
only bumps `updated_at` when a row actually changed and the caller didn't
already set it — avoiding "ghost updates" from no-op upserts. `created_at`
is excluded from `ON CONFLICT DO UPDATE` sets so it survives re-ingestion.

## API

All endpoints are read-only (`GET`) and mounted under `/api/v1`.

**`/api/v1/candidates`** (`api/routers/candidates.py`)

| Method | Path | Query params | Returns |
|---|---|---|---|
| GET | `/` | `state`, `office`, `cycle`, `limit`/`offset`, `sort_by`, `order` | Paginated list of candidates |
| GET | `/{candidate_id}` | — | Single candidate (404 if not found) |
| GET | `/{candidate_id}/spending` | — | That candidate's spending summary across all cycles |

**`/api/v1/candidate-spending`** (`api/routers/candidate_spending.py`)

| Method | Path | Query params | Returns |
|---|---|---|---|
| GET | `/` | `cycle`, `office` (`P`/`S`/`H`), `limit`/`offset`, `sort_by` (e.g. `total_spending`, `influence_ratio`), `order` | Paginated candidate spending summaries, joined with candidate info; only candidates with positive total spending |

**`/api/v1/election-spending`** (`api/routers/election_spending.py`)

| Method | Path | Query params | Returns |
|---|---|---|---|
| GET | `/` | — | All cycle-level spending summaries, newest first |
| GET | `/{cycle}` | — | One cycle's summary (must be an even year, 1980–current; 404 if no data) |

`committees`, `inside_totals_by_candidate`, and `schedule_e_totals_by_candidate`
have services (`services/data/`) but no HTTP routers — they're populated by
the ingestion pipeline only.

## Data Ingestion Pipeline

1. `FECClient` (`services/fec_client.py`) fetches paginated data from the FEC
   API (`https://api.open.fec.gov/v1`), authenticating via `FEC_API_KEY` as a
   query param. It applies two rate limiters (900 req/hour, ~60 req/min) and
   retries retryable errors (server errors, timeouts, network errors) with
   exponential backoff (2s–600s, 3 attempts). Its one public method,
   `fetch_all(endpoint, **params)`, fetches every page of an `FECEndpoint`.
2. Each entity is an `Ingestion` declaration in `jobs/ingestors/<entity>.py`,
   next to the `FECEndpoint` it reads: its scope (a date window resumed from
   the watermark, or one election cycle), Pydantic schema, table, optional
   committee corrections, and any fields summed across rows that share a key.
3. One pipeline (`jobs/pipeline.py`, `run_ingestion`) runs every declaration:
   resolve the scope, `fetch_all`, apply corrections, validate (invalid rows
   are logged and skipped, but a summing ingestion fails the run on an
   invalid row that has its key), combine rows by primary key, and upsert via
   `BaseService` (`INSERT ... ON CONFLICT DO UPDATE` on the full primary key,
   batched with row-by-row fallback — see `BaseService.upsert_batch`). Each
   run is recorded in `ingestion_runs`.
4. `IngestionManager` (`jobs/manager.py`) owns a shared `FECClient` and runs
   the declarations in `INGESTIONS` order (`jobs/ingestors/__init__.py`),
   parents before the tables that reference them: `committees` → `candidates`
   → `inside_totals_by_candidate` → `schedule_e_totals_by_candidate`.
5. After a batch that includes either per-cycle ingestion, the manager
   refreshes both materialized views (see [Materialized views](#materialized-views)).

| Ingestion | Scope | FEC data | Upserts into |
|---|---|---|---|
| `COMMITTEES_INGESTION` | date window | `/v1/committees/` | `committees` |
| `CANDIDATES_INGESTION` | date window | `/v1/candidates/` | `candidates` |
| `INSIDE_TOTALS_INGESTION` | per cycle | `/v1/candidates/totals/`, plus committee corrections | `inside_totals_by_candidate` |
| `SCHEDULE_E_TOTALS_INGESTION` | per cycle | `/v1/schedules/schedule_e/totals/by_candidate/` | `schedule_e_totals_by_candidate` |

**Running ingestion:** the CLI runs the nightly routine with no arguments, or
chosen entities with `--entities` (and `--cycle` for the two totals ingestors).
It exits 1 if any entity or the materialized view refresh fails.

```bash
poetry run python -m civic_lantern.jobs.ingestion
poetry run python -m civic_lantern.jobs.ingestion --entities inside_totals_by_candidate --cycle 2024
```

GitHub Actions runs the nightly routine daily at 10:00 UTC
(`.github/workflows/nightly-ingestion.yml`), and `manual-ingestion.yml` runs
chosen entities on demand.

## Testing

```bash
poetry run pytest                                              # All tests
poetry run pytest -m unit                                      # Unit tests only (mocked DB/HTTP)
poetry run pytest -m integration                                # Integration tests (needs a running DB)
poetry run pytest tests/unit/test_candidate_schema.py::test_name  # Single test
poetry run pytest --cov=civic_lantern                           # With coverage
```

- **Unit tests** mock `httpx` (via `respx`) and the DB session; they don't
  touch a real database.
- **Integration tests** use a real Postgres database at
  `TEST_DATABASE_URL_ASYNC`, creating/dropping tables via SQLAlchemy metadata
  per session.

## Linting & Formatting

```bash
poetry run ruff check .            # Lint (pycodestyle, pyflakes, isort)
poetry run ruff check --fix .      # Lint with auto-fix
poetry run black .                 # Format
poetry run mypy .                  # Type check
poetry run pip-audit               # Dependency vulnerability scan
```

CI (`.github/workflows/ci.yml`) runs all of these on every PR as blocking checks.
