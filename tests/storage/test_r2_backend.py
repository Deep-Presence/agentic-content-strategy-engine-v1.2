"""Tests for R2StorageBackend — Cloudflare R2 (S3-compatible) artifact storage.

Uses unittest.mock to stub the boto3 S3 client. No real S3/R2 calls are made.
"""
from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from core.storage.backends.r2 import R2StorageBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def backend(mock_client: MagicMock) -> R2StorageBackend:
    return R2StorageBackend(
        bucket_name="test-bucket",
        endpoint_url="https://fake.r2.dev",
        access_key_id="fake-key",
        secret_access_key="fake-secret",
        _client=mock_client,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_get_object_response(body: bytes) -> dict:
    """Build a minimal get_object response dict."""
    return {"Body": BytesIO(body)}


def _make_client_error(code: str = "NoSuchKey") -> Exception:
    """Build a botocore ClientError with the given error code."""
    from botocore.exceptions import ClientError

    return ClientError(
        error_response={"Error": {"Code": code, "Message": "Not found"}},
        operation_name="GetObject",
    )


def _setup_paginator(mock_client: MagicMock, pages: list[dict]) -> None:
    """Configure mock_client.get_paginator to return pages."""
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = pages
    mock_client.get_paginator.return_value = mock_paginator


# ---------------------------------------------------------------------------
# read / write (text)
# ---------------------------------------------------------------------------


class TestR2ReadWrite:
    def test_read_returns_decoded_text(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.get_object.return_value = _make_get_object_response(
            "# Hello".encode("utf-8")
        )
        result = backend.read("knowledge_base/test/v1.md")
        assert result == "# Hello"
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="knowledge_base/test/v1.md"
        )

    def test_read_nonexistent_returns_none(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        assert backend.read("missing.md") is None

    def test_read_other_error_propagates(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.get_object.side_effect = _make_client_error("AccessDenied")
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError):
            backend.read("forbidden.md")

    def test_write_returns_path(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        result = backend.write("kb/test/v1.md", "# Content")
        assert result == "kb/test/v1.md"
        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="kb/test/v1.md",
            Body="# Content".encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )

    def test_write_utf8(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        content = "Unicode: éàüñ 🚀 你好"
        backend.write("utf8.md", content)
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["Body"] == content.encode("utf-8")


# ---------------------------------------------------------------------------
# read_bytes / write_bytes (binary)
# ---------------------------------------------------------------------------


class TestR2BinaryReadWrite:
    def test_read_bytes_returns_raw(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        raw = b"\x00\x01\x02\xff\xfe"
        mock_client.get_object.return_value = _make_get_object_response(raw)
        assert backend.read_bytes("data.bin") == raw

    def test_read_bytes_nonexistent_returns_none(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        assert backend.read_bytes("missing.bin") is None

    def test_read_bytes_access_denied_propagates(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.get_object.side_effect = _make_client_error("AccessDenied")
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError):
            backend.read_bytes("forbidden.bin")

    def test_write_bytes_returns_path(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        data = b"\x89PNG\r\n"
        result = backend.write_bytes("image.png", data)
        assert result == "image.png"
        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="image.png",
            Body=data,
            ContentType="application/octet-stream",
        )


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


class TestR2Exists:
    def test_exists_true_for_object(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.head_object.return_value = {}
        assert backend.exists("file.md") is True
        mock_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key="file.md"
        )

    def test_exists_false_no_object_no_prefix(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.head_object.side_effect = _make_client_error("404")
        mock_client.list_objects_v2.return_value = {"KeyCount": 0}
        assert backend.exists("missing.md") is False

    def test_exists_true_for_prefix_directory(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        """exists() returns True for a prefix with children (directory-like)."""
        mock_client.head_object.side_effect = _make_client_error("404")
        mock_client.list_objects_v2.return_value = {"KeyCount": 1}
        assert backend.exists("knowledge_base/test") is True
        mock_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket",
            Prefix="knowledge_base/test/",
            MaxKeys=1,
        )

    def test_exists_access_denied_propagates(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        """Non-404 errors must propagate, not be swallowed as False."""
        mock_client.head_object.side_effect = _make_client_error("AccessDenied")
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError):
            backend.exists("forbidden.md")


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestR2Delete:
    def test_delete_existing_returns_true(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.head_object.return_value = {}
        assert backend.delete("file.md") is True
        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="file.md"
        )

    def test_delete_nonexistent_returns_false(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        mock_client.head_object.side_effect = _make_client_error("404")
        assert backend.delete("missing.md") is False
        mock_client.delete_object.assert_not_called()

    def test_delete_access_denied_propagates(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        """Non-404 errors in delete must propagate."""
        mock_client.head_object.side_effect = _make_client_error("AccessDenied")
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError):
            backend.delete("forbidden.md")


# ---------------------------------------------------------------------------
# list_dir (with paginator)
# ---------------------------------------------------------------------------


class TestR2ListDir:
    def test_list_dir_combines_files_and_prefixes(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        _setup_paginator(mock_client, [{
            "Contents": [
                {"Key": "kb/ramp/v1.md"},
                {"Key": "kb/ramp/v2.md"},
            ],
            "CommonPrefixes": [
                {"Prefix": "kb/ramp/drafts/"},
            ],
        }])
        result = backend.list_dir("kb/ramp")
        assert "kb/ramp/drafts" in result
        assert "kb/ramp/v1.md" in result
        assert "kb/ramp/v2.md" in result
        assert result == sorted(result)

    def test_list_dir_empty(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        _setup_paginator(mock_client, [{}])
        assert backend.list_dir("empty/") == []

    def test_list_dir_normalizes_prefix(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        """Prefix without trailing / should be normalized."""
        _setup_paginator(mock_client, [{}])
        backend.list_dir("kb/ramp")
        paginator = mock_client.get_paginator.return_value
        call_kwargs = paginator.paginate.call_args[1]
        assert call_kwargs["Prefix"] == "kb/ramp/"

    def test_list_dir_excludes_prefix_key_itself(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        """If Contents includes the prefix itself (directory marker), exclude it."""
        _setup_paginator(mock_client, [{
            "Contents": [
                {"Key": "kb/ramp/"},  # directory marker
                {"Key": "kb/ramp/v1.md"},
            ],
        }])
        result = backend.list_dir("kb/ramp")
        assert "kb/ramp/" not in result
        assert "kb/ramp/v1.md" in result

    def test_list_dir_pagination(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        """Verify pagination handles multiple pages correctly."""
        page1 = {
            "Contents": [{"Key": f"dir/file_{i:04d}.md"} for i in range(1000)],
        }
        page2 = {
            "Contents": [{"Key": f"dir/file_{i:04d}.md"} for i in range(1000, 1500)],
            "CommonPrefixes": [{"Prefix": "dir/subdir/"}],
        }
        _setup_paginator(mock_client, [page1, page2])
        result = backend.list_dir("dir")
        # 1500 files + 1 subdir = 1501 entries
        assert len(result) == 1501
        assert result == sorted(result)
        assert "dir/subdir" in result


# ---------------------------------------------------------------------------
# mkdir
# ---------------------------------------------------------------------------


class TestR2Mkdir:
    def test_mkdir_is_noop(
        self, backend: R2StorageBackend, mock_client: MagicMock
    ) -> None:
        backend.mkdir("any/path")
        mock_client.put_object.assert_not_called()
        mock_client.head_object.assert_not_called()


# ---------------------------------------------------------------------------
# Path traversal safety
# ---------------------------------------------------------------------------


class TestR2PathTraversalSafety:
    def test_dotdot_escape_read(self, backend: R2StorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage scope"):
            backend.read("../../../etc/passwd")

    def test_dotdot_escape_write(self, backend: R2StorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage scope"):
            backend.write("../outside.md", "bad")

    def test_dotdot_escape_read_bytes(self, backend: R2StorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage scope"):
            backend.read_bytes("../../secret.bin")

    def test_dotdot_escape_write_bytes(self, backend: R2StorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage scope"):
            backend.write_bytes("../outside.bin", b"bad")

    def test_dotdot_escape_exists(self, backend: R2StorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage scope"):
            backend.exists("../../etc/passwd")

    def test_dotdot_escape_delete(self, backend: R2StorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage scope"):
            backend.delete("../outside.md")

    def test_absolute_path_rejected(self, backend: R2StorageBackend) -> None:
        with pytest.raises(ValueError, match="Path must be relative"):
            backend.read("/etc/passwd")

    def test_dotdot_in_middle(self, backend: R2StorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage scope"):
            backend.read("a/b/../../../../etc/passwd")


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestR2Constructor:
    def test_creates_boto3_client_when_no_override(self) -> None:
        with patch("core.storage.backends.r2.boto3") as mock_boto3:
            R2StorageBackend(
                bucket_name="my-bucket",
                endpoint_url="https://acct.r2.cloudflarestorage.com",
                access_key_id="key",
                secret_access_key="secret",
            )
            mock_boto3.client.assert_called_once_with(
                "s3",
                endpoint_url="https://acct.r2.cloudflarestorage.com",
                aws_access_key_id="key",
                aws_secret_access_key="secret",
                region_name="auto",
            )

    def test_uses_injected_client(self, mock_client: MagicMock) -> None:
        backend = R2StorageBackend(
            bucket_name="b",
            endpoint_url="https://x",
            access_key_id="k",
            secret_access_key="s",
            _client=mock_client,
        )
        assert backend._client is mock_client
