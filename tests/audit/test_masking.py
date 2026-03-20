"""Tests for core.audit.masking — SensitiveDataMasker structlog processor."""
from __future__ import annotations

from core.audit.masking import REDACTED, SensitiveDataMasker

masker = SensitiveDataMasker()


def _mask(event_dict: dict) -> dict:
    """Helper: run masker as a structlog processor."""
    return masker(None, "info", event_dict)


class TestSensitiveFieldNameRedaction:
    """Keys containing sensitive keywords → entire value redacted."""

    def test_password_key(self) -> None:
        result = _mask({"event": "test", "password": "hunter2"})
        assert result["password"] == REDACTED

    def test_api_key_key(self) -> None:
        result = _mask({"event": "test", "api_key": "some-value"})
        assert result["api_key"] == REDACTED

    def test_access_token_key(self) -> None:
        result = _mask({"event": "test", "access_token": "abc123"})
        assert result["access_token"] == REDACTED

    def test_authorization_key(self) -> None:
        result = _mask({"event": "test", "Authorization": "Bearer xyz"})
        assert result["Authorization"] == REDACTED

    def test_invite_code_key(self) -> None:
        result = _mask({"event": "test", "invite_code": "abc-def-123"})
        assert result["invite_code"] == REDACTED

    def test_password_hash_key(self) -> None:
        result = _mask({"event": "test", "password_hash": "abcdef1234:5678"})
        assert result["password_hash"] == REDACTED

    def test_webhook_url_key(self) -> None:
        result = _mask({"event": "test", "webhook_url": "https://hooks.slack.com/xxx"})
        assert result["webhook_url"] == REDACTED

    def test_case_insensitive_key_matching(self) -> None:
        result = _mask({"event": "test", "API_KEY": "val", "Secret": "val2"})
        assert result["API_KEY"] == REDACTED
        assert result["Secret"] == REDACTED

    def test_client_secret_key(self) -> None:
        result = _mask({"event": "test", "client_secret": "s3cr3t"})
        assert result["client_secret"] == REDACTED


class TestAPIKeyPatternRedaction:
    """API key patterns in string values → redacted."""

    def test_openai_api_key_redacted(self) -> None:
        val = "Using key sk-proj-abcdefghijklmnopqrstuvwxyz1234567890abcdefgh"
        result = _mask({"event": val})
        assert "sk-proj-" not in result["event"]
        assert REDACTED in result["event"]

    def test_anthropic_api_key_redacted(self) -> None:
        val = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"
        result = _mask({"event": "test", "info": val})
        assert "sk-ant-" not in result["info"]

    def test_google_api_key_redacted(self) -> None:
        val = "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456"
        result = _mask({"event": "test", "key_val": val})
        assert "AIzaSy" not in result["key_val"]

    def test_langsmith_key_redacted(self) -> None:
        val = "lsv2__abcdefghijklmnopqrstuvwxyz"
        result = _mask({"event": "test", "ls_key": val})
        assert "lsv2__" not in result["ls_key"]

    def test_perplexity_key_redacted(self) -> None:
        val = "pplx-abcdefghijklmnopqrstuvwxyz"
        result = _mask({"event": "test", "pplx": val})
        assert "pplx-" not in result["pplx"]


class TestBearerTokenRedaction:
    """Bearer tokens and JWTs → redacted."""

    def test_bearer_token_redacted(self) -> None:
        val = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = _mask({"event": "test", "header": val})
        assert "Bearer" not in result["header"] or REDACTED in result["header"]

    def test_jwt_redacted(self) -> None:
        val = "eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiMTIzIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = _mask({"event": "test", "tok": val})
        assert "eyJ" not in result["tok"]


