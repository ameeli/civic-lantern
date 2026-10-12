"""End-to-end tests of the ingestion CLI: real manager, pipeline and FECClient,
FEC HTTP mocked with respx, against a scratch Postgres built by Alembic so the
materialized views exist."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx
import pytest
import respx
from aiolimiter import AsyncLimiter
from alembic.config import Config
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from alembic import command
from civic_lantern.db.models import Base
from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.ingestion_run import IngestionRun, IngestionRunStatus
from civic_lantern.jobs.ingestion import main
from civic_lantern.services.data.base import BaseService
from civic_lantern.services.fec_client import FECClient

# Where the CLI builds its FECClient and session factory.
CLIENT_TARGET = "civic_lantern.jobs.ingestion.FECClient"
SESSIONS_TARGET = "civic_lantern.jobs.ingestion.JobSessionLocal"

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"
CYCLES = [2024, 2026]
BIDEN, HARRIS, TRUMP, OTHER = "P80000722", "P00009423", "P80001571", "H0CA00001"
CANDIDATE_IDS = (BIDEN, HARRIS, TRUMP, OTHER)
ALL_RUNS = {
    ("committees", None),
    ("candidates", None),
    *(("inside_totals_by_candidate", c) for c in CYCLES),
    *(("schedule_e_totals_by_candidate", c) for c in CYCLES),
}


def _admin_url(url: URL) -> URL:
    return url.set(drivername="postgresql+psycopg2")


@pytest.fixture(scope="module")
def migrated_db_url(test_database_url):
    """A throwaway database migrated with `alembic upgrade head`, local only."""
    base = make_url(test_database_url)
    if base.host not in ("localhost", "127.0.0.1"):
        pytest.skip("end-to-end tests create databases; only run against localhost")
    name = f"civic_lantern_e2e_{uuid.uuid4().hex[:8]}"
    admin = create_engine(
        _admin_url(base), poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name)
    try:
        # No config file, so Alembic doesn't reconfigure logging.
        config = Config()
        config.set_main_option("script_location", str(ALEMBIC_DIR))
        config.set_main_option(
            "sqlalchemy.url", _admin_url(url).render_as_string(hide_password=False)
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("ALEMBIC_DATABASE_URL", raising=False)
            command.upgrade(config, "head")
        yield url.render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def migrated_db(migrated_db_url):
    """The migrated database, emptied before each test."""
    engine = create_engine(_admin_url(make_url(migrated_db_url)), poolclass=NullPool)
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    engine.dispose()
    return migrated_db_url


@pytest.fixture
def run_cli(mocker):
    """Run main(argv) against `db_url` with a fast, keyed FECClient; returns the
    exit code (0 when main returns normally)."""

    def fast_client(*args, **kwargs):
        client = FECClient(show_progress=False)
        client.api_key = "test-api-key"
        client.limiter = AsyncLimiter(max_rate=10000, time_period=1)
        client.minute_limiter = AsyncLimiter(max_rate=10000, time_period=1)
        return client

    def run(db_url, argv):
        engine = create_async_engine(db_url, poolclass=NullPool)
        mocker.patch(
            SESSIONS_TARGET, async_sessionmaker(engine, expire_on_commit=False)
        )
        mocker.patch(CLIENT_TARGET, side_effect=fast_client)
        mocker.patch("civic_lantern.jobs.manager.active_cycles", return_value=CYCLES)
        mocker.patch("civic_lantern.jobs.ingestion.configure_logging")
        try:
            main(argv=argv)
        except SystemExit as e:
            return e.code
        return 0

    return run


def _page(results: list) -> httpx.Response:
    return httpx.Response(200, json={"results": results, "pagination": {"pages": 1}})


def _route(path: str, rows_by_cycle=None, rows=None, status: int = 200):
    """Serve `path` with `rows`, or `rows_by_cycle[cycle]`, or an error status."""

    def respond(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={"error": "nope"})
        if rows_by_cycle is not None:
            return _page(rows_by_cycle.get(int(request.url.params["cycle"]), []))
        return _page(rows or [])

    return respx.get(f"{FECClient.BASE_URL}{path}").mock(side_effect=respond)


def _mock_fec(**overrides) -> dict:
    """Mock every endpoint a nightly run hits with clean data; `overrides` maps
    a path to replacement _route kwargs. Returns the routes by path."""
    defaults: Dict[str, Dict[str, Any]] = {
        "/committees/": {"rows": [{"committee_id": "C1", "name": "Alpha PAC"}]},
        "/candidates/": {
            "rows": [{"candidate_id": c, "name": c} for c in CANDIDATE_IDS]
        },
        "/candidates/totals/": {
            "rows_by_cycle": {
                cycle: [
                    {
                        "candidate_id": c,
                        "cycle": cycle,
                        "receipts": 10,
                        "disbursements": 9,
                    }
                    for c in CANDIDATE_IDS
                ]
                for cycle in CYCLES
            }
        },
        "/committee/C00828541/totals/": {"rows": [{"receipts": 5, "disbursements": 4}]},
        "/committee/C00694455/totals/": {"rows": [{"receipts": 0, "disbursements": 1}]},
        "/committee/C00703975/reports/": {
            "rows": [
                {
                    "coverage_start_date": "2024-01-01T00:00:00",
                    "coverage_end_date": "2024-06-30T00:00:00",
                    "total_receipts_period": 6,
                    "total_disbursements_period": 5,
                    "most_recent": True,
                }
            ]
        },
        "/schedules/schedule_e/totals/by_candidate/": {
            "rows_by_cycle": {
                cycle: [
                    {
                        "candidate_id": c,
                        "cycle": cycle,
                        "support_oppose_indicator": "S",
                        "total": 3,
                    }
                    for c in CANDIDATE_IDS
                ]
                for cycle in CYCLES
            }
        },
    }
    defaults.update(overrides)
    return {path: _route(path, **kwargs) for path, kwargs in defaults.items()}


def _sync_engine(db_url):
    return create_engine(_admin_url(make_url(db_url)), poolclass=NullPool)


def _query(db_url, stmt) -> list:
    engine = _sync_engine(db_url)
    with engine.begin() as conn:
        rows = list(conn.execute(stmt).all())
    engine.dispose()
    return rows


def _runs(db_url) -> dict:
    rows = _query(
        db_url,
        select(IngestionRun.ingestor_name, IngestionRun.cycle, IngestionRun.status),
    )
    return {(name, cycle): status for name, cycle, status in rows}


def _count(db_url, table: str) -> int:
    return _query(db_url, text(f"SELECT count(*) FROM {table}"))[0][0]


def _insert(db_url, *objects) -> None:
    engine = _sync_engine(db_url)
    with Session(engine) as session:
        session.add_all(objects)
        session.commit()
    engine.dispose()


@pytest.fixture
def unmigrated_db(test_database_url):
    """The test database built with create_all: tables but no materialized views."""
    engine = _sync_engine(test_database_url)
    Base.metadata.create_all(engine)
    yield test_database_url
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.mark.integration
class TestNightly:
    @respx.mock
    def test_clean_run_writes_every_table_and_refreshes_the_views(
        self, migrated_db, run_cli
    ):
        _mock_fec()

        code = run_cli(migrated_db, [])

        assert code == 0
        assert _runs(migrated_db) == {
            key: IngestionRunStatus.SUCCESS for key in ALL_RUNS
        }
        assert _count(migrated_db, "committees") == 1
        assert _count(migrated_db, "candidates") == 4
        assert _count(migrated_db, "inside_totals_by_candidate") == 8
        assert _count(migrated_db, "schedule_e_totals_by_candidate") == 8
        assert _count(migrated_db, "mv_candidate_spending_summary") == 8
        assert _count(migrated_db, "mv_election_spending_summary") == 2

    @respx.mock
    def test_a_failed_entity_fails_the_cli_but_not_the_others(
        self, migrated_db, run_cli
    ):
        _mock_fec(**{"/committees/": {"status": 404}})

        code = run_cli(migrated_db, [])

        assert code == 1
        runs = _runs(migrated_db)
        assert runs.pop(("committees", None)) == IngestionRunStatus.FAILED
        assert set(runs.values()) == {IngestionRunStatus.SUCCESS}
        assert _count(migrated_db, "mv_election_spending_summary") == 2

    @respx.mock
    def test_upsert_errors_are_a_partial_success_and_exit_zero(
        self, migrated_db, run_cli
    ):
        unknown = {
            "candidate_id": "P_UNKNOWN",
            "cycle": 2026,
            "support_oppose_indicator": "O",
            "total": 1,
        }
        schedule_e = "/schedules/schedule_e/totals/by_candidate/"
        _mock_fec(**{schedule_e: {"rows_by_cycle": {2026: [unknown]}}})

        code = run_cli(migrated_db, [])

        assert code == 0
        assert (
            _runs(migrated_db)[("schedule_e_totals_by_candidate", 2026)]
            == IngestionRunStatus.PARTIAL_SUCCESS
        )

    @respx.mock
    def test_an_active_run_skips_the_night_and_exits_zero(self, migrated_db, run_cli):
        _insert(
            migrated_db,
            IngestionRun(
                ingestor_name="committees",
                status=IngestionRunStatus.IN_PROGRESS,
                started_at=datetime.now(timezone.utc),
            ),
        )
        routes = _mock_fec()

        code = run_cli(migrated_db, [])

        assert code == 0
        assert not any(route.called for route in routes.values())


@pytest.mark.integration
class TestManualRun:
    @respx.mock
    def test_a_scope_mismatch_fails_without_a_run_row(self, migrated_db, run_cli):
        _mock_fec()

        code = run_cli(migrated_db, ["--entities", "committees", "--cycle", "2024"])

        assert code == 1
        assert _runs(migrated_db) == {}

    @respx.mock
    def test_a_failed_view_refresh_fails_the_cli(self, unmigrated_db, run_cli):
        _insert(
            unmigrated_db, *(Candidate(candidate_id=c, name=c) for c in CANDIDATE_IDS)
        )
        _mock_fec()
        argv = ["--entities", "schedule_e_totals_by_candidate", "--cycle", "2024"]

        code = run_cli(unmigrated_db, argv)

        assert code == 1
        assert _runs(unmigrated_db) == {
            ("schedule_e_totals_by_candidate", 2024): IngestionRunStatus.SUCCESS
        }

    @respx.mock
    def test_spending_without_rows_does_not_refresh_the_views(
        self, unmigrated_db, run_cli
    ):
        # A refresh would fail here (no views), so exiting 0 proves none ran.
        _mock_fec(**{"/candidates/totals/": {"rows_by_cycle": {}}})
        argv = ["--entities", "inside_totals_by_candidate", "--cycle", "2026"]

        code = run_cli(unmigrated_db, argv)

        assert code == 0
        assert _count(unmigrated_db, "inside_totals_by_candidate") == 0


@pytest.fixture
def fail_second_committee_batch():
    """Raise mid-upsert, as a dropped connection would, on the second batch."""
    inserts = []

    def on_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO committees"):
            inserts.append(statement)
            if len(inserts) == 2:
                raise RuntimeError("connection reset by peer")

    event.listen(Engine, "before_cursor_execute", on_execute)
    yield
    event.remove(Engine, "before_cursor_execute", on_execute)


@pytest.mark.integration
class TestUpsertFailure:
    @respx.mock
    def test_a_run_failing_mid_upsert_leaves_the_previous_data_whole(
        self, migrated_db, run_cli, request
    ):
        def committees(version: str) -> list:
            return [
                {"committee_id": f"C{i:04d}", "name": f"{version} {i}"}
                for i in range(1200)  # three upsert batches
            ]

        argv = ["--entities", "committees"]
        _mock_fec(**{"/committees/": {"rows": committees("old")}})
        assert run_cli(migrated_db, argv) == 0

        respx.clear()
        _mock_fec(**{"/committees/": {"rows": committees("new")}})
        request.getfixturevalue("fail_second_committee_batch")
        code = run_cli(migrated_db, argv)

        assert code == 1
        assert _runs(migrated_db) == {("committees", None): IngestionRunStatus.FAILED}
        names = _query(migrated_db, text("SELECT name FROM committees"))
        assert {name.split()[0] for (name,) in names} == {"old"}


@pytest.fixture
def drop_connection_before_second_committee_batch(migrated_db):
    """Terminate the ingestion's backend just before its second batch INSERT."""
    inserts = []

    def on_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO committees"):
            inserts.append(statement)
            if len(inserts) == 2:
                _query(
                    migrated_db,
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND pid <> pg_backend_pid()"
                    ),
                )

    event.listen(Engine, "before_cursor_execute", on_execute)
    yield
    event.remove(Engine, "before_cursor_execute", on_execute)


