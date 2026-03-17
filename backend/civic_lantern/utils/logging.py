import logging
from datetime import datetime, timezone


class UTCFormatter(logging.Formatter):
    """Log formatter that renders timestamps in UTC."""

    def formatTime(self, record: logging.LogRecord, datefmt: str = None) -> str:
        utc_dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            return utc_dt.strftime(datefmt)
        return utc_dt.isoformat()


def configure_logging() -> None:
    """Configure the root logger with UTC-formatted output.

    Should be called once at application startup. Subsequent calls are
    no-ops because basicConfig skips configuration if handlers already exist.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        UTCFormatter(
            fmt="%(asctime)s [%(levelname)s] %(process)d %(name)s %(filename)s:%(lineno)d: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
