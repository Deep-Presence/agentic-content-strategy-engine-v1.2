import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.config.settings import settings
from core.storage.supabase_client import get_supabase_client


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def mirror_company_context_markdown(
    *,
    company_id: str,
    company_name: str,
    domain: Optional[str],
    artifact_path: str,
    markdown: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Filesystem-first: mirror current artifact to public.artifacts + append immutable snapshot to public.artifact_versions.

    - public.artifacts.content stores metadata + current body (md) for frontend display/editing.
    - public.artifact_versions stores version history snapshots.
    """
    sb = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    sha = _sha256_text(markdown)

    # 1) Find existing artifact row for this company/type
    existing = (
        sb.table("artifacts")
        .select("id,version,title")
        .eq("company_id", company_id)
        .eq("type", "company_context")
        .limit(1)
        .execute()
    )
    existing_row = (existing.data or [None])[0]

    title = f"{company_name} — Company Context"
    content = {
        "format": "md",
        "path": artifact_path,
        "body": markdown,
        "sha256": sha,
        "domain": domain,
        "mirrored_at": now,
    }

    if existing_row:
        artifact_id = existing_row["id"]
        next_version = int(existing_row.get("version") or 1) + 1
        update_payload: Dict[str, Any] = {
            "title": title,
            "version": next_version,
            "content": content,
            "source": "agent",
        }
        if agent_id:
            update_payload["last_regenerated_by"] = agent_id
        sb.table("artifacts").update(update_payload).eq("id", artifact_id).execute()
    else:
        next_version = 1
        insert_payload: Dict[str, Any] = {
            "company_id": company_id,
            "type": "company_context",
            "title": title,
            "status": "active",
            "version": next_version,
            "content": content,
            "source": "agent",
        }
        if agent_id:
            insert_payload["last_regenerated_by"] = agent_id
        inserted = sb.table("artifacts").insert(insert_payload).execute()
        artifact_id = inserted.data[0]["id"]

    # 2) Append immutable snapshot row
    version_payload: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "version_no": next_version,
        "body_md": markdown,
        "metadata": {
            "path": artifact_path,
            "sha256": sha,
            "domain": domain,
            "mirrored_at": now,
        },
    }
    if agent_id:
        version_payload["created_by_agent_id"] = agent_id

    sb.table("artifact_versions").insert(version_payload).execute()

    return {"artifact_id": artifact_id, "version_no": next_version, "sha256": sha}


def mirror_company_context_if_configured(
    *,
    company_id: Optional[str],
    company_name: str,
    domain: Optional[str],
    artifact_path: str,
    markdown: str,
) -> Optional[Dict[str, Any]]:
    """
    Convenience wrapper: if Supabase env vars aren't set or company_id missing, do nothing.
    """
    if not company_id:
        return None
    if not settings.effective_supabase_url or not settings.effective_supabase_key:
        return None

    agent_id = settings.supabase_agent_id
    return mirror_company_context_markdown(
        company_id=company_id,
        company_name=company_name,
        domain=domain,
        artifact_path=artifact_path,
        markdown=markdown,
        agent_id=agent_id,
    )


def mirror_persona_markdown(
    *,
    company_id: str,
    company_name: str,
    domain: Optional[str],
    artifact_path: str,
    markdown: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mirror a persona artifact (multiple per company) into public.artifacts + public.artifact_versions.
    We locate the row by (company_id, type='persona', content contains path).
    """
    sb = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    sha = _sha256_text(markdown)

    title = f"{company_name} — Persona"
    content = {
        "format": "md",
        "path": artifact_path,
        "body": markdown,
        "sha256": sha,
        "domain": domain,
        "mirrored_at": now,
    }

    existing = (
        sb.table("artifacts")
        .select("id,version,title,content")
        .eq("company_id", company_id)
        .eq("type", "persona")
        .contains("content", {"path": artifact_path})
        .limit(1)
        .execute()
    )
    existing_row = (existing.data or [None])[0]

    if existing_row:
        artifact_id = existing_row["id"]
        next_version = int(existing_row.get("version") or 1) + 1
        update_payload: Dict[str, Any] = {
            "title": title,
            "version": next_version,
            "content": content,
            "source": "agent",
        }
        if agent_id:
            update_payload["last_regenerated_by"] = agent_id
        sb.table("artifacts").update(update_payload).eq("id", artifact_id).execute()
    else:
        next_version = 1
        insert_payload: Dict[str, Any] = {
            "company_id": company_id,
            "type": "persona",
            "title": title,
            "status": "active",
            "version": next_version,
            "content": content,
            "source": "agent",
        }
        if agent_id:
            insert_payload["last_regenerated_by"] = agent_id
        inserted = sb.table("artifacts").insert(insert_payload).execute()
        artifact_id = inserted.data[0]["id"]

    version_payload: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "version_no": next_version,
        "body_md": markdown,
        "metadata": {
            "path": artifact_path,
            "sha256": sha,
            "domain": domain,
            "mirrored_at": now,
        },
    }
    if agent_id:
        version_payload["created_by_agent_id"] = agent_id
    sb.table("artifact_versions").insert(version_payload).execute()

    return {"artifact_id": artifact_id, "version_no": next_version, "sha256": sha}


