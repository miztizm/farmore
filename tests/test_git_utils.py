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


# ── --ff-only / --force / reset-to-remote (mocked) ──────────────────────────


@patch("subprocess.run")
def test_pull_ff_only_passes_flag(mock_run: MagicMock, tmp_path: Path) -> None:
    """pull(ff_only=True) must add --ff-only to the git pull command."""
    (tmp_path / ".git").mkdir()
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="Already up to date.")

    success, _ = GitOperations.pull(tmp_path, "main", ff_only=True)

    assert success is True
    pull_cmds = [c.args[0] for c in mock_run.call_args_list if c.args[0][:2] == ["git", "pull"]]
    assert pull_cmds, "expected a git pull invocation"
    assert "--ff-only" in pull_cmds[0]


@patch("subprocess.run")
def test_pull_reports_divergence(mock_run: MagicMock, tmp_path: Path) -> None:
    """A non-fast-forwardable pull is reported as 'Diverged', not a hard failure string."""
    from subprocess import CalledProcessError

    (tmp_path / ".git").mkdir()
    mock_run.side_effect = [
        MagicMock(returncode=0, stderr="", stdout=""),  # checkout
        CalledProcessError(1, ["git", "pull"], stderr="fatal: Not possible to fast-forward, aborting."),
    ]

    success, message = GitOperations.pull(tmp_path, "main", ff_only=True)

    assert success is False
    assert "Diverged" in message and "--force" in message


@patch("subprocess.run")
def test_reset_to_remote_runs_reset_and_clean(mock_run: MagicMock, tmp_path: Path) -> None:
    """reset_to_remote does fetch + checkout -B + reset --hard + clean -fd."""
    (tmp_path / ".git").mkdir()
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

    success, message = GitOperations.reset_to_remote(tmp_path, "main")

    assert success is True
    assert message == "Reset to upstream"
    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert ["git", "reset", "--hard", "origin/main"] in cmds
    assert ["git", "clean", "-fd"] in cmds


@patch("subprocess.run")
def test_update_force_resets(mock_run: MagicMock, sample_repo: Repository, tmp_path: Path) -> None:
    """update(force=True) routes through a hard reset to origin/<default_branch>."""
    (tmp_path / ".git").mkdir()
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

    success, _ = GitOperations.update(sample_repo, tmp_path, force=True)

    assert success is True
    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert ["git", "reset", "--hard", "origin/main"] in cmds


@patch("subprocess.run")
def test_detect_default_branch_from_origin_head(mock_run: MagicMock, tmp_path: Path) -> None:
    """detect_default_branch prefers origin/HEAD (handles 'master' repos)."""
    mock_run.return_value = MagicMock(returncode=0, stdout="origin/master\n", stderr="")
    assert GitOperations.detect_default_branch(tmp_path) == "master"


# ── Real-git integration: force/ff-only/preservation end-to-end ─────────────


def _git(cwd: Path, *args: str):
    import subprocess

    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)


@pytest.mark.skipif(__import__("shutil").which("git") is None, reason="git not installed")
def test_force_and_ff_only_end_to_end(tmp_path: Path) -> None:
    """
    Against a controllable local 'remote': a diverged backup is reported by
    --ff-only and repaired by --force, while a committed-.gitignore'd file
    survives the reset (the whole point of force-mirroring).
    """
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(remote))

    seed = tmp_path / "seed"
    _git(tmp_path, "clone", str(remote), str(seed))
    _git(seed, "config", "user.email", "a@a")
    _git(seed, "config", "user.name", "a")
    (seed / ".gitignore").write_text("data/\n")
    (seed / "app.py").write_text("v1\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "init")
    _git(seed, "push", "-q", "origin", "main")

    backup = tmp_path / "backup"
    _git(tmp_path, "clone", str(remote), str(backup))
    _git(backup, "config", "user.email", "b@b")
    _git(backup, "config", "user.name", "b")
    repo = Repository(
        name="r", full_name="o/r", owner="o",
        ssh_url="", clone_url=str(remote), default_branch="main",
    )

    # Upstream advances...
    (seed / "app.py").write_text("v2-upstream\n")
    _git(seed, "commit", "-qam", "upstream v2")
    _git(seed, "push", "-q", "origin", "main")

    # ...and the backup diverges with its own commit + an ignored file + junk.
    (backup / "app.py").write_text("v2-local\n")
    _git(backup, "commit", "-qam", "local v2")
    (backup / "data").mkdir()
    (backup / "data" / "big.bin").write_text("KEEPME")
    (backup / "junk.txt").write_text("remove me")

    # --ff-only refuses and does not merge.
    ok, msg = GitOperations.update(repo, backup, ff_only=True)
    assert ok is False
    assert "Diverged" in msg
    assert "local v2" in _git(backup, "log", "--oneline", "-1").stdout

    # --force repairs: HEAD == origin, ignored file kept, junk gone.
    ok, msg = GitOperations.update(repo, backup, force=True)
    assert ok is True, msg
    assert (backup / "app.py").read_text().strip() == "v2-upstream"
    assert (backup / "data" / "big.bin").read_text() == "KEEPME"
    assert not (backup / "junk.txt").exists()
    head = _git(backup, "rev-parse", "HEAD").stdout.strip()
    origin = _git(backup, "rev-parse", "origin/main").stdout.strip()
    assert head == origin