@pytest.mark.integration
class TestDroppedConnection:
    @respx.mock
    def test_a_dropped_connection_fails_the_run_without_row_by_row_retries(
        self, migrated_db, run_cli, request, mocker
    ):
        def committees(version: str) -> list:
            return [
                {"committee_id": f"C{i:04d}", "name": f"{version} {i}"}
                for i in range(1200)  # three upsert batches
            ]

        argv = ["--entities", "committees"]
        _mock_fec(**{"/committees/": {"rows": committees("old")}})
        assert run_cli(migrated_db, argv) == 0

        respx.clear()
        _mock_fec(**{"/committees/": {"rows": committees("new")}})
        row_by_row = mocker.spy(BaseService, "_process_batch_individually")
        request.getfixturevalue("drop_connection_before_second_committee_batch")
        code = run_cli(migrated_db, argv)

        assert code == 1
        status, error = _query(
            migrated_db, select(IngestionRun.status, IngestionRun.error_message)
        )[0]
        assert status == IngestionRunStatus.FAILED
        assert "connection was closed" in error
        assert "rolled back" not in error
        assert row_by_row.call_count == 0
        names = _query(migrated_db, text("SELECT name FROM committees"))
        assert len(names) == 1200
        assert {name.split()[0] for (name,) in names} == {"old"}
