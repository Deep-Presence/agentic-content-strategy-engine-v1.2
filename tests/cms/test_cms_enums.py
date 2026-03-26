"""Tests for CMS enum values and serialization."""
from __future__ import annotations

from core.db.enums import CMSPostStatus, CMSProvider, CMSPublishAction


class TestCMSProviderEnum:
    def test_values(self) -> None:
        assert CMSProvider.wordpress.value == "wordpress"
        assert CMSProvider.webflow.value == "webflow"
        assert CMSProvider.strapi.value == "strapi"
        assert CMSProvider.ghost.value == "ghost"
        assert CMSProvider.hubspot.value == "hubspot"

    def test_from_string(self) -> None:
        assert CMSProvider("wordpress") == CMSProvider.wordpress

    def test_is_str_enum(self) -> None:
        assert isinstance(CMSProvider.wordpress, str)


class TestCMSPostStatusEnum:
    def test_values(self) -> None:
        assert CMSPostStatus.draft.value == "draft"
        assert CMSPostStatus.publish.value == "publish"
        assert CMSPostStatus.pending.value == "pending"
        assert CMSPostStatus.private.value == "private"

    def test_from_string(self) -> None:
        assert CMSPostStatus("draft") == CMSPostStatus.draft


class TestCMSPublishActionEnum:
    def test_values(self) -> None:
        assert CMSPublishAction.create.value == "create"
        assert CMSPublishAction.update.value == "update"
        assert CMSPublishAction.refresh.value == "refresh"

    def test_from_string(self) -> None:
        assert CMSPublishAction("refresh") == CMSPublishAction.refresh


class TestOrmModelImport:
    """Verify ORM models can be imported without error."""

    def test_connection_model(self) -> None:
        from core.db.models.cms import CMSConnectionModel
        assert CMSConnectionModel.__tablename__ == "cms_connections"

    def test_publish_record_model(self) -> None:
        from core.db.models.cms import CMSPublishRecordModel
        assert CMSPublishRecordModel.__tablename__ == "cms_publish_records"

    def test_synced_post_model(self) -> None:
        from core.db.models.cms import CMSSyncedPostModel
        assert CMSSyncedPostModel.__tablename__ == "cms_synced_posts"


class TestRepositoryImport:
    """Verify repositories can be imported."""

    def test_connection_repo(self) -> None:
        from core.db.repositories.cms_repo import CMSConnectionRepository
        assert CMSConnectionRepository.model_class.__tablename__ == "cms_connections"

    def test_publish_repo(self) -> None:
        from core.db.repositories.cms_repo import CMSPublishRecordRepository
        assert CMSPublishRecordRepository.model_class.__tablename__ == "cms_publish_records"

    def test_synced_repo(self) -> None:
        from core.db.repositories.cms_repo import CMSSyncedPostRepository
        assert CMSSyncedPostRepository.model_class.__tablename__ == "cms_synced_posts"
