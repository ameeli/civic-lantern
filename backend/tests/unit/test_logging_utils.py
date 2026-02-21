import logging
from datetime import datetime, timezone

import pytest

from civic_lantern.utils.logging import EasternFormatter, configure_logging


def _make_record(utc_dt: datetime) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="test", args=(), exc_info=None,
    )
    record.created = utc_dt.timestamp()
    return record


@pytest.mark.unit
class TestEasternFormatter:
    """EasternFormatter renders log timestamps in US/Eastern."""

    def test_formattime_winter_est(self):
        """UTC timestamp converts to EST (UTC-5) in January."""
        utc_dt = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        record = _make_record(utc_dt)
        formatter = EasternFormatter()

        result = formatter.formatTime(record)

        assert "13:00:00" in result
        assert "-05:00" in result

    def test_formattime_summer_edt(self):
        """UTC timestamp converts to EDT (UTC-4) in July."""
        utc_dt = datetime(2024, 7, 15, 18, 0, 0, tzinfo=timezone.utc)
        record = _make_record(utc_dt)
        formatter = EasternFormatter()

        result = formatter.formatTime(record)

        assert "14:00:00" in result
        assert "-04:00" in result

    def test_formattime_respects_datefmt(self):
        """datefmt parameter is applied to the Eastern-adjusted time."""
        utc_dt = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        record = _make_record(utc_dt)
        formatter = EasternFormatter()

        result = formatter.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z")

        assert result == "2024-01-15T13:00:00-0500"

    def test_formattime_without_datefmt_returns_isoformat(self):
        """Without datefmt, formatTime returns full ISO 8601 string."""
        utc_dt = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        record = _make_record(utc_dt)
        formatter = EasternFormatter()

        result = formatter.formatTime(record, datefmt=None)

        assert result == "2024-01-15T13:00:00-05:00"


@pytest.mark.unit
class TestConfigureLogging:
    """configure_logging() installs EasternFormatter on the root logger."""

    def test_root_logger_has_eastern_formatter_after_configure(self):
        """After configure_logging(), root logger's handler uses EasternFormatter."""
        # Reset root logger so basicConfig takes effect
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            configure_logging()
            assert any(
                isinstance(h.formatter, EasternFormatter)
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
