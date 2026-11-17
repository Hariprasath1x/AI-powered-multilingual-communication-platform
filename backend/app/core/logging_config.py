"""PII and credential redacting logging filter and configuration for MassCommAI."""

import logging
import re
from typing import Any


class PIIRedactingFilter(logging.Filter):
    """
    Log filter that scrubs PII (emails, phone numbers) and credentials (bearer tokens, secrets)
    from log records before output.
    """

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    PHONE_PATTERN = re.compile(r"(?:\+?91[\-\s]?)?[6-9]\d{9}\b")
    BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]+", re.IGNORECASE)
    SECRET_PATTERN = re.compile(
        r"(password|secret|hashed_password|api_key|verify_token)([\"']?\s*[:=]\s*[\"']?)([^\"'\s,]+)",
        re.IGNORECASE,
    )

    def _sanitize(self, text: str) -> str:
        if not isinstance(text, str):
            return text
        text = self.EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
        text = self.PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
        text = self.BEARER_PATTERN.sub("Bearer [REDACTED]", text)
        text = self.SECRET_PATTERN.sub(r"\1\2[REDACTED]", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)

        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self._sanitize(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: self._sanitize(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True


def setup_pii_redacting_logger(logger_name: str = "masscommai") -> logging.Logger:
    """Configures and attaches the PIIRedactingFilter to the target logger and root handlers."""
    target_logger = logging.getLogger(logger_name)
    pii_filter = PIIRedactingFilter()

    # Attach filter to target logger
    target_logger.addFilter(pii_filter)

    # Attach filter to all root handlers to ensure uncaught logs are filtered
    root_logger = logging.getLogger()
    root_logger.addFilter(pii_filter)
    for handler in root_logger.handlers:
        handler.addFilter(pii_filter)

    return target_logger
