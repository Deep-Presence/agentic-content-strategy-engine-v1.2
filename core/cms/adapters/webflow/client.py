"""Async HTTP client for Webflow Data API v2."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from core.cms.exceptions import (
    CMSAPIError,
    CMSAuthError,
    CMSConnectionError,
    CMSNotFoundError,
    CMSRateLimitError,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.webflow.com/v2"
_MAX_PAGINATION_PAGES = 50
_PAGE_SIZE = 100


def parse_dt(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        normalized = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def normalize_site_host(site_url: str) -> str:
    parsed = urlparse(site_url if "://" in site_url else f"https://{site_url}")
    return (parsed.netloc or parsed.path).lower().rstrip("/")


class WebflowClient:
    """Thin wrapper around httpx with Webflow error mapping."""

    def __init__(
        self,
        access_token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._access_token = access_token
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {
            "base_url": API_BASE,
            "headers": {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "DeepPresence/1.0",
            },
            "timeout": self._timeout,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        async with self._client() as client:
            try:
                resp = await client.request(method, path, params=params, json=json_body)
            except httpx.ConnectError as exc:
                raise CMSConnectionError(f"Cannot reach Webflow API: {exc}") from exc
            except httpx.TimeoutException as exc:
                raise CMSConnectionError(f"Webflow API timeout: {exc}") from exc

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "60")
                raise CMSRateLimitError(
                    f"Webflow rate limit exceeded; retry after {retry_after}s"
                )
            if resp.status_code in (401, 403):
                raise CMSAuthError("Invalid or unauthorized Webflow credentials")
            if resp.status_code == 404:
                raise CMSNotFoundError(f"Webflow resource not found: {path}")
            if resp.status_code >= 400:
                raise CMSAPIError(
                    f"Webflow API error {resp.status_code}: {resp.text[:500]}"
                )

            if resp.status_code == 204:
                return {}
            data = resp.json()
            if isinstance(data, (dict, list)):
                return data
            return {}

    async def get_authorized_by(self) -> dict[str, Any]:
        result = await self.request("GET", "/token/authorized_by")
        return result if isinstance(result, dict) else {}

    async def list_sites(self) -> list[dict[str, Any]]:
        result = await self.request("GET", "/sites")
        if isinstance(result, dict):
            sites = result.get("sites")
            if isinstance(sites, list):
                return [s for s in sites if isinstance(s, dict)]
        return []

    async def get_site(self, site_id: str) -> dict[str, Any]:
        result = await self.request("GET", f"/sites/{site_id}")
        return result if isinstance(result, dict) else {}

    async def list_collections(self, site_id: str) -> list[dict[str, Any]]:
        result = await self.request("GET", f"/sites/{site_id}/collections")
        if isinstance(result, dict):
            collections = result.get("collections")
            if isinstance(collections, list):
                return [c for c in collections if isinstance(c, dict)]
        return []

    async def get_collection(self, collection_id: str) -> dict[str, Any]:
        result = await self.request("GET", f"/collections/{collection_id}")
        return result if isinstance(result, dict) else {}

    async def list_live_items(
        self,
        collection_id: str,
        *,
        offset: int = 0,
        limit: int = _PAGE_SIZE,
    ) -> tuple[list[dict[str, Any]], int]:
        result = await self.request(
            "GET",
            f"/collections/{collection_id}/items/live",
            params={"offset": offset, "limit": min(limit, _PAGE_SIZE)},
        )
        if not isinstance(result, dict):
            return [], 0
        items = result.get("items") or []
        pagination = result.get("pagination") or {}
        total = int(pagination.get("total", len(items)))
        parsed_items = [i for i in items if isinstance(i, dict)]
        return parsed_items, total

    async def list_all_live_items(
        self,
        collection_id: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        all_items: list[dict[str, Any]] = []
        offset = 0
        truncated = False
        page = 0
        while True:
            batch, total = await self.list_live_items(
                collection_id, offset=offset, limit=_PAGE_SIZE
            )
            all_items.extend(batch)
            offset += len(batch)
            page += 1
            if offset >= total or not batch:
                break
            if page >= _MAX_PAGINATION_PAGES:
                logger.warning(
                    "Webflow pagination cap reached for collection %s (%d items)",
                    collection_id,
                    len(all_items),
                )
                truncated = True
                break
        return all_items, truncated

    async def get_live_item(
        self,
        collection_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        result = await self.request(
            "GET",
            f"/collections/{collection_id}/items/{item_id}/live",
        )
        return result if isinstance(result, dict) else {}

    async def create_live_item(
        self,
        collection_id: str,
        field_data: dict[str, Any],
        *,
        is_draft: bool = False,
    ) -> dict[str, Any]:
        payload = {"fieldData": field_data, "isDraft": is_draft}
        result = await self.request(
            "POST",
            f"/collections/{collection_id}/items/live",
            json_body=payload,
        )
        return result if isinstance(result, dict) else {}

    async def create_staged_item(
        self,
        collection_id: str,
        field_data: dict[str, Any],
        *,
        is_draft: bool = True,
    ) -> dict[str, Any]:
        payload = {"fieldData": field_data, "isDraft": is_draft}
        result = await self.request(
            "POST",
            f"/collections/{collection_id}/items",
            json_body=payload,
        )
        return result if isinstance(result, dict) else {}

    async def publish_items(
        self,
        collection_id: str,
        item_ids: list[str],
    ) -> dict[str, Any]:
        result = await self.request(
            "POST",
            f"/collections/{collection_id}/items/publish",
            json_body={"itemIds": item_ids},
        )
        return result if isinstance(result, dict) else {}

    async def update_live_item(
        self,
        collection_id: str,
        item_id: str,
        field_data: dict[str, Any],
    ) -> dict[str, Any]:
        result = await self.request(
            "PATCH",
            f"/collections/{collection_id}/items/{item_id}/live",
            json_body={"fieldData": field_data},
        )
        return result if isinstance(result, dict) else {}

    async def create_asset(
        self,
        site_id: str,
        *,
        file_name: str,
        file_hash: str,
    ) -> dict[str, Any]:
        result = await self.request(
            "POST",
            f"/sites/{site_id}/assets",
            json_body={"fileName": file_name, "fileHash": file_hash},
        )
        return result if isinstance(result, dict) else {}

    async def upload_asset_bytes(
        self,
        site_id: str,
        *,
        file_name: str,
        content_bytes: bytes,
        mime_type: str = "image/png",
    ) -> dict[str, Any]:
        """Two-step asset upload: announce to Webflow, then POST binary to S3."""
        file_hash = hashlib.md5(content_bytes).hexdigest()
        meta = await self.create_asset(
            site_id,
            file_name=file_name,
            file_hash=file_hash,
        )
        upload_url = str(meta.get("uploadUrl") or "")
        upload_details = meta.get("uploadDetails")
        if not upload_url or not isinstance(upload_details, dict):
            raise CMSAPIError("Webflow asset upload metadata missing uploadUrl")

        form_fields: dict[str, str] = {}
        for key, value in upload_details.items():
            if value is not None and key != "uploadUrl":
                form_fields[key] = str(value)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    upload_url,
                    data=form_fields,
                    files={"file": (file_name, content_bytes, mime_type)},
                )
            except httpx.ConnectError as exc:
                raise CMSConnectionError(
                    f"Cannot reach Webflow asset upload URL: {exc}"
                ) from exc
            except httpx.TimeoutException as exc:
                raise CMSConnectionError(
                    f"Webflow asset upload timeout: {exc}"
                ) from exc

        if resp.status_code >= 400:
            raise CMSAPIError(
                f"Webflow asset binary upload failed ({resp.status_code}): "
                f"{resp.text[:300]}"
            )

        asset_url = str(meta.get("hostedUrl") or meta.get("url") or "")
        asset_id = str(meta.get("id") or "")
        return {
            "id": asset_id,
            "url": asset_url,
            "fileName": file_name,
            "raw": meta,
        }

    async def create_webhook(
        self,
        site_id: str,
        *,
        trigger_type: str,
        url: str,
    ) -> dict[str, Any]:
        result = await self.request(
            "POST",
            f"/sites/{site_id}/webhooks",
            json_body={"triggerType": trigger_type, "url": url},
        )
        return result if isinstance(result, dict) else {}

    async def list_webhooks(self, site_id: str) -> list[dict[str, Any]]:
        result = await self.request("GET", f"/sites/{site_id}/webhooks")
        if isinstance(result, dict):
            webhooks = result.get("webhooks")
            if isinstance(webhooks, list):
                return [w for w in webhooks if isinstance(w, dict)]
        return []

    async def delete_webhook(self, site_id: str, webhook_id: str) -> None:
        await self.request("DELETE", f"/sites/{site_id}/webhooks/{webhook_id}")
