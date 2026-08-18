# The Civic Lantern — Backend

## Overview

The Civic Lantern is a campaign finance transparency platform that tracks
outside spending (independent expenditures) alongside candidates' own
fundraising, using data ingested from the FEC (Federal Election Commission)
API. The backend is a FastAPI service backed by PostgreSQL, exposing
read-only endpoints over candidate, committee, and campaign-spending data.

## Tech Stack

- **Language / Framework:** Python 3.11+, FastAPI
- **Database:** PostgreSQL 15
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
│   ├── data/        # BaseService[T] + per-table services (query/upsert logic)
│   ├── fec_client.py     # FECClient: paginated, rate-limited, retrying HTTP client
│   └── fec_exceptions.py # FEC error hierarchy
├── jobs/            # Ingestion orchestration (manager, ingestion entrypoint, ingestors/)
├── utils/           # logging setup, raw-FEC-JSON -> validated-schema transformers
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
| `TEST_DATABASE_URL_ASYNC` | yes | Async connection string for integration tests |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | yes | Individual DB connection parameters |
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
| GET | `/` | `cycle`, `limit`/`offset`, `sort_by` (e.g. `outside_total`, `influence_ratio`), `order` | Paginated candidate spending summaries, joined with candidate info |

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
   exponential backoff (2s–600s, 3 attempts).
2. Each ingestor in `jobs/ingestors/` calls one client method, transforms the
   raw JSON through a Pydantic schema (`utils/transformers.py`, invalid/
   duplicate records are logged and skipped), and upserts via its
   `services/data/*Service` (`INSERT ... ON CONFLICT DO UPDATE`, batched with
   row-by-row fallback on batch failure — see `BaseService.upsert_batch`).
3. `IngestionManager` (`jobs/manager.py`) owns a shared `FECClient` and runs
   ingestors in dependency order via `INGESTOR_REGISTRY`
   (`jobs/ingestors/__init__.py`): `committees` → `candidates` →
   `inside_totals_by_candidate` → `schedule_e_totals_by_candidate`.
4. After a batch that includes either totals ingestor, the manager refreshes
   both materialized views (see [Materialized views](#materialized-views)).

| Ingestor | FEC data | Upserts into |
|---|---|---|
| `CandidateIngestor` | `/v1/candidates/` | `candidates` |
| `CommitteeIngestor` | `/v1/committees/` | `committees` |
| `InsideTotalsByCandidateIngestor` | `/v1/candidates/totals/` (summed across primary+general) | `inside_totals_by_candidate` |
| `ScheduleETotalsByCandidateIngestor` | Schedule E independent-expenditure totals | `schedule_e_totals_by_candidate` |

**Running ingestion:** there is currently no CLI or scheduled job. The only
entrypoint is `civic_lantern/jobs/ingestion.py`'s `if __name__ == "__main__"`
block, which is hardcoded to ingest only `schedule_e_totals_by_candidate` for
the 2024 cycle:

```bash
poetry run python -m civic_lantern.jobs.ingestion
```

To run the full pipeline or other entities, call `ingest()` /
`IngestionManager` programmatically, e.g. `ingest(entities=None)` to run
every registered ingestor.

> **Known limitation:** `ScheduleETotalsByCandidateIngestor` calls
> `FECClient.get_outside_spending_totals()`, which references
> `self.outside_spending_url` — an attribute that is never set in
> `FECClient.__init__`. Calling this ingestor as-is raises `AttributeError`.
> This needs a fix before Schedule E ingestion will work end to end.

## Testing

```bash
poetry run pytest                                              # All tests
poetry run pytest -m unit                                      # Unit tests only (mocked DB/HTTP)
poetry run pytest -m integration                                # Integration tests (needs a running DB)
poetry run pytest tests/unit/test_transformers.py::test_name    # Single test
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
```
