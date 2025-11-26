"""
Tests for configuration profile management.

"Test your configs before they test you." — schema.cx
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from farmore.config import BackupProfile, ConfigManager, create_profile_from_args


class TestBackupProfile:
    """Tests for BackupProfile dataclass."""

    def test_create_profile(self) -> None:
        """Test creating a basic profile."""
        profile = BackupProfile(
            name="test-profile",
            target_type="user",
            target_name="testuser",
        )

        assert profile.name == "test-profile"
        assert profile.target_type == "user"
        assert profile.target_name == "testuser"
        assert profile.visibility == "all"
        assert profile.include_forks is False
        assert profile.parallel_workers == 4

    def test_profile_to_dict(self) -> None:
        """Test converting profile to dictionary."""
        profile = BackupProfile(
            name="test",
            target_type="org",
            target_name="myorg",
            include_issues=True,
        )

        data = profile.to_dict()

        assert data["name"] == "test"
        assert data["target_type"] == "org"
        assert data["include_issues"] is True

    def test_profile_from_dict(self) -> None:
        """Test creating profile from dictionary."""
        data = {
            "name": "imported",
            "target_type": "user",
            "target_name": "someone",
            "parallel_workers": 8,
        }

        profile = BackupProfile.from_dict(data)

        assert profile.name == "imported"
        assert profile.parallel_workers == 8

    def test_profile_from_dict_with_defaults(self) -> None:
        """Test that missing fields get default values."""
        data = {"name": "minimal"}

        profile = BackupProfile.from_dict(data)

        assert profile.name == "minimal"
        assert profile.target_type == "user"
        assert profile.visibility == "all"


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_save_and_load_profile(self) -> None:
        """Test saving and loading a profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=Path(tmpdir))

            profile = BackupProfile(
                name="test-save",
                target_type="user",
                target_name="testuser",
            )

            manager.save_profile(profile)
            loaded = manager.load_profile("test-save")

            assert loaded is not None
            assert loaded.name == "test-save"
            assert loaded.target_name == "testuser"

    def test_load_nonexistent_profile(self) -> None:
        """Test loading a profile that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=Path(tmpdir))

            result = manager.load_profile("nonexistent")

            assert result is None

    def test_delete_profile(self) -> None:
        """Test deleting a profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=Path(tmpdir))

            profile = BackupProfile(
                name="to-delete",
                target_type="user",
                target_name="testuser",
            )
            manager.save_profile(profile)

            # Verify it exists
            assert manager.load_profile("to-delete") is not None

            # Delete it
            result = manager.delete_profile("to-delete")
            assert result is True

            # Verify it's gone
            assert manager.load_profile("to-delete") is None

    def test_delete_nonexistent_profile(self) -> None:
        """Test deleting a profile that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=Path(tmpdir))

            result = manager.delete_profile("nonexistent")

            assert result is False

    def test_list_profiles(self) -> None:
        """Test listing all profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=Path(tmpdir))

            # Initially empty
            assert manager.list_profiles() == []

            # Add some profiles
            for name in ["profile1", "profile2", "profile3"]:
                profile = BackupProfile(
                    name=name,
                    target_type="user",
                    target_name=f"user-{name}",
                )
                manager.save_profile(profile)

            profiles = manager.list_profiles()

            assert len(profiles) == 3
            names = {p.name for p in profiles}
            assert names == {"profile1", "profile2", "profile3"}

    def test_export_and_import_profile(self) -> None:
        """Test exporting and importing profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=Path(tmpdir))
            export_path = Path(tmpdir) / "exported.yaml"

            # Create and save a profile
            profile = BackupProfile(
                name="exportable",
                target_type="org",
                target_name="myorg",
                include_issues=True,
                parallel_workers=8,
            )
            manager.save_profile(profile)

            # Export it
            result = manager.export_profile("exportable", export_path)
            assert result is True
            assert export_path.exists()

            # Delete it
            manager.delete_profile("exportable")

            # Import it with a new name
            imported = manager.import_profile(export_path, "imported-profile")
            assert imported is not None
            assert imported.name == "imported-profile"
            assert imported.target_name == "myorg"
            assert imported.include_issues is True

    def test_export_nonexistent_profile(self) -> None:
        """Test exporting a profile that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=Path(tmpdir))

            result = manager.export_profile("nonexistent", Path(tmpdir) / "out.yaml")

            assert result is False


class TestCreateProfileFromArgs:
    """Tests for create_profile_from_args helper function."""

    def test_create_minimal_profile(self) -> None:
        """Test creating a profile with minimal arguments."""
        profile = create_profile_from_args(
            name="cli-profile",
            target_type="user",
            target_name="cliuser",
        )

        assert profile.name == "cli-profile"
        assert profile.target_type == "user"
        assert profile.target_name == "cliuser"

    def test_create_full_profile(self) -> None:
        """Test creating a profile with all options."""
        profile = create_profile_from_args(
            name="full-profile",
            target_type="org",
            target_name="myorg",
            dest="/backups/myorg",
            visibility="public",
            include_forks=True,
            include_archived=True,
            include_issues=True,
            include_pulls=True,
            include_releases=True,
            include_wikis=True,
            parallel_workers=16,
            skip_existing=True,
            bare=True,
            lfs=True,
            incremental=True,
            description="Full backup profile",
        )

        assert profile.name == "full-profile"
        assert profile.dest == "/backups/myorg"
        assert profile.include_forks is True
        assert profile.include_issues is True
        assert profile.parallel_workers == 16
        assert profile.bare is True
        assert profile.description == "Full backup profile"
