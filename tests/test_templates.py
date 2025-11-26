"""Tests for the templates module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from farmore.templates import (
    BUILTIN_TEMPLATES,
    BackupTemplate,
    TemplateManager,
)


class TestBackupTemplate:
    """Tests for the BackupTemplate dataclass."""

    def test_template_creation(self):
        """Test creating a backup template."""
        template = BackupTemplate(
            id="my-template",
            name="My Template",
            description="Test template",
            category="custom",
            target_type="user",
            include_forks=True,
            parallel_workers=8,
        )
        assert template.id == "my-template"
        assert template.name == "My Template"
        assert template.include_forks is True
        assert template.parallel_workers == 8

    def test_template_defaults(self):
        """Test template default values."""
        template = BackupTemplate(
            id="test",
            name="Test",
            description="Test",
            category="test",
        )
        assert template.target_type == "user"
        assert template.visibility == "all"
        assert template.include_forks is False
        assert template.bare is False
        assert template.parallel_workers == 4

    def test_template_to_dict(self):
        """Test converting template to dictionary."""
        template = BackupTemplate(
            id="test-template",
            name="Test Template",
            description="Test description",
            category="custom",
            include_issues=True,
            include_pulls=True,
        )
        data = template.to_dict()
        assert data["id"] == "test-template"
        assert data["include_issues"] is True
        assert data["include_pulls"] is True

    def test_template_from_dict(self):
        """Test creating template from dictionary."""
        data = {
            "id": "from-dict",
            "name": "From Dict",
            "description": "Created from dict",
            "category": "custom",
            "target_type": "org",
            "include_releases": True,
            "parallel_workers": 12,
        }
        template = BackupTemplate.from_dict(data)
        assert template.id == "from-dict"
        assert template.target_type == "org"
        assert template.include_releases is True
        assert template.parallel_workers == 12


class TestBuiltinTemplates:
    """Tests for the built-in templates."""

    def test_builtin_templates_exist(self):
        """Test that built-in templates are defined."""
        assert len(BUILTIN_TEMPLATES) >= 5

    def test_user_essential_template(self):
        """Test user-essential template."""
        template = next(t for t in BUILTIN_TEMPLATES if t.id == "user-essential")
        assert template.name == "User Essential"
        assert template.target_type == "user"
        assert template.include_forks is False
        assert template.skip_existing is True

    def test_user_complete_template(self):
        """Test user-complete template."""
        template = next(t for t in BUILTIN_TEMPLATES if t.id == "user-complete")
        assert template.include_issues is True
        assert template.include_pulls is True
        assert template.include_releases is True
        assert template.include_wikis is True

    def test_org_complete_template(self):
        """Test org-complete template."""
        template = next(t for t in BUILTIN_TEMPLATES if t.id == "org-complete")
        assert template.target_type == "org"
        assert template.schedule_interval == "daily"
        assert template.notify_on_failure is True

    def test_disaster_recovery_template(self):
        """Test disaster-recovery template."""
        template = next(t for t in BUILTIN_TEMPLATES if t.id == "disaster-recovery")
        assert template.bare is True
        assert template.lfs is True
        assert template.include_forks is True
        assert template.include_archived is True

    def test_all_templates_have_required_fields(self):
        """Test all templates have required fields."""
        for template in BUILTIN_TEMPLATES:
            assert template.id
            assert template.name
            assert template.description
            assert template.category


class TestTemplateManager:
    """Tests for the TemplateManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a template manager with temp directory."""
        return TemplateManager(config_dir=tmp_path)

    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert manager is not None

    def test_list_all_templates(self, manager):
        """Test listing all templates."""
        templates = manager.list_all()
        assert len(templates) >= len(BUILTIN_TEMPLATES)

    def test_list_builtin_templates(self, manager):
        """Test listing built-in templates only."""
        templates = manager.list_builtin()
        assert len(templates) == len(BUILTIN_TEMPLATES)

    def test_list_custom_templates_empty(self, manager):
        """Test listing custom templates when empty."""
        templates = manager.list_custom()
        assert len(templates) == 0

    def test_get_template_by_id(self, manager):
        """Test getting template by ID."""
        template = manager.get("user-essential")
        assert template is not None
        assert template.id == "user-essential"

    def test_get_nonexistent_template(self, manager):
        """Test getting nonexistent template."""
        template = manager.get("nonexistent")
        assert template is None

    def test_get_by_category(self, manager):
        """Test getting templates by category."""
        user_templates = manager.get_by_category("user")
        assert len(user_templates) >= 1
        for t in user_templates:
            assert t.category == "user"

    def test_get_by_tag(self, manager):
        """Test getting templates by tag."""
        tagged = manager.get_by_tag("complete")
        assert len(tagged) >= 1
        for t in tagged:
            assert "complete" in t.tags

    def test_search_templates(self, manager):
        """Test searching templates."""
        results = manager.search("disaster")
        assert len(results) >= 1

    def test_add_custom_template(self, manager, tmp_path):
        """Test adding a custom template."""
        template = BackupTemplate(
            id="my-custom",
            name="My Custom",
            description="Custom template",
            category="custom",
            include_issues=True,
        )
        manager.add_custom(template)
        
        custom = manager.list_custom()
        assert len(custom) == 1
        assert custom[0].id == "my-custom"

    def test_remove_custom_template(self, manager):
        """Test removing a custom template."""
        # Add first
        template = BackupTemplate(
            id="to-remove",
            name="To Remove",
            description="Will be removed",
            category="custom",
        )
        manager.add_custom(template)
        
        # Verify added
        assert manager.get("to-remove") is not None
        
        # Remove
        result = manager.remove_custom("to-remove")
        assert result is True
        
        # Verify removed
        custom = manager.list_custom()
        assert len(custom) == 0

    def test_remove_nonexistent_template(self, manager):
        """Test removing nonexistent template."""
        result = manager.remove_custom("nonexistent")
        assert result is False

    def test_export_template(self, manager, tmp_path):
        """Test exporting a template."""
        output_path = tmp_path / "exported.json"
        result = manager.export_template("user-essential", output_path)
        
        assert result is True
        assert output_path.exists()
        
        data = json.loads(output_path.read_text())
        assert data["id"] == "user-essential"

    def test_export_nonexistent_template(self, manager, tmp_path):
        """Test exporting nonexistent template."""
        output_path = tmp_path / "exported.json"
        result = manager.export_template("nonexistent", output_path)
        assert result is False

    def test_import_template(self, manager, tmp_path):
        """Test importing a template."""
        # Create template file
        template_data = {
            "id": "imported",
            "name": "Imported",
            "description": "Imported template",
            "category": "custom",
            "include_forks": True,
        }
        import_path = tmp_path / "to_import.json"
        import_path.write_text(json.dumps(template_data))
        
        # Import
        template = manager.import_template(import_path)
        
        assert template is not None
        assert template.id == "imported"
        assert template.include_forks is True

    def test_import_invalid_file(self, manager, tmp_path):
        """Test importing invalid file."""
        invalid_path = tmp_path / "invalid.json"
        invalid_path.write_text("not valid json")
        
        template = manager.import_template(invalid_path)
        assert template is None

    def test_apply_template(self, manager):
        """Test applying a template."""
        args = manager.apply_template("user-essential", "myuser")
        
        assert args is not None
        assert args["target_name"] == "myuser"
        assert args["target_type"] == "user"
        assert args["skip_existing"] is True

    def test_apply_nonexistent_template(self, manager):
        """Test applying nonexistent template."""
        args = manager.apply_template("nonexistent", "target")
        assert args is None

    def test_get_categories(self, manager):
        """Test getting all categories."""
        categories = manager.get_categories()
        assert "user" in categories
        assert "org" in categories

    def test_get_tags(self, manager):
        """Test getting all tags."""
        tags = manager.get_tags()
        assert "complete" in tags or "essential" in tags

    def test_update_existing_custom_template(self, manager):
        """Test updating an existing custom template."""
        # Add initial
        template1 = BackupTemplate(
            id="updatable",
            name="Original",
            description="Original description",
            category="custom",
        )
        manager.add_custom(template1)
        
        # Update with same ID
        template2 = BackupTemplate(
            id="updatable",
            name="Updated",
            description="Updated description",
            category="custom",
            include_issues=True,
        )
        manager.add_custom(template2)
        
        # Verify updated
        template = manager.get("updatable")
        assert template.name == "Updated"
        assert template.include_issues is True
        
        # Verify only one custom template
        assert len(manager.list_custom()) == 1
