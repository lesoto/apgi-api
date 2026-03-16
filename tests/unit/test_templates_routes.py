"""
Unit tests for templates routes.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import HTTPException, status
from datetime import datetime
from app.models.schemas import SessionTemplateCreateRequest, SessionTemplateUpdateRequest
from app.routes.templates import init_template_routes


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.execute = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_current_user():
    """Mock current user."""
    user = Mock()
    user.user_id = "user123"
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_template():
    """Mock template."""
    template = MagicMock()
    template.template_id = "template123"
    template.user_id = "user123"
    template.name = "Test Template"
    template.description = "A test template"
    template.config_path = "/path/to/config"
    template.custom_config = {"key": "value"}
    template.default_description = "Default description"
    template.tags = ["tag1", "tag2"]
    template.is_public = False
    template.created_at = datetime.now()
    template.updated_at = datetime.now()
    return template


class TestTemplateRoutes:
    """Test template routes."""

    def test_init_template_routes(self):
        """Test template routes initialization."""
        init_template_routes()
        # Should not raise any errors

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_list_templates_success(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_db,
        mock_current_user,
        mock_template,
    ):
        """Test successful template listing."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_template]
        mock_db.query.return_value.filter.return_value.count.return_value = 1

        # Import after mocking
        from app.routes.templates import list_templates

        result = await list_templates(
            page=1, per_page=10, public_only=False, current_user=mock_current_user
        )

        assert len(result.templates) == 1
        assert result.pagination.page == 1
        assert result.pagination.total == 1

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_list_templates_invalid_page(
        self, mock_require_permission, mock_get_user, mock_get_db, mock_current_user
    ):
        """Test listing templates with invalid page."""
        mock_get_user.return_value = mock_current_user

        from app.routes.templates import list_templates

        with pytest.raises(HTTPException) as exc_info:
            await list_templates(
                page=0, per_page=10, public_only=False, current_user=mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_list_templates_invalid_per_page(
        self, mock_require_permission, mock_get_user, mock_get_db, mock_current_user
    ):
        """Test listing templates with invalid per_page."""
        mock_get_user.return_value = mock_current_user

        from app.routes.templates import list_templates

        with pytest.raises(HTTPException) as exc_info:
            await list_templates(
                page=1, per_page=101, public_only=False, current_user=mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_list_templates_public_only(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_db,
        mock_current_user,
        mock_template,
    ):
        """Test listing public templates only."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_template.is_public = True
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_template]
        mock_db.query.return_value.filter.return_value.count.return_value = 1

        from app.routes.templates import list_templates

        result = await list_templates(
            page=1, per_page=10, public_only=True, current_user=mock_current_user
        )

        assert len(result.templates) == 1

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_create_template_success(
        self, mock_require_permission, mock_get_user, mock_get_db, mock_db, mock_current_user
    ):
        """Test successful template creation."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalar_one_or_none.return_value = None  # No existing template

        created_template = MagicMock()
        created_template.template_id = "new_template"
        created_template.user_id = "user123"
        created_template.name = "New Template"
        created_template.description = "A new template"
        created_template.config_path = "/path"
        created_template.custom_config = {}
        created_template.default_description = "Default"
        created_template.tags = []
        created_template.is_public = False
        created_template.created_at = datetime.now()
        created_template.updated_at = datetime.now()
        mock_db.add.side_effect = lambda t: setattr(
            created_template,
            "template_id",
            t.template_id if hasattr(t, "template_id") else "new_template",
        )

        from app.routes.templates import create_template

        request = SessionTemplateCreateRequest(
            name="New Template",
            description="A new template",
            config_path="/path",
            custom_config={},
            default_description="Default",
            tags=[],
            is_public=False,
        )

        result = await create_template(request, current_user=mock_current_user)

        assert result.name == "New Template"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_create_template_duplicate_name(
        self, mock_require_permission, mock_get_user, mock_get_db, mock_db, mock_current_user
    ):
        """Test template creation with duplicate name."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalar_one_or_none.return_value = (
            MagicMock()
        )  # Existing template

        from app.routes.templates import create_template

        request = SessionTemplateCreateRequest(
            name="Existing Template",
            description="Template",
            config_path="/path",
            custom_config={},
            default_description="Default",
            tags=[],
            is_public=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_template(request, current_user=mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_get_template_success(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_db,
        mock_current_user,
        mock_template,
    ):
        """Test successful template retrieval."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_template

        from app.routes.templates import get_template

        result = await get_template("template123", current_user=mock_current_user)

        assert result.template_id == "template123"
        assert result.name == "Test Template"

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_get_template_not_found(
        self, mock_require_permission, mock_get_user, mock_get_db, mock_db, mock_current_user
    ):
        """Test getting non-existent template."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        from app.routes.templates import get_template

        with pytest.raises(HTTPException) as exc_info:
            await get_template("nonexistent", current_user=mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_get_template_access_denied(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_db,
        mock_current_user,
        mock_template,
    ):
        """Test getting template with access denied."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_template.user_id = "other_user"
        mock_template.is_public = False
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_template

        from app.routes.templates import get_template

        with pytest.raises(HTTPException) as exc_info:
            await get_template("template123", current_user=mock_current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_update_template_success(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_db,
        mock_current_user,
        mock_template,
    ):
        """Test successful template update."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_template

        from app.routes.templates import update_template

        request = SessionTemplateUpdateRequest(
            name="Updated Template",
            description="Updated description",
            config_path="default",
            custom_config={},
            default_description="Default description",
            tags=[],
            is_public=False,
        )

        result = await update_template("template123", request, current_user=mock_current_user)

        assert result.name == "Updated Template"

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_update_template_not_owner(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_db,
        mock_current_user,
        mock_template,
    ):
        """Test updating template by non-owner."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_template.user_id = "other_user"
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_template

        from app.routes.templates import update_template

        request = SessionTemplateUpdateRequest(
            name="Updated",
            description="Updated description",
            config_path="default",
            custom_config={},
            default_description="Default description",
            tags=[],
            is_public=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_template("template123", request, current_user=mock_current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_delete_template_success(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_db,
        mock_current_user,
        mock_template,
    ):
        """Test successful template deletion."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_template

        from app.routes.templates import delete_template

        await delete_template("template123", current_user=mock_current_user)

        mock_db.delete.assert_called_once_with(mock_template)

    @patch("app.routes.templates.get_db_context")
    @patch("app.routes.templates.get_current_user")
    @patch("app.routes.templates.require_permission")
    async def test_delete_template_not_owner(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_db,
        mock_current_user,
        mock_template,
    ):
        """Test deleting template by non-owner."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_template.user_id = "other_user"
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_template

        from app.routes.templates import delete_template

        with pytest.raises(HTTPException) as exc_info:
            await delete_template("template123", current_user=mock_current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
