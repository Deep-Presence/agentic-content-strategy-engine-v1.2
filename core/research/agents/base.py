"""
Shared agent infrastructure: backend factories, store, filesystem helpers, debug logging.

Extracted from company_research_agent.py to be reused by all research agents.
"""
import json
import time
from pathlib import Path
from typing import Any, Dict

from deepagents.backends import (
    CompositeBackend,
    FilesystemBackend,
    StateBackend,
    StoreBackend,
)
from langgraph.store.memory import InMemoryStore

from core.config.settings import settings

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # content-strategy-engine/

# region debug logging (do not log secrets)
_DEBUG_LOG_PATH = str(_PROJECT_ROOT / "artifacts" / "_logs" / "debug.log")


def _dbg(*, run_id: str, hypothesis_id: str, location: str, message: str, data: Dict[str, Any]) -> None:
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        # Never break runtime for logging failures.
        pass


def _env_flag(name: str) -> Dict[str, Any]:
    v = getattr(settings, name.lower(), None)
    return {
        "present": v is not None,
        "non_empty": bool(v),
        "length": (len(v) if v is not None else None),
    }


def _dotenv_presence() -> Dict[str, bool]:
    rr = _PROJECT_ROOT
    pr = _PROJECT_ROOT.parent
    candidates = {
        "project_root_.env": (rr / ".env"),
        "project_root_.env.local": (rr / ".env.local"),
        "project_root_.env.test.local": (rr / ".env.test.local"),
        "parent_.env": (pr / ".env"),
        "parent_.env.local": (pr / ".env.local"),
        "parent_.env.test.local": (pr / ".env.test.local"),
    }
    return {k: p.exists() for k, p in candidates.items()}

# endregion


_backend = None
_store = None


def get_store() -> InMemoryStore:
    global _store
    if _store is None:
        # NOTE: In-memory only (durable within this process). Swap later to a durable BaseStore.
        _store = InMemoryStore()
    return _store


def backend_factory(rt: Any) -> CompositeBackend:
    """Composite backend:
    - default: StateBackend (scratchpad, per-thread)
    - /artifacts/: FilesystemBackend (canonical markdown artifacts on disk)
    - /memories/: StoreBackend (durable across threads if store is durable)
    """
    workspace_root = _PROJECT_ROOT
    artifacts_root = workspace_root / "artifacts"
    for sub in ["company_context", "personas", "style_guides", "_logs"]:
        (artifacts_root / sub).mkdir(parents=True, exist_ok=True)

    fs_backend = FilesystemBackend(root_dir=str(artifacts_root), virtual_mode=True)

    return CompositeBackend(
        default=StateBackend(rt),
        routes={
            "/artifacts/": fs_backend,
            "/memories/": StoreBackend(rt),
        },
    )


def get_filesystem_backend() -> FilesystemBackend:
    """Helper for non-agent code paths (e.g. LangGraph node) to write to /artifacts/* on disk."""
    workspace_root = _PROJECT_ROOT
    artifacts_root = workspace_root / "artifacts"
    for sub in ["company_context", "personas", "style_guides", "_logs"]:
        (artifacts_root / sub).mkdir(parents=True, exist_ok=True)
    return FilesystemBackend(root_dir=str(workspace_root), virtual_mode=True)


def get_backend():
    global _backend
    if _backend is None:
        _backend = backend_factory
    return _backend
