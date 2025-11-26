"""Tests for the analytics module."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from farmore.analytics import (
    BackupAnalytics,
    BackupHistory,
    BackupStats,
    RepositoryStats,
)


class TestRepositoryStats:
    """Tests for the RepositoryStats dataclass."""

    def test_repository_stats_creation(self):
        """Test creating repository stats."""
        stats = RepositoryStats(
            name="test-repo",
            path=Path("/backups/test-repo"),
            size_bytes=1024000,
            file_count=50,
            commit_count=100,
            branch_count=5,
            tag_count=10,
        )
        assert stats.name == "test-repo"
        assert stats.size_bytes == 1024000
        assert stats.commit_count == 100

    def test_repository_stats_size_properties(self):
        """Test size conversion properties."""
        stats = RepositoryStats(
            name="test-repo",
            path=Path("/backups/test-repo"),
            size_bytes=1024 * 1024 * 10,  # 10 MB
        )
        assert stats.size_mb == 10.0
        assert stats.size_gb == pytest.approx(0.00976, rel=0.01)

    def test_repository_stats_to_dict(self):
        """Test converting stats to dictionary."""
        stats = RepositoryStats(
            name="my-repo",
            path=Path("/backups/my-repo"),
            size_bytes=204800,
            commit_count=100,
            branch_count=5,
            tag_count=10,
        )
        data = stats.to_dict()
        assert data["name"] == "my-repo"
        assert data["size_bytes"] == 204800


class TestBackupStats:
    """Tests for the BackupStats dataclass."""

    def test_backup_stats_creation(self):
        """Test creating backup stats."""
        stats = BackupStats(
            path=Path("/backups"),
            total_repositories=10,
            total_size_bytes=1024000,
            total_files=500,
            total_commits=1000,
        )
        assert stats.total_repositories == 10
        assert stats.total_size_bytes == 1024000
        assert stats.total_commits == 1000

    def test_backup_stats_to_dict(self):
        """Test converting stats to dictionary."""
        stats = BackupStats(
            path=Path("/backups"),
            total_repositories=5,
            total_size_bytes=512000,
            total_files=100,
            total_commits=200,
        )
        data = stats.to_dict()
        assert data["total_repositories"] == 5
        assert data["total_size_bytes"] == 512000
        assert "analyzed_at" in data

    def test_backup_stats_avg_repo_size(self):
        """Test average repository size calculation."""
        stats = BackupStats(
            path=Path("/backups"),
            total_repositories=10,
            total_size_bytes=1024 * 1024 * 100,  # 100 MB total
        )
        assert stats.avg_repo_size_mb == 10.0

    def test_backup_stats_avg_repo_size_empty(self):
        """Test average repository size with no repos."""
        stats = BackupStats(
            path=Path("/backups"),
            total_repositories=0,
            total_size_bytes=0,
        )
        assert stats.avg_repo_size_mb == 0


class TestBackupHistory:
    """Tests for the BackupHistory dataclass."""

    def test_backup_history_creation(self):
        """Test creating backup history."""
        history = BackupHistory(
            backup_id="abc123",
            started_at="2024-06-01T10:00:00",
            completed_at="2024-06-01T10:30:00",
            duration_seconds=1800,
            repos_cloned=5,
            repos_updated=10,
            repos_failed=0,
            total_size_bytes=1024000,
            success=True,
        )
        assert history.backup_id == "abc123"
        assert history.repos_cloned == 5
        assert history.success is True

    def test_backup_history_to_dict(self):
        """Test converting history to dictionary."""
        history = BackupHistory(
            backup_id="def456",
            started_at="2024-06-15T10:00:00",
            completed_at="2024-06-15T10:15:00",
            duration_seconds=900,
            repos_cloned=3,
            repos_updated=7,
            repos_failed=1,
            success=False,
            error_message="Network error",
        )
        data = history.to_dict()
        assert data["backup_id"] == "def456"
        assert data["repos_failed"] == 1
        assert data["error_message"] == "Network error"


class TestBackupAnalytics:
    """Tests for the BackupAnalytics class."""

    @pytest.fixture
    def analytics(self, tmp_path):
        """Create an analytics instance with temp directory."""
        return BackupAnalytics(backup_dir=tmp_path)

    @pytest.fixture
    def mock_repo_dir(self, tmp_path):
        """Create a mock repository directory."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        git_dir = repo_dir / ".git"
        git_dir.mkdir()
        # Create some mock files
        (repo_dir / "README.md").write_text("# Test")
        (repo_dir / "src").mkdir()
        (repo_dir / "src" / "main.py").write_text("print('hello')")
        return repo_dir

    def test_analytics_initialization(self, analytics):
        """Test analytics initialization."""
        assert analytics is not None
        assert analytics.backup_dir is not None

    def test_get_directory_size(self, analytics, mock_repo_dir):
        """Test calculating directory size."""
        size = analytics._get_directory_size(mock_repo_dir)
        assert size > 0

    def test_analyze_directory_empty(self, analytics):
        """Test analyzing empty directory."""
        stats = analytics.analyze_directory()
        assert stats.total_repositories == 0
        assert stats.total_size_bytes == 0

    def test_analyze_directory_with_repos(self, analytics, mock_repo_dir, tmp_path):
        """Test analyzing directory with repositories."""
        # Create analytics with the temp path that contains the mock repo
        analytics = BackupAnalytics(backup_dir=tmp_path)
        stats = analytics.analyze_directory()
        assert stats.total_repositories >= 1

    @patch("subprocess.run")
    def test_analyze_repository(self, mock_run, analytics, mock_repo_dir):
        """Test analyzing a single repository."""
        # Mock git commands
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="50\n",
        )
        
        stats = analytics.analyze_repository(mock_repo_dir)
        assert stats is not None
        assert stats.name == "test-repo"

    def test_record_backup(self, analytics):
        """Test recording backup history."""
        history = analytics.record_backup(
            repos_cloned=5,
            repos_updated=10,
            repos_failed=0,
            duration_seconds=300,
            total_size_bytes=1024000,
        )
        assert history is not None
        assert history.repos_cloned == 5
        assert history.success is True

    def test_get_history(self, analytics):
        """Test getting backup history."""
        # Record some backups
        for i in range(5):
            analytics.record_backup(
                repos_cloned=i,
                repos_updated=i * 2,
                repos_failed=0,
                duration_seconds=100 + i * 10,
            )
        
        history = analytics.get_history(limit=3)
        assert len(history) == 3

    def test_generate_report_text(self, analytics, tmp_path):
        """Test generating text report."""
        report = analytics.generate_report(format="text")
        assert "FARMORE BACKUP REPORT" in report

    def test_generate_report_json(self, analytics, tmp_path):
        """Test generating JSON report."""
        report = analytics.generate_report(format="json")
        data = json.loads(report)
        assert "total_repositories" in data

    def test_get_growth_stats_no_history(self, analytics):
        """Test getting growth stats with no history."""
        stats = analytics.get_growth_stats()
        assert stats["has_data"] is False

    def test_get_growth_stats_with_history(self, analytics):
        """Test getting growth stats with history."""
        # Record multiple backups
        for i in range(3):
            analytics.record_backup(
                repos_cloned=i + 1,
                repos_updated=i * 2,
                repos_failed=0,
                duration_seconds=100,
            )
        
        stats = analytics.get_growth_stats()
        assert stats["has_data"] is True
        assert stats["backup_count"] == 3

    def test_categorize_repositories(self, analytics, tmp_path):
        """Test repository categorization."""
        # Create repos in different categories
        (tmp_path / "private" / "repo1").mkdir(parents=True)
        (tmp_path / "private" / "repo1" / ".git").mkdir()
        (tmp_path / "public" / "repo2").mkdir(parents=True)
        (tmp_path / "public" / "repo2" / ".git").mkdir()
        
        analytics = BackupAnalytics(backup_dir=tmp_path)
        repos = analytics._find_repositories(tmp_path)
        categories = analytics._categorize_repositories(repos)
        
        assert "private" in categories or "public" in categories or "other" in categories

    def test_analyze_languages(self, analytics, mock_repo_dir):
        """Test language analysis."""
        languages = analytics._analyze_languages(mock_repo_dir)
        assert "Python" in languages or "Markdown" in languages