def mirror_persona_if_configured(
    *,
    company_id: Optional[str],
    company_name: str,
    domain: Optional[str],
    artifact_path: str,
    markdown: str,
) -> Optional[Dict[str, Any]]:
    if not company_id:
        return None
    if not settings.effective_supabase_url or not settings.effective_supabase_key:
        return None
    agent_id = settings.supabase_agent_id
    return mirror_persona_markdown(
        company_id=company_id,
        company_name=company_name,
        domain=domain,
        artifact_path=artifact_path,
        markdown=markdown,
        agent_id=agent_id,
    )


def mirror_styleguide_markdown(
    *,
    company_id: str,
    company_name: str,
    domain: Optional[str],
    artifact_path: str,
    markdown: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mirror a style-guide artifact into public.artifacts + public.artifact_versions.
    """
    sb = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    sha = _sha256_text(markdown)

    title = f"{company_name} — Writing Style Guide"
    content = {
        "format": "md",
        "path": artifact_path,
        "body": markdown,
        "sha256": sha,
        "domain": domain,
        "mirrored_at": now,
    }

    existing = (
        sb.table("artifacts")
        .select("id,version,title,content")
        .eq("company_id", company_id)
        .eq("type", "guidelines")
        .contains("content", {"path": artifact_path})
        .limit(1)
        .execute()
    )
    existing_row = (existing.data or [None])[0]

    if existing_row:
        artifact_id = existing_row["id"]
        next_version = int(existing_row.get("version") or 1) + 1
        update_payload: Dict[str, Any] = {
            "title": title,
            "version": next_version,
            "content": content,
            "source": "agent",
        }
        if agent_id:
            update_payload["last_regenerated_by"] = agent_id
        sb.table("artifacts").update(update_payload).eq("id", artifact_id).execute()
    else:
        next_version = 1
        insert_payload: Dict[str, Any] = {
            "company_id": company_id,
            "type": "guidelines",
            "title": title,
            "status": "active",
            "version": next_version,
            "content": content,
            "source": "agent",
        }
        if agent_id:
            insert_payload["last_regenerated_by"] = agent_id
        inserted = sb.table("artifacts").insert(insert_payload).execute()
        artifact_id = inserted.data[0]["id"]

    version_payload: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "version_no": next_version,
        "body_md": markdown,
        "metadata": {
            "path": artifact_path,
            "sha256": sha,
            "domain": domain,
            "mirrored_at": now,
        },
    }
    if agent_id:
        version_payload["created_by_agent_id"] = agent_id
    sb.table("artifact_versions").insert(version_payload).execute()

    return {"artifact_id": artifact_id, "version_no": next_version, "sha256": sha}


def mirror_styleguide_if_configured(
    *,
    company_id: Optional[str],
    company_name: str,
    domain: Optional[str],
    artifact_path: str,
    markdown: str,
) -> Optional[Dict[str, Any]]:
    if not company_id:
        return None
    if not settings.effective_supabase_url or not settings.effective_supabase_key:
        return None
    agent_id = settings.supabase_agent_id
    return mirror_styleguide_markdown(
        company_id=company_id,
        company_name=company_name,
        domain=domain,
        artifact_path=artifact_path,
        markdown=markdown,
        agent_id=agent_id,
    )
