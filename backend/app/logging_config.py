"""Logging with secret redaction.

A single filter scrubs every configured secret from every record. This is the
backstop that keeps an API key out of logs even if a provider library decides
to include the request URL in an exception message.
"""

from __future__ import annotations

import logging
import re

_REDACTED = "***REDACTED***"


class SecretRedactionFilter(logging.Filter):
    """Replaces configured secret values with a placeholder."""

    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        # Longest first, so a secret that contains another is fully masked.
        self._secrets = sorted({s for s in secrets if s}, key=len, reverse=True)

    def _scrub(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, _REDACTED)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            if isinstance(record.msg, str):
                record.msg = self._scrub(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: self._scrub(v) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        self._scrub(a) if isinstance(a, str) else a
                        for a in record.args
                    )
        return True


def configure_logging(level: str = "INFO", secrets: list[str] | None = None) -> None:
    """Configure root logging once, with redaction installed."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in root.handlers:
        handler.filters = [
            f for f in handler.filters if not isinstance(f, SecretRedactionFilter)
        ]
    if not root.handlers:
        root.addHandler(logging.StreamHandler())

    redaction = SecretRedactionFilter(secrets or [])
    for handler in root.handlers:
        handler.addFilter(redaction)


def redact(text: str, secrets: list[str]) -> str:
    """Scrub secrets from an arbitrary string (used before error reporting)."""
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        text = text.replace(secret, _REDACTED)
    return text


# Common shapes that should never be echoed even if not in the secret list.
_TOKEN_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b"),
]


def redact_tokens(text: str) -> str:
    """Redact anything that looks like a credential, regardless of config."""
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text
