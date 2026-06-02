"""Map between normalized CMS models and Webflow collection fieldData."""
from __future__ import annotations

from typing import Any

from core.cms.adapters.webflow.client import parse_dt
from core.cms.models import CMSPost, CMSPostCreate, CMSPostStatus, CMSPostUpdate
from core.cms.webflow_models import WebflowCollectionConfig, WebflowFieldMapping


def _field_value(field_data: dict[str, Any], slug: str) -> Any:
    if not slug:
        return None
    return field_data.get(slug)


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_as_str(v) for v in value if _as_str(v)]
    text = _as_str(value)
    return [text] if text else []


def parse_webflow_item(
    raw: dict[str, Any],
    *,
    collection: WebflowCollectionConfig,
    item_url: str = "",
) -> CMSPost:
    """Normalize a Webflow live/staged item into ``CMSPost``."""
    mapping = collection.field_mapping
    field_data = raw.get("fieldData") or {}

    title = _as_str(_field_value(field_data, mapping.title_field))
    slug = _as_str(_field_value(field_data, mapping.slug_field))
    content_html = _as_str(_field_value(field_data, mapping.body_field))
    excerpt = _as_str(_field_value(field_data, mapping.excerpt_field))
    seo_title = _as_str(_field_value(field_data, mapping.seo_title_field))
    seo_description = _as_str(_field_value(field_data, mapping.seo_description_field))

    categories = _as_str_list(_field_value(field_data, mapping.category_field))
    tags = _as_str_list(_field_value(field_data, mapping.tags_field))

    is_draft = bool(raw.get("isDraft", False))
    status = CMSPostStatus.draft if is_draft else CMSPostStatus.publish

    published_at = parse_dt(raw.get("lastPublished") or raw.get("createdOn"))
    modified_at = parse_dt(raw.get("lastUpdated") or raw.get("lastPublished"))
    word_count = len(content_html.split()) if content_html else 0

    return CMSPost(
        cms_id=_as_str(raw.get("id")),
        title=title,
        slug=slug,
        content_html=content_html,
        excerpt=excerpt,
        status=status,
        url=item_url,
        published_at=published_at,
        modified_at=modified_at,
        categories=categories,
        tags=tags,
        seo_title=seo_title,
        seo_description=seo_description,
        word_count=word_count,
        raw_metadata={
            **raw,
            "collection_id": collection.collection_id,
            "collection_slug": collection.collection_slug,
        },
    )


def build_field_data_for_create(
    post: CMSPostCreate,
    mapping: WebflowFieldMapping,
) -> dict[str, Any]:
    field_data: dict[str, Any] = {}
    if mapping.title_field:
        field_data[mapping.title_field] = post.title
    if mapping.slug_field and post.slug:
        field_data[mapping.slug_field] = post.slug
    if mapping.body_field:
        field_data[mapping.body_field] = post.content_html
    if mapping.excerpt_field and post.excerpt:
        field_data[mapping.excerpt_field] = post.excerpt
    if mapping.seo_title_field and post.seo_title:
        field_data[mapping.seo_title_field] = post.seo_title
    if mapping.seo_description_field and post.seo_description:
        field_data[mapping.seo_description_field] = post.seo_description
    if mapping.category_field and post.categories:
        field_data[mapping.category_field] = post.categories[0]
    if mapping.tags_field and post.tags:
        field_data[mapping.tags_field] = post.tags
    if mapping.featured_image_field and post.featured_image_id:
        image_value: dict[str, str] = {"fileId": post.featured_image_id}
        if post.featured_image_url:
            image_value["url"] = post.featured_image_url
        field_data[mapping.featured_image_field] = image_value
    return field_data


_TITLE_SLUGS = frozenset({"name", "title", "post-title", "post-title-2"})
_SLUG_SLUGS = frozenset({"slug"})
_BODY_HINTS = frozenset({"body", "content", "post-body", "article", "rich-text", "richtext"})
_EXCERPT_HINTS = frozenset({"excerpt", "summary", "short-description", "intro"})
_SEO_TITLE_HINTS = frozenset({"seo-title", "meta-title", "og-title"})
_SEO_DESC_HINTS = frozenset({"seo-description", "meta-description", "og-description"})
_CATEGORY_HINTS = frozenset({"category", "categories", "topic", "section"})
_TAG_HINTS = frozenset({"tags", "tag", "topics"})
_IMAGE_TYPES = frozenset({"image", "imageref", "file", "externallink"})


