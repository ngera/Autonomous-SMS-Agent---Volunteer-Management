import logging
import re


class PIIMaskingFilter(logging.Filter):
    """Masks phone numbers in log messages to protect PII."""

    PHONE_PATTERN = re.compile(r"(\+\d{1,3})\d{4,}(\d{3})")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.PHONE_PATTERN.sub(r"\1****\2", record.msg)
        return True


def setup_logging() -> None:
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    handler.addFilter(PIIMaskingFilter())
    logger.addHandler(handler)

    # Quiet down noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"app.{name}")
