"""Tests for the diff module."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from farmore.diff import (
    BackupCompare,
    BackupDiff,
    ChangeType,
    FileChange,
    RepositoryDiff,
    SnapshotInfo,
)


class TestChangeType:
    """Tests for the ChangeType enum."""

    def test_change_types_exist(self):
        """Test that all change types are defined."""
        assert ChangeType.ADDED is not None
        assert ChangeType.REMOVED is not None
        assert ChangeType.MODIFIED is not None
        assert ChangeType.UNCHANGED is not None


class TestFileChange:
    """Tests for the FileChange dataclass."""

    def test_file_change_creation(self):
        """Test creating a file change."""
        change = FileChange(
            path="src/main.py",
            change_type=ChangeType.MODIFIED,
            old_size=100,
            new_size=150,
        )
        assert change.path == "src/main.py"
        assert change.change_type == ChangeType.MODIFIED
        assert change.old_size == 100
        assert change.new_size == 150

    def test_file_change_to_dict(self):
        """Test converting file change to dictionary."""
        change = FileChange(
            path="README.md",
            change_type=ChangeType.ADDED,
            old_size=None,
            new_size=500,
        )
        data = change.to_dict()
        assert data["path"] == "README.md"
        assert data["change_type"] == "added"
        assert data["new_size"] == 500


class TestRepositoryDiff:
    """Tests for the RepositoryDiff dataclass."""

    def test_repository_diff_creation(self):
        """Test creating a repository diff."""
        diff = RepositoryDiff(
            name="test-repo",
            path=Path("/backups/test-repo"),
            change_type=ChangeType.MODIFIED,
            commit_diff=5,
            old_head="abc123",
            new_head="def456",
        )
        assert diff.name == "test-repo"
        assert diff.change_type == ChangeType.MODIFIED
        assert diff.commit_diff == 5

    def test_repository_diff_file_counts(self):
        """Test file change counts."""
        diff = RepositoryDiff(
            name="test-repo",
            path=Path("/backups/test-repo"),
            change_type=ChangeType.MODIFIED,
            file_changes=[
                FileChange(path="a.py", change_type=ChangeType.ADDED),
                FileChange(path="b.py", change_type=ChangeType.ADDED),
                FileChange(path="c.py", change_type=ChangeType.MODIFIED),
                FileChange(path="d.py", change_type=ChangeType.REMOVED),
            ],
        )
        assert diff.files_added == 2
        assert diff.files_modified == 1
        assert diff.files_removed == 1

    def test_repository_diff_to_dict(self):
        """Test converting repository diff to dictionary."""
        diff = RepositoryDiff(
            name="my-repo",
            path=Path("/backups/my-repo"),
            change_type=ChangeType.MODIFIED,
            commit_diff=10,
        )
        data = diff.to_dict()
        assert data["name"] == "my-repo"
        assert data["commit_diff"] == 10


class TestBackupDiff:
    """Tests for the BackupDiff dataclass."""

    def test_backup_diff_creation(self):
        """Test creating a backup diff."""
        diff = BackupDiff(
            old_path=Path("/backups/v1"),
            new_path=Path("/backups/v2"),
            repos_added=["new-repo"],
            repos_removed=["old-repo"],
            repos_unchanged=["stable-repo"],
        )
        assert len(diff.repos_added) == 1
        assert len(diff.repos_removed) == 1
        assert diff.has_changes is True

    def test_backup_diff_no_changes(self):
        """Test backup diff with no changes."""
        diff = BackupDiff(
            old_path=Path("/backups/v1"),
            new_path=Path("/backups/v2"),
            repos_unchanged=["repo1", "repo2"],
        )
        assert diff.has_changes is False
        assert diff.total_changes == 0

    def test_backup_diff_to_dict(self):
        """Test converting backup diff to dictionary."""
        diff = BackupDiff(
            old_path=Path("/old"),
            new_path=Path("/new"),
            repos_added=["new-repo"],
        )
        data = diff.to_dict()
        assert data["repos_added"] == ["new-repo"]
        assert "summary" in data


class TestSnapshotInfo:
    """Tests for the SnapshotInfo dataclass."""

    def test_snapshot_info_creation(self):
        """Test creating snapshot info."""
        snapshot = SnapshotInfo(
            path=Path("/backups"),
            created_at="2024-06-01T10:00:00",
            repo_count=10,
            total_size_bytes=1024000,
        )
        assert snapshot.repo_count == 10
        assert snapshot.total_size_bytes == 1024000

    def test_snapshot_info_to_dict(self):
        """Test converting snapshot info to dictionary."""
        snapshot = SnapshotInfo(
            path=Path("/backups"),
            created_at="2024-06-15T10:00:00",
            repo_count=5,
            total_size_bytes=512000,
            repositories={"repo1": {"head": "abc123", "size": 100}},
        )
        data = snapshot.to_dict()
        assert data["repo_count"] == 5
        assert "repo1" in data["repositories"]


class TestBackupCompare:
    """Tests for the BackupCompare class."""

    @pytest.fixture
    def comparer(self):
        """Create a BackupCompare instance."""
        return BackupCompare()

    @pytest.fixture
    def mock_backup_v1(self, tmp_path):
        """Create a mock backup version 1."""
        v1 = tmp_path / "v1" / "repo"
        v1.mkdir(parents=True)
        (v1 / ".git").mkdir()
        (v1 / "README.md").write_text("# Version 1")
        (v1 / "src").mkdir()
        (v1 / "src" / "main.py").write_text("print('v1')")
        (v1 / "old_file.txt").write_text("old content")
        return v1.parent

    @pytest.fixture
    def mock_backup_v2(self, tmp_path):
        """Create a mock backup version 2."""
        v2 = tmp_path / "v2" / "repo"
        v2.mkdir(parents=True)
        (v2 / ".git").mkdir()
        (v2 / "README.md").write_text("# Version 2 - Updated")
        (v2 / "src").mkdir()
        (v2 / "src" / "main.py").write_text("print('v2')")
        (v2 / "src" / "new_module.py").write_text("# New file")
        return v2.parent

    def test_comparer_initialization(self, comparer):
        """Test comparer initialization."""
        assert comparer is not None

    def test_create_snapshot(self, comparer, mock_backup_v1):
        """Test creating a snapshot."""
        snapshot = comparer.create_snapshot(mock_backup_v1)
        assert snapshot is not None
        assert snapshot.repo_count >= 1

    def test_save_and_load_snapshot(self, comparer, mock_backup_v1):
        """Test saving and loading a snapshot."""
        # Save
        snapshot_path = comparer.save_snapshot(mock_backup_v1)
        assert snapshot_path.exists()
        
        # Load
        loaded = comparer.load_snapshot(mock_backup_v1)
        assert loaded is not None
        assert loaded.repo_count >= 1

    def test_compare_directories(self, comparer, mock_backup_v1, mock_backup_v2):
        """Test comparing two backup directories."""
        diff = comparer.compare_directories(mock_backup_v1, mock_backup_v2)
        
        assert diff is not None
        assert isinstance(diff, BackupDiff)

    def test_compare_repositories(self, comparer, tmp_path):
        """Test comparing two repository versions."""
        # Create two repos
        old = tmp_path / "old_repo"
        old.mkdir()
        (old / ".git").mkdir()
        (old / "file.txt").write_text("old")
        
        new = tmp_path / "new_repo"
        new.mkdir()
        (new / ".git").mkdir()
        (new / "file.txt").write_text("new")
        
        diff = comparer.compare_repositories(old, new, "test-repo")
        assert diff is not None
        assert diff.name == "test-repo"

    @patch("subprocess.run")
    def test_get_repository_log(self, mock_run, comparer, tmp_path):
        """Test getting repository log."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123|First commit|Author|2024-06-01\n",
        )
        
        log = comparer.get_repository_log(repo, limit=10)
        assert isinstance(log, list)

    def test_generate_diff_report_text(self, comparer):
        """Test generating text diff report."""
        diff = BackupDiff(
            old_path=Path("/old"),
            new_path=Path("/new"),
            repos_added=["new-repo"],
            repos_removed=["old-repo"],
        )
        
        report = comparer.generate_diff_report(diff, format="text")
        assert "FARMORE BACKUP DIFF REPORT" in report

    def test_generate_diff_report_json(self, comparer):
        """Test generating JSON diff report."""
        diff = BackupDiff(
            old_path=Path("/old"),
            new_path=Path("/new"),
            repos_added=["new-repo"],
        )
        
        report = comparer.generate_diff_report(diff, format="json")
        data = json.loads(report)
        assert "repos_added" in data

    def test_get_file_hashes(self, comparer, tmp_path):
        """Test getting file hashes."""
        (tmp_path / "test.txt").write_text("test content")
        
        hashes = comparer._get_file_hashes(tmp_path)
        assert "test.txt" in hashes

    def test_find_repositories(self, comparer, mock_backup_v1):
        """Test finding repositories."""
        repos = comparer._find_repositories(mock_backup_v1)
        assert len(repos) >= 1

    def test_get_directory_size(self, comparer, tmp_path):
        """Test getting directory size."""
        (tmp_path / "file.txt").write_text("content")
        
        size = comparer._get_directory_size(tmp_path)
        assert size > 0
