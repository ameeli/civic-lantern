import logging
from datetime import datetime, timezone

from civic_lantern.utils.timezone import FEC_TIMEZONE


class EasternFormatter(logging.Formatter):
    """Log formatter that renders timestamps in US/Eastern with offset."""

    def formatTime(self, record: logging.LogRecord, datefmt: str = None) -> str:
        utc_dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        et_dt = utc_dt.astimezone(FEC_TIMEZONE)
        if datefmt:
            return et_dt.strftime(datefmt)
        return et_dt.isoformat()


def configure_logging() -> None:
    """Configure the root logger with Eastern-time formatted output.

    Should be called once at application startup. Subsequent calls are
    no-ops because basicConfig skips configuration if handlers already exist.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        EasternFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler])
