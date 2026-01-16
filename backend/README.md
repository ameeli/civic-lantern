# The Civic Lantern

## Overview

The Civic Lantern is a tool for tracking campaign contributions, independent expenditures, and election data. This project pairs a FastAPI backend with a PostgreSQL database. Users can explore candidate funding, top supporters, and election totals.

## Tech Stack

- **Backend:** Python, FastAPI
- **Database:** PostgreSQL
- **ORM / Migrations:** SQLAlchemy + Alembic
- **Dependency Management:** Poetry
- **Containerization:** Docker / Docker Compose

## Local Setup

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/civic_lantern.git
cd civic_lantern
```

2. **Install dependencies**

```bash
poetry install
```

3. **Start the database via Docker Compose**

```bash
docker-compose up -d
```

4. **Run Alembic migrations**

```bash
alembic upgrade head
```

5. **Start the FastAPI server**

```bash
poetry run uvicorn civic_lantern.main:app --reload
```

## Database

- PostgreSQL database managed in Docker.
- Tables: `candidates`, `elections`, `election_candidates`, `totals_by_election`, `totals_by_candidate`, `schedule_e`, `committees`.
- Materialized views: `candidate_supporters_mv`.
- Indexes and enums set up for efficient queries.

## Ingestion Pipeline

1. Pull data from FEC API (`/candidates`, `/committees`, `/schedule_e`, `/elections/summary`).
2. Parse and transform data into SQLAlchemy models.
3. Upsert into the database tables.
4. Refresh materialized views as needed.
5. Run scheduled ingestion periodically (can use cron or Airflow for automation).