def _normalize_slug(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _field_slug(field: dict[str, Any]) -> str:
    return _normalize_slug(str(field.get("slug") or ""))


def _field_display(field: dict[str, Any]) -> str:
    return _normalize_slug(str(field.get("displayName") or field.get("display_name") or ""))


def _field_type(field: dict[str, Any]) -> str:
    return _normalize_slug(str(field.get("type") or ""))


def _matches_hints(text: str, hints: frozenset[str]) -> bool:
    if not text:
        return False
    if text in hints:
        return True
    return any(h in text for h in hints)


def suggest_field_mapping(fields: list[dict[str, Any]]) -> WebflowFieldMapping:
    """Heuristic field mapping from a Webflow collection schema."""
    mapping = WebflowFieldMapping()
    assigned: set[str] = set()

    def pick(
        *,
        slug_set: frozenset[str] | None = None,
        type_set: frozenset[str] | None = None,
        hint_set: frozenset[str] | None = None,
        prefer_richtext: bool = False,
    ) -> str:
        candidates: list[tuple[int, str]] = []
        for field in fields:
            if not isinstance(field, dict):
                continue
            slug = _field_slug(field)
            if not slug or slug in assigned:
                continue
            ftype = _field_type(field)
            label = _field_display(field)
            score = 0
            if slug_set and slug in slug_set:
                score += 100
            if hint_set and (_matches_hints(slug, hint_set) or _matches_hints(label, hint_set)):
                score += 50
            if type_set and ftype in type_set:
                score += 30
            if prefer_richtext and ftype == "richtext":
                score += 40
            if score > 0:
                candidates.append((score, slug))
        if not candidates:
            return ""
        candidates.sort(key=lambda item: (-item[0], item[1]))
        chosen = candidates[0][1]
        assigned.add(chosen)
        return chosen

    mapping.title_field = pick(slug_set=_TITLE_SLUGS, hint_set=frozenset({"title", "name"})) or mapping.title_field
    slug_pick = pick(slug_set=_SLUG_SLUGS)
    if slug_pick:
        mapping.slug_field = slug_pick
    mapping.body_field = pick(
        hint_set=_BODY_HINTS,
        type_set=frozenset({"richtext"}),
        prefer_richtext=True,
    )
    mapping.excerpt_field = pick(
        hint_set=_EXCERPT_HINTS,
        type_set=frozenset({"plaintext", "text", "richtext"}),
    )
    mapping.seo_title_field = pick(hint_set=_SEO_TITLE_HINTS)
    mapping.seo_description_field = pick(
        hint_set=_SEO_DESC_HINTS,
        type_set=frozenset({"plaintext", "text"}),
    )
    mapping.category_field = pick(
        hint_set=_CATEGORY_HINTS,
        type_set=frozenset({"option", "reference", "multireference"}),
    )
    mapping.tags_field = pick(
        hint_set=_TAG_HINTS,
        type_set=frozenset({"plaintext", "text", "multireference"}),
    )
    mapping.featured_image_field = pick(type_set=_IMAGE_TYPES, hint_set=frozenset({"image", "thumbnail", "hero"}))
    return mapping


def build_field_data_for_update(
    updates: CMSPostUpdate,
    mapping: WebflowFieldMapping,
) -> dict[str, Any]:
    field_data: dict[str, Any] = {}
    if updates.title is not None and mapping.title_field:
        field_data[mapping.title_field] = updates.title
    if updates.slug is not None and mapping.slug_field:
        field_data[mapping.slug_field] = updates.slug
    if updates.content_html is not None and mapping.body_field:
        field_data[mapping.body_field] = updates.content_html
    if updates.excerpt is not None and mapping.excerpt_field:
        field_data[mapping.excerpt_field] = updates.excerpt
    if updates.seo_title is not None and mapping.seo_title_field:
        field_data[mapping.seo_title_field] = updates.seo_title
    if updates.seo_description is not None and mapping.seo_description_field:
        field_data[mapping.seo_description_field] = updates.seo_description
    return field_data
