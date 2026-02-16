# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Civic Lantern is a campaign finance transparency platform that tracks dark money flows in politics. The backend is built with FastAPI + PostgreSQL, ingesting and analyzing campaign contributions, independent expenditures, and election data from the FEC API.

**Tech Stack:** Python, FastAPI, PostgreSQL, SQLAlchemy 2.0 (async), Pydantic v2, Poetry

## Architecture

### Project Structure

- **`civic_lantern/core/`** — Pydantic Settings config, loaded from `.env` via `get_settings()` (cached with `lru_cache`)
- **`civic_lantern/services/`** — Business logic. `BaseService[T]` provides generic async upsert with batch processing and row-by-row fallback. `FECClient` is an async HTTP client with rate limiting (aiolimiter) and retry (tenacity)
- **`civic_lantern/schemas/`** — Pydantic v2 models for validation and transformation of incoming FEC data (name normalization, district padding, etc.)
- **`civic_lantern/db/`** — SQLAlchemy 2.0 async models with `TimestampMixin` (auto `created_at`/`updated_at` via PostgreSQL trigger). Session factory in `session.py`
- **`civic_lantern/jobs/`** — Ingestion pipeline orchestration
- **`civic_lantern/utils/`** — Transformers that validate raw API data through Pydantic schemas, skipping invalid records
- **`alembic/`** — Database migrations

### Data Ingestion Flow

1. `FECClient` fetches paginated data from FEC API with rate limiting (900 req/hr)
2. Transformers validate via Pydantic schemas, logging and skipping invalid records
3. Services perform batch upsert (`INSERT ... ON CONFLICT DO UPDATE`) with configurable batch size (default 500)
4. On batch failure, falls back to row-by-row inserts to isolate bad records
5. Materialized views refreshed as needed

**Key Principle:** All FEC data ingestion is idempotent. Handle malformed data gracefully, log processing errors for manual review, and validate at ingestion boundaries.

### Error Handling Pattern

Custom exception hierarchy rooted in `FECException`. Errors are classified as retryable (`FECRateLimitError`, `FECServerError`) or non-retryable. The retry decorator uses exponential backoff (2s min, 600s max). HTTP status codes are mapped to specific exception types in `FECClient`.

### Database

PostgreSQL 15 via Docker. All models use `TimestampMixin` — a PostgreSQL trigger function `set_updated_at()` handles `updated_at` automatically. `created_at` is preserved during upserts by excluding it from the update set.

## Commands

### Setup

```bash
poetry install                  # Install all dependencies (including dev)
docker-compose up -d            # Start PostgreSQL
poetry run alembic upgrade head # Apply migrations
```

### Server

```bash
poetry run uvicorn civic_lantern.main:app --reload
```

### Database Migrations

```bash
poetry run alembic upgrade head                               # Apply migrations
poetry run alembic revision --autogenerate -m "description"   # Create new migration
```

### Tests

```bash
poetry run pytest                          # Run all tests
poetry run pytest -m unit                  # Unit tests only
poetry run pytest -m integration           # Integration tests only (requires running DB)
poetry run pytest tests/unit/test_transformers.py::test_name  # Single test
poetry run pytest --cov=civic_lantern      # With coverage
```

### Linting & Formatting

```bash
poetry run ruff check .            # Lint (pycodestyle, pyflakes, isort)
poetry run ruff check --fix .      # Lint with auto-fix
poetry run black .                 # Format
poetry run mypy .                  # Type check
```

## Code Conventions

- Use type hints for all function signatures
- Docstrings for all public functions and classes
- TDD preferred — write tests first
- Create feature branches from main; keep commits focused and atomic

## Testing

Tests use markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`

Integration tests require a running PostgreSQL instance and `TEST_DATABASE_URL_ASYNC` in `.env`.

### Patterns

- **Unit tests:** Mock external dependencies (httpx via `respx`, database via `pytest-mock`)
- **Integration tests:** Real test database, tables created/dropped per test session via SQLAlchemy metadata
- **Async tests:** Use `pytest-asyncio`
- **External APIs:** Mock FEC API calls to avoid rate limits during testing
- Validate idempotency of ingestion operations

## FEC Data Handling

- FEC data can be inconsistent — some fields may be null or malformed, always validate
- Candidate IDs are the primary key for linking records across tables
- Watch for duplicate entries and handle deduplication
- All dates should be stored in UTC

## Environment Configuration

`.env` file must include:
- Database connection strings (including `TEST_DATABASE_URL_ASYNC` for integration tests)
- FEC API key
