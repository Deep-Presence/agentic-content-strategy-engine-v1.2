"""Tests for LocalStorageBackend — filesystem-backed artifact storage."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.storage.backends.local import LocalStorageBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def backend(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(tmp_path)


# ---------------------------------------------------------------------------
# read / write roundtrip
# ---------------------------------------------------------------------------


class TestWriteAndRead:
    def test_roundtrip(self, backend: LocalStorageBackend) -> None:
        backend.write("hello.md", "# Hello")
        assert backend.read("hello.md") == "# Hello"

    def test_nested_path_creates_parents(self, backend: LocalStorageBackend) -> None:
        backend.write("a/b/c/deep.md", "deep content")
        assert backend.read("a/b/c/deep.md") == "deep content"

    def test_overwrite_existing(self, backend: LocalStorageBackend) -> None:
        backend.write("doc.md", "v1")
        backend.write("doc.md", "v2")
        assert backend.read("doc.md") == "v2"

    def test_utf8_roundtrip(self, backend: LocalStorageBackend) -> None:
        content = "Unicode: \u00e9\u00e0\u00fc\u00f1 \U0001f680 \u4f60\u597d"
        backend.write("utf8.md", content)
        assert backend.read("utf8.md") == content

    def test_write_returns_logical_path(self, backend: LocalStorageBackend) -> None:
        result = backend.write("foo/bar.md", "content")
        assert result == "foo/bar.md"


# ---------------------------------------------------------------------------
# read edge cases
# ---------------------------------------------------------------------------


class TestRead:
    def test_nonexistent_returns_none(self, backend: LocalStorageBackend) -> None:
        assert backend.read("does-not-exist.md") is None

    def test_directory_returns_none(self, backend: LocalStorageBackend) -> None:
        backend.mkdir("somedir")
        assert backend.read("somedir") is None

    def test_empty_file(self, backend: LocalStorageBackend) -> None:
        backend.write("empty.md", "")
        assert backend.read("empty.md") == ""


# ---------------------------------------------------------------------------
# Atomicity
# ---------------------------------------------------------------------------


class TestAtomicity:
    def test_no_temp_files_left_after_write(
        self, backend: LocalStorageBackend
    ) -> None:
        backend.write("target.md", "content")
        parent = backend.root
        tmp_files = [f for f in parent.iterdir() if f.suffix == ".tmp"]
        assert tmp_files == []

    def test_no_temp_files_on_success_in_subdir(
        self, backend: LocalStorageBackend
    ) -> None:
        backend.write("sub/dir/file.md", "content")
        subdir = backend.root / "sub" / "dir"
        tmp_files = [f for f in subdir.iterdir() if f.suffix == ".tmp"]
        assert tmp_files == []


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


class TestExists:
    def test_exists_after_write(self, backend: LocalStorageBackend) -> None:
        backend.write("file.md", "data")
        assert backend.exists("file.md") is True

    def test_not_exists_before_write(self, backend: LocalStorageBackend) -> None:
        assert backend.exists("missing.md") is False

    def test_exists_for_directory(self, backend: LocalStorageBackend) -> None:
        backend.mkdir("mydir")
        assert backend.exists("mydir") is True


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_existing(self, backend: LocalStorageBackend) -> None:
        backend.write("file.md", "content")
        assert backend.delete("file.md") is True
        assert backend.read("file.md") is None

    def test_delete_nonexistent(self, backend: LocalStorageBackend) -> None:
        assert backend.delete("nope.md") is False

    def test_delete_directory_returns_false(
        self, backend: LocalStorageBackend
    ) -> None:
        backend.mkdir("adir")
        assert backend.delete("adir") is False


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------


class TestListDir:
    def test_list_dir_returns_relative_paths(
        self, backend: LocalStorageBackend
    ) -> None:
        backend.write("kb/ramp/v1.md", "a")
        backend.write("kb/ramp/v2.md", "b")
        result = backend.list_dir("kb/ramp")
        # Should contain relative-to-root paths
        assert "kb/ramp/v1.md" in result
        assert "kb/ramp/v2.md" in result

    def test_list_dir_empty_directory(
        self, backend: LocalStorageBackend
    ) -> None:
        backend.mkdir("emptydir")
        assert backend.list_dir("emptydir") == []

    def test_list_dir_nonexistent(self, backend: LocalStorageBackend) -> None:
        assert backend.list_dir("no-such-dir") == []

    def test_list_dir_sorted(self, backend: LocalStorageBackend) -> None:
        backend.write("dir/c.md", "c")
        backend.write("dir/a.md", "a")
        backend.write("dir/b.md", "b")
        result = backend.list_dir("dir")
        names = [Path(p).name for p in result]
        assert names == ["a.md", "b.md", "c.md"]

    def test_list_dir_includes_subdirs(
        self, backend: LocalStorageBackend
    ) -> None:
        backend.write("parent/child/file.md", "content")
        result = backend.list_dir("parent")
        # Should list the 'child' directory entry
        assert any("child" in entry for entry in result)


# ---------------------------------------------------------------------------
# mkdir
# ---------------------------------------------------------------------------


class TestMkdir:
    def test_mkdir_creates_directory(
        self, backend: LocalStorageBackend
    ) -> None:
        backend.mkdir("new/nested/dir")
        assert backend.exists("new/nested/dir") is True

    def test_mkdir_idempotent(self, backend: LocalStorageBackend) -> None:
        backend.mkdir("mydir")
        backend.mkdir("mydir")  # should not raise
        assert backend.exists("mydir") is True


# ---------------------------------------------------------------------------
# Path traversal safety (Codex finding)
# ---------------------------------------------------------------------------


class TestPathTraversalSafety:
    def test_dotdot_escape_read(self, backend: LocalStorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage root"):
            backend.read("../../../etc/passwd")

    def test_dotdot_escape_write(self, backend: LocalStorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage root"):
            backend.write("../outside.md", "bad")

    def test_dotdot_escape_exists(self, backend: LocalStorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage root"):
            backend.exists("../../etc/passwd")

    def test_dotdot_escape_delete(self, backend: LocalStorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage root"):
            backend.delete("../outside.md")

    def test_dotdot_escape_list_dir(
        self, backend: LocalStorageBackend
    ) -> None:
        with pytest.raises(ValueError, match="escapes storage root"):
            backend.list_dir("../../")

    def test_dotdot_escape_mkdir(self, backend: LocalStorageBackend) -> None:
        with pytest.raises(ValueError, match="escapes storage root"):
            backend.mkdir("../escape")

    def test_absolute_path_rejected(
        self, backend: LocalStorageBackend
    ) -> None:
        with pytest.raises(ValueError, match="escapes storage root"):
            backend.read("/etc/passwd")

    def test_dotdot_in_middle_still_escapes(
        self, backend: LocalStorageBackend
    ) -> None:
        with pytest.raises(ValueError, match="escapes storage root"):
            backend.read("a/b/../../../../etc/passwd")

    def test_dotdot_that_stays_inside_is_allowed(
        self, backend: LocalStorageBackend
    ) -> None:
        """a/b/../b/file.md resolves to a/b/file.md — still inside root."""
        backend.write("a/b/file.md", "ok")
        assert backend.read("a/b/../b/file.md") == "ok"