class TestEmailRedaction:
    """Email addresses in structured fields → redacted (not in event string)."""

    def test_email_redacted_in_structured_field(self) -> None:
        result = _mask({"event": "test", "user_email": "alice@example.com"})
        assert "alice@example.com" not in result["user_email"]
        assert REDACTED in result["user_email"]

    def test_email_not_redacted_in_event_string(self) -> None:
        result = _mask({"event": "User alice@example.com logged in"})
        assert "alice@example.com" in result["event"]


class TestPasswordHashRedaction:
    """Password hashes → redacted."""

    def test_pbkdf2_hash_redacted(self) -> None:
        h = "a" * 32 + ":" + "b" * 64
        result = _mask({"event": "test", "hash": h})
        assert h not in result["hash"]

    def test_bcrypt_hash_redacted(self) -> None:
        h = "$2b$12$" + "A" * 53
        result = _mask({"event": "test", "pw": h})
        assert "$2b$" not in result["pw"]


class TestNestedStructures:
    """Nested dicts and lists → recursively redacted."""

    def test_nested_dict_redacted(self) -> None:
        result = _mask({
            "event": "test",
            "config": {"api_key": "sk-abcdefghijklmnopqrstuvwxyz1234567890"},
        })
        assert result["config"]["api_key"] == REDACTED

    def test_list_of_dicts_redacted(self) -> None:
        result = _mask({
            "event": "test",
            "users": [{"password": "secret123"}],
        })
        assert result["users"][0]["password"] == REDACTED

    def test_deeply_nested_beyond_max_depth(self) -> None:
        """Nesting beyond max depth doesn't crash (graceful degradation)."""
        d: dict = {"event": "test"}
        current = d
        for i in range(12):
            current[f"level_{i}"] = {}
            current = current[f"level_{i}"]
        current["password"] = "secret"
        # Should not raise
        result = _mask(d)
        assert isinstance(result, dict)


class TestNonSensitiveDataUnchanged:
    """Non-sensitive data passes through unchanged."""

    def test_preserves_non_sensitive_keys(self) -> None:
        result = _mask({
            "event": "Pipeline completed",
            "company_slug": "ramp",
            "status_code": 200,
            "duration_ms": 1234,
            "pipeline": "gap_analysis",
        })
        assert result["company_slug"] == "ramp"
        assert result["status_code"] == 200
        assert result["duration_ms"] == 1234
        assert result["pipeline"] == "gap_analysis"

    def test_handles_none_values(self) -> None:
        result = _mask({"event": "test", "user_id": None})
        assert result["user_id"] is None

    def test_handles_non_string_values(self) -> None:
        result = _mask({"event": "test", "count": 42, "active": True})
        assert result["count"] == 42
        assert result["active"] is True


class TestLogInjectionHardening:
    """Control characters stripped from string values."""

    def test_newline_stripped(self) -> None:
        result = _mask({"event": "test\ninjected_line"})
        assert "\n" not in result["event"]

    def test_carriage_return_stripped(self) -> None:
        result = _mask({"event": "test\rinjected"})
        assert "\r" not in result["event"]

    def test_tab_stripped(self) -> None:
        result = _mask({"event": "test\tinjected"})
        assert "\t" not in result["event"]


class TestAPIKeyInEventString:
    """API keys in event strings are redacted (unlike emails)."""

    def test_api_key_in_event_string_redacted(self) -> None:
        val = "Using key sk-proj-abcdefghijklmnopqrstuvwxyz1234567890abcdefgh for API call"
        result = _mask({"event": val})
        assert "sk-proj-" not in result["event"]
        assert REDACTED in result["event"]

    def test_bearer_in_event_string_redacted(self) -> None:
        val = "Authorization: Bearer abc123def456"
        result = _mask({"event": val})
        assert "abc123def456" not in result["event"]


class TestSkipInternalKeys:
    """Internal structlog keys like _record are not touched."""

    def test_record_key_skipped(self) -> None:
        record = {"password": "secret123"}
        result = _mask({"event": "test", "_record": record})
        assert result["_record"]["password"] == "secret123"
