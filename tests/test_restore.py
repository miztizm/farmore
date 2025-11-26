"""
Tests for restore functionality.

"Test your restores before disaster strikes." — schema.cx
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses

from farmore.restore import RestoreManager, RestoreResult, restore_from_backup


class TestRestoreResult:
    """Tests for RestoreResult dataclass."""

    def test_create_result(self) -> None:
        """Test creating a restore result."""
        result = RestoreResult(
            success=True,
            item_type="issue",
            item_name="issues",
            items_restored=5,
        )

        assert result.success is True
        assert result.item_type == "issue"
        assert result.items_restored == 5
        assert result.items_failed == 0

    def test_result_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = RestoreResult(
            success=True,
            item_type="release",
            item_name="releases",
            items_restored=3,
            restored_items=["v1.0", "v1.1", "v1.2"],
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["items_restored"] == 3
        assert len(data["restored_items"]) == 3


class TestRestoreManager:
    """Tests for RestoreManager class."""

    @responses.activate
    def test_restore_issues_dry_run(self) -> None:
        """Test dry run of issue restoration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a backup file
            backup_path = Path(tmpdir) / "issues.json"
            issues = [
                {"title": "Issue 1", "body": "Body 1"},
                {"title": "Issue 2", "body": "Body 2"},
            ]
            with open(backup_path, "w") as f:
                json.dump(issues, f)

            # Mock the existing issues endpoint
            responses.add(
                responses.GET,
                "https://api.github.com/repos/test/repo/issues",
                json=[],
                status=200,
            )

            manager = RestoreManager(token="test-token")
            result = manager.restore_issues(
                backup_path=backup_path,
                target_repo="test/repo",
                dry_run=True,
            )

            assert result.success is True
            assert result.items_restored == 2
            assert all("[DRY RUN]" in item for item in result.restored_items)

    @responses.activate
    def test_restore_issues_skip_existing(self) -> None:
        """Test skipping existing issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "issues.json"
            issues = [
                {"title": "Existing Issue", "body": "Already exists"},
                {"title": "New Issue", "body": "New"},
            ]
            with open(backup_path, "w") as f:
                json.dump(issues, f)

            # Mock existing issues
            responses.add(
                responses.GET,
                "https://api.github.com/repos/test/repo/issues",
                json=[{"title": "Existing Issue"}],
                status=200,
            )

            manager = RestoreManager(token="test-token")
            result = manager.restore_issues(
                backup_path=backup_path,
                target_repo="test/repo",
                skip_existing=True,
                dry_run=True,
            )

            assert result.items_skipped == 1
            assert result.items_restored == 1
            assert "Existing Issue" in result.skipped_items

    def test_restore_issues_invalid_file(self) -> None:
        """Test restoring from an invalid file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "invalid.json"
            with open(backup_path, "w") as f:
                f.write("not valid json")

            manager = RestoreManager(token="test-token")
            result = manager.restore_issues(
                backup_path=backup_path,
                target_repo="test/repo",
            )

            assert result.success is False
            assert "Failed to load" in result.error_message

    @responses.activate
    def test_restore_releases_dry_run(self) -> None:
        """Test dry run of release restoration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "releases.json"
            releases = [
                {"tag_name": "v1.0.0", "name": "Version 1.0"},
                {"tag_name": "v1.1.0", "name": "Version 1.1"},
            ]
            with open(backup_path, "w") as f:
                json.dump(releases, f)

            # Mock existing releases
            responses.add(
                responses.GET,
                "https://api.github.com/repos/test/repo/releases",
                json=[],
                status=200,
            )

            manager = RestoreManager(token="test-token")
            result = manager.restore_releases(
                backup_path=backup_path,
                target_repo="test/repo",
                dry_run=True,
            )

            assert result.success is True
            assert result.items_restored == 2

    @responses.activate
    def test_restore_labels_dry_run(self) -> None:
        """Test dry run of label restoration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "labels.json"
            labels = [
                {"name": "bug", "color": "d73a4a", "description": "Bug reports"},
                {"name": "feature", "color": "a2eeef", "description": "New features"},
            ]
            with open(backup_path, "w") as f:
                json.dump(labels, f)

            # Mock existing labels
            responses.add(
                responses.GET,
                "https://api.github.com/repos/test/repo/labels",
                json=[],
                status=200,
            )

            manager = RestoreManager(token="test-token")
            result = manager.restore_labels(
                backup_path=backup_path,
                target_repo="test/repo",
                dry_run=True,
            )

            assert result.success is True
            assert result.items_restored == 2

    @responses.activate
    def test_restore_milestones_dry_run(self) -> None:
        """Test dry run of milestone restoration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "milestones.json"
            milestones = [
                {"title": "v1.0", "description": "First release", "state": "open"},
                {"title": "v2.0", "description": "Second release", "state": "open"},
            ]
            with open(backup_path, "w") as f:
                json.dump(milestones, f)

            # Mock existing milestones
            responses.add(
                responses.GET,
                "https://api.github.com/repos/test/repo/milestones",
                json=[],
                status=200,
            )

            manager = RestoreManager(token="test-token")
            result = manager.restore_milestones(
                backup_path=backup_path,
                target_repo="test/repo",
                dry_run=True,
            )

            assert result.success is True
            assert result.items_restored == 2


class TestRestoreFromBackup:
    """Tests for restore_from_backup convenience function."""

    @responses.activate
    def test_restore_issues_via_function(self) -> None:
        """Test restoring issues via convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "issues.json"
            with open(backup_path, "w") as f:
                json.dump([{"title": "Test"}], f)

            responses.add(
                responses.GET,
                "https://api.github.com/repos/test/repo/issues",
                json=[],
                status=200,
            )

            result = restore_from_backup(
                backup_path=backup_path,
                target_repo="test/repo",
                token="test-token",
                item_type="issues",
                dry_run=True,
            )

            assert result.item_type == "issue"

    def test_restore_unknown_type(self) -> None:
        """Test restoring with unknown item type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "data.json"
            with open(backup_path, "w") as f:
                json.dump([], f)

            result = restore_from_backup(
                backup_path=backup_path,
                target_repo="test/repo",
                token="test-token",
                item_type="unknown",
            )

            assert result.success is False
            assert "Unknown item type" in result.error_message
