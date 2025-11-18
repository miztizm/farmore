"""
Tests for Git utilities.

"Git is complicated. Tests make it less so." — schema.cx
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from farmore.git_utils import GitOperations
from farmore.models import Repository


@pytest.fixture
def sample_repo() -> Repository:
    """Create a sample repository for testing."""
    return Repository(
        name="test-repo",
        full_name="owner/test-repo",
        owner="owner",
        ssh_url="git@github.com:owner/test-repo.git",
        clone_url="https://github.com/owner/test-repo.git",
        default_branch="main",
    )


def test_is_git_repository(tmp_path: Path) -> None:
    """Test checking if a directory is a git repository."""
    # Not a git repo
    assert GitOperations.is_git_repository(tmp_path) is False

    # Create .git directory
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Now it's a git repo
    assert GitOperations.is_git_repository(tmp_path) is True


@patch("subprocess.run")
def test_get_remote_url(mock_run: MagicMock, tmp_path: Path) -> None:
    """Test getting remote URL."""
    # Create .git directory
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Mock successful git remote get-url
    mock_run.return_value = MagicMock(
        stdout="git@github.com:owner/repo.git\n",
        returncode=0,
    )

    url = GitOperations.get_remote_url(tmp_path)
    assert url == "git@github.com:owner/repo.git"


@patch("subprocess.run")
def test_clone_ssh_success(mock_run: MagicMock, sample_repo: Repository, tmp_path: Path) -> None:
    """Test successful SSH clone."""
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

    dest = tmp_path / "test-repo"
    success, message = GitOperations.clone(sample_repo, dest, use_ssh=True)

    assert success is True
    assert "success" in message.lower()
    mock_run.assert_called_once()

    # Check that SSH URL was used
    call_args = mock_run.call_args[0][0]
    assert sample_repo.ssh_url in call_args


@patch("subprocess.run")
def test_clone_https_success(mock_run: MagicMock, sample_repo: Repository, tmp_path: Path) -> None:
    """Test successful HTTPS clone."""
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

    dest = tmp_path / "test-repo"
    success, message = GitOperations.clone(sample_repo, dest, use_ssh=False)

    assert success is True
    assert "success" in message.lower()

    # Check that HTTPS URL was used
    call_args = mock_run.call_args[0][0]
    assert sample_repo.clone_url in call_args


@patch("subprocess.run")
def test_clone_ssh_failure(mock_run: MagicMock, sample_repo: Repository, tmp_path: Path) -> None:
    """Test SSH clone failure."""
    from subprocess import CalledProcessError

    mock_run.side_effect = CalledProcessError(
        returncode=128,
        cmd=["git", "clone"],
        stderr="Permission denied (publickey)",
    )

    dest = tmp_path / "test-repo"
    success, message = GitOperations.clone(sample_repo, dest, use_ssh=True)

    assert success is False
    assert "SSH authentication failed" in message


@patch("subprocess.run")
def test_fetch_success(mock_run: MagicMock, tmp_path: Path) -> None:
    """Test successful fetch."""
    # Create .git directory
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

    success, message = GitOperations.fetch(tmp_path)

    assert success is True
    assert "success" in message.lower()


@patch("subprocess.run")
def test_pull_success(mock_run: MagicMock, tmp_path: Path) -> None:
    """Test successful pull."""
    # Create .git directory
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    mock_run.return_value = MagicMock(
        returncode=0,
        stderr="",
        stdout="Already up to date.",
    )

    success, message = GitOperations.pull(tmp_path, "main")

    assert success is True
    assert "up to date" in message.lower()


@patch("subprocess.run")
def test_pull_with_updates(mock_run: MagicMock, tmp_path: Path) -> None:
    """Test pull with actual updates."""
    # Create .git directory
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    mock_run.return_value = MagicMock(
        returncode=0,
        stderr="",
        stdout="Updating abc123..def456\nFast-forward",
    )

    success, message = GitOperations.pull(tmp_path, "main")

    assert success is True
    assert "updated" in message.lower()


@patch("subprocess.run")
def test_update_success(mock_run: MagicMock, sample_repo: Repository, tmp_path: Path) -> None:
    """Test successful update (fetch + pull)."""
    # Create .git directory
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    mock_run.return_value = MagicMock(
        returncode=0,
        stderr="",
        stdout="Already up to date.",
    )

    success, message = GitOperations.update(sample_repo, tmp_path)

    assert success is True
    # Should have called git commands
    assert mock_run.call_count >= 2  # fetch + checkout + pull


def test_is_git_repository_nonexistent(tmp_path: Path) -> None:
    """Test checking non-existent directory."""
    nonexistent = tmp_path / "does-not-exist"
    assert GitOperations.is_git_repository(nonexistent) is False
