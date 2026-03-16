"""Sensitive data masking — structlog processor that redacts secrets from log output.

Insert as the LAST processor in the ``shared_processors`` chain (after
``format_exc_info``, before the renderer) so that every log record is
scrubbed before it reaches JSON/console output.

Redacts:
  - API keys (OpenAI, Anthropic, Google, Perplexity, LangSmith)
  - Bearer / JWT tokens
  - Email addresses (in structured fields only, NOT in event strings)
  - Password hashes (PBKDF2, bcrypt, argon2)
  - Any field whose name contains sensitive keywords
  - Control characters in user-supplied values (log-injection hardening)
"""
from __future__ import annotations

import re
from typing import Any

__all__ = ["SensitiveDataMasker"]

REDACTED = "***REDACTED***"
_MAX_DEPTH = 8

# ---------------------------------------------------------------------------
# Sensitive field-name keywords (case-insensitive substring match)
# ---------------------------------------------------------------------------

_SENSITIVE_FIELD_KEYWORDS: frozenset[str] = frozenset({
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "invite_code",
    "password_hash",
    "access_token",
    "stream_token",
    "refresh_token",
    "private_key",
    "client_secret",
    "webhook_url",
})

# ---------------------------------------------------------------------------
# Value-pattern regexes (compiled once at import time)
# ---------------------------------------------------------------------------

# API keys — order matters: more specific patterns first
_API_KEY_PATTERN = re.compile(
    r"(?:"
    r"sk-ant-[A-Za-z0-9_-]{20,}"       # Anthropic
    r"|sk-[A-Za-z0-9_-]{20,}"           # OpenAI
    r"|(?:pk|key)-[A-Za-z0-9_-]{20,}"   # Generic prefixed
    r"|AIzaSy[A-Za-z0-9_-]{33}"         # Google
    r"|(?:ls|lsv2)__[A-Za-z0-9_-]{20,}" # LangSmith
    r"|pplx-[A-Za-z0-9]{20,}"           # Perplexity
    r")"
)

_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_.=-]+", re.IGNORECASE)

_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_=-]+")

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Password hashes
_PBKDF2_HASH_PATTERN = re.compile(r"[0-9a-f]{32}:[0-9a-f]{64}")
_BCRYPT_PATTERN = re.compile(r"\$2[aby]\$\d{2}\$[A-Za-z0-9./]{53}")
_ARGON2_PATTERN = re.compile(r"\$argon2(?:id|i|d)\$[^\s]+")

# Control characters for log-injection hardening
_CONTROL_CHAR_PATTERN = re.compile(r"[\n\r\t]")

# Keys that should NOT be redacted even if they contain a sensitive keyword
# (e.g., "token" appears in "stream_token" but _record is internal)
_SKIP_KEYS: frozenset[str] = frozenset({"_record"})


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------


class SensitiveDataMasker:
    """structlog processor that recursively redacts sensitive data from event dicts.

    Usage::

        shared_processors.append(SensitiveDataMasker())
    """

    def __call__(
        self,
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        return self._mask_dict(event_dict, depth=0, is_root=True)

    # -- Internal helpers ---------------------------------------------------

    def _mask_dict(
        self, d: dict[str, Any], depth: int, *, is_root: bool = False,
    ) -> dict[str, Any]:
        if depth > _MAX_DEPTH:
            return d
        for key in list(d.keys()):
            if key in _SKIP_KEYS:
                continue
            val = d[key]
            if self._is_sensitive_key(key):
                d[key] = REDACTED
            elif isinstance(val, str):
                d[key] = self._mask_string(val, is_event=(is_root and key == "event"))
            elif isinstance(val, dict):
                d[key] = self._mask_dict(val, depth + 1)
            elif isinstance(val, (list, tuple)):
                d[key] = self._mask_sequence(val, depth + 1)
        return d

    def _mask_sequence(self, seq: list | tuple, depth: int) -> list | tuple:
        if depth > _MAX_DEPTH:
            return seq
        result = []
        for item in seq:
            if isinstance(item, dict):
                result.append(self._mask_dict(item, depth + 1))
            elif isinstance(item, str):
                result.append(self._mask_string(item, is_event=False))
            elif isinstance(item, (list, tuple)):
                result.append(self._mask_sequence(item, depth + 1))
            else:
                result.append(item)
        return type(seq)(result) if isinstance(seq, tuple) else result

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        key_lower = key.lower()
        return any(kw in key_lower for kw in _SENSITIVE_FIELD_KEYWORDS)

    @staticmethod
    def _mask_string(value: str, *, is_event: bool) -> str:
        """Mask sensitive patterns in a string value.

        Args:
            value: The string to scan.
            is_event: True if this is the ``event`` key (the log message).
                For event strings, only API key and bearer patterns are
                scanned (NOT emails — per requirements).
        """
        # API keys and bearer tokens — always scan
        value = _API_KEY_PATTERN.sub(REDACTED, value)
        value = _BEARER_PATTERN.sub(REDACTED, value)
        value = _JWT_PATTERN.sub(REDACTED, value)

        if not is_event:
            # Structured fields: also scan emails and password hashes
            value = _EMAIL_PATTERN.sub(REDACTED, value)
            value = _PBKDF2_HASH_PATTERN.sub(REDACTED, value)
            value = _BCRYPT_PATTERN.sub(REDACTED, value)
            value = _ARGON2_PATTERN.sub(REDACTED, value)

        # Log-injection hardening: strip control characters
        value = _CONTROL_CHAR_PATTERN.sub(" ", value)

        return value
