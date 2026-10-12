"""End-to-end tests for the ingestion CLI's exit code against the test Postgres."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from civic_lantern.jobs.ingestion import main


@pytest.mark.integration
def test_cli_exits_nonzero_when_mv_refresh_fails(test_database_url, mocker):
    # The test DB has no materialized views, so the real REFRESH fails.
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    mocker.patch(
        "civic_lantern.jobs.manager.JobSessionLocal", async_sessionmaker(engine)
    )
    run = mocker.patch(
        "civic_lantern.jobs.manager.run_ingestion",
        return_value={"inserted": 1, "updated": 0, "errors": 0, "failed_ids": []},
    )
    mocker.patch("civic_lantern.jobs.manager.FECClient")
    mocker.patch("civic_lantern.jobs.ingestion.configure_logging")

    with pytest.raises(SystemExit) as exc_info:
        main(argv=["--entities", "inside_totals_by_candidate", "--cycle", "2024"])

    assert exc_info.value.code == 1
    run.assert_awaited_once()  # the entity succeeded, so the refresh failed it
