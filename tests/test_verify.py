"""
Tests for backup verification.

"Verify twice, restore once." — schema.cx
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from farmore.verify import BackupVerifier, VerificationResult, verify_backup


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_create_result(self) -> None:
        """Test creating a verification result."""
        result = VerificationResult(
            path=Path("/tmp/test"),
            is_valid=True,
            repository_name="test-repo",
        )

        assert result.is_valid is True
        assert result.repository_name == "test-repo"
        assert result.git_valid is True
        assert result.files_checked == 0

    def test_result_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = VerificationResult(
            path=Path("/tmp/test"),
            is_valid=True,
            repository_name="test",
            git_errors=["error1"],
        )

        data = result.to_dict()

        assert data["is_valid"] is True
        assert "test" in data["path"]  # Path separator varies by OS
        assert "error1" in data["git_errors"]


class TestBackupVerifier:
    """Tests for BackupVerifier class."""

    def test_verify_nonexistent_path(self) -> None:
        """Test verifying a path that doesn't exist."""
        verifier = BackupVerifier()
        result = verifier.verify_repository(Path("/nonexistent/path"))

        assert result.is_valid is False
        assert "does not exist" in result.error_message

    def test_verify_non_git_directory(self) -> None:
        """Test verifying a directory that's not a git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = BackupVerifier()
            result = verifier.verify_repository(Path(tmpdir))

            assert result.is_valid is False
            assert "Not a valid git repository" in result.error_message

    @patch("subprocess.run")
    def test_verify_valid_repository(self, mock_run: MagicMock) -> None:
        """Test verifying a valid git repository."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / ".git").mkdir()

            verifier = BackupVerifier()
            result = verifier.verify_repository(repo_path)

            assert result.git_valid is True

    @patch("subprocess.run")
    def test_verify_bare_repository(self, mock_run: MagicMock) -> None:
        """Test verifying a bare git repository."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / "HEAD").touch()

            verifier = BackupVerifier()
            result = verifier.verify_repository(repo_path)

            assert result.git_valid is True

    @patch("subprocess.run")
    def test_verify_with_git_errors(self, mock_run: MagicMock) -> None:
        """Test verification when git commands fail."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="fatal: not a git repository",
            stdout="",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / ".git").mkdir()

            verifier = BackupVerifier()
            result = verifier.verify_repository(repo_path)

            assert result.git_valid is False
            assert result.is_valid is False
            assert len(result.git_errors) > 0

    @patch("subprocess.run")
    def test_verify_deep(self, mock_run: MagicMock) -> None:
        """Test deep verification with git fsck."""
        # First call for HEAD, second for fsck
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr="", stdout="abc123"),
            MagicMock(returncode=0, stderr="", stdout=""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / ".git").mkdir()

            verifier = BackupVerifier()
            result = verifier.verify_repository(repo_path, deep=True)

            assert result.verification_type == "deep"
            assert mock_run.call_count == 2

    def test_verify_backup_directory_empty(self) -> None:
        """Test verifying an empty backup directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = BackupVerifier()
            results = verifier.verify_backup_directory(Path(tmpdir))

            assert results == []

    @patch("subprocess.run")
    def test_verify_backup_directory_with_repos(self, mock_run: MagicMock) -> None:
        """Test verifying a directory with multiple repositories."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create some test repos
            for name in ["repo1", "repo2"]:
                repo_path = base / name
                repo_path.mkdir()
                (repo_path / ".git").mkdir()

            verifier = BackupVerifier()
            results = verifier.verify_backup_directory(base)

            assert len(results) == 2


class TestVerifyBackupFunction:
    """Tests for the verify_backup convenience function."""

    @patch("subprocess.run")
    def test_verify_single_repo(self, mock_run: MagicMock) -> None:
        """Test verifying a single repository via convenience function."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / ".git").mkdir()

            results = verify_backup(repo_path)

            assert len(results) == 1

    def test_verify_directory(self) -> None:
        """Test verifying a directory without repos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = verify_backup(Path(tmpdir))

            # No repos to verify
            assert results == []
