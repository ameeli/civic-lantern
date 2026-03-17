import logging
from datetime import datetime, timezone

import pytest

from civic_lantern.utils.logging import UTCFormatter, configure_logging


def _make_record(utc_dt: datetime) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="test", args=(), exc_info=None,
    )
    record.created = utc_dt.timestamp()
    return record


@pytest.mark.unit
class TestUTCFormatter:
    """UTCFormatter renders log timestamps in UTC."""

    def test_formattime_winter(self):
        """UTC timestamp stays in UTC in January."""
        utc_dt = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        record = _make_record(utc_dt)
        formatter = UTCFormatter()

        result = formatter.formatTime(record)

        assert "18:00:00" in result
        assert "+00:00" in result

    def test_formattime_summer(self):
        """UTC timestamp stays in UTC in July."""
        utc_dt = datetime(2024, 7, 15, 18, 0, 0, tzinfo=timezone.utc)
        record = _make_record(utc_dt)
        formatter = UTCFormatter()

        result = formatter.formatTime(record)

        assert "18:00:00" in result
        assert "+00:00" in result

    def test_formattime_respects_datefmt(self):
        """datefmt parameter is applied to the UTC time."""
        utc_dt = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        record = _make_record(utc_dt)
        formatter = UTCFormatter()

        result = formatter.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z")

        assert result == "2024-01-15T18:00:00+0000"

    def test_formattime_without_datefmt_returns_isoformat(self):
        """Without datefmt, formatTime returns full ISO 8601 string."""
        utc_dt = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        record = _make_record(utc_dt)
        formatter = UTCFormatter()

        result = formatter.formatTime(record, datefmt=None)

        assert result == "2024-01-15T18:00:00+00:00"


@pytest.mark.unit
class TestConfigureLogging:
    """configure_logging() installs UTCFormatter on the root logger."""

    def test_root_logger_has_utc_formatter_after_configure(self):
        """After configure_logging(), root logger's handler uses UTCFormatter."""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            configure_logging()
            assert any(
                isinstance(h.formatter, UTCFormatter)
                for h in root.handlers
            )
        finally:
            root.handlers = original_handlers

    def test_configure_logging_sets_info_level(self):
        """configure_logging() sets root logger level to INFO."""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        root.handlers.clear()

        try:
            configure_logging()
            assert root.level == logging.INFO
        finally:
            root.handlers = original_handlers
            root.setLevel(original_level)
