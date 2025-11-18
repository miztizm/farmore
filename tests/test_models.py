"""
Tests for data models.

"Models are just structured assumptions. Test them." — schema.cx
"""

from pathlib import Path

from farmore.models import (
    Config,
    MirrorResult,
    MirrorSummary,
    Repository,
    TargetType,
    Visibility,
)


def test_repository_creation() -> None:
    """Test repository model creation."""
    repo = Repository(
        name="test-repo",
        full_name="owner/test-repo",
        owner="owner",
        ssh_url="git@github.com:owner/test-repo.git",
        clone_url="https://github.com/owner/test-repo.git",
        default_branch="main",
        private=False,
        fork=False,
        archived=False,
    )

    assert repo.name == "test-repo"
    assert repo.full_name == "owner/test-repo"
    assert repo.local_path == "owner/test-repo"


def test_repository_local_path() -> None:
    """Test repository local path generation."""
    repo = Repository(
        name="my-repo",
        full_name="myuser/my-repo",
        owner="myuser",
        ssh_url="git@github.com:myuser/my-repo.git",
        clone_url="https://github.com/myuser/my-repo.git",
        default_branch="main",
    )

    assert repo.local_path == "myuser/my-repo"


def test_config_creation() -> None:
    """Test config model creation."""
    config = Config(
        target_type=TargetType.USER,
        target_name="testuser",
        dest=Path("/tmp/backups"),
    )

    assert config.target_type == TargetType.USER
    assert config.target_name == "testuser"
    assert config.dest == Path("/tmp/backups")
    assert config.visibility == Visibility.ALL
    assert config.include_forks is False
    assert config.include_archived is False
    assert config.dry_run is False
    assert config.max_workers == 4


def test_config_path_expansion() -> None:
    """Test that config expands user home directory."""
    config = Config(
        target_type=TargetType.USER,
        target_name="testuser",
        dest=Path("~/backups"),
    )

    # Should expand ~ to actual home directory
    assert "~" not in str(config.dest)


def test_mirror_summary_add_result() -> None:
    """Test mirror summary result tracking."""
    summary = MirrorSummary()
    repo = Repository(
        name="test",
        full_name="owner/test",
        owner="owner",
        ssh_url="git@github.com:owner/test.git",
        clone_url="https://github.com/owner/test.git",
        default_branch="main",
    )

    # Add cloned result
    result = MirrorResult(repo=repo, success=True, action="cloned", message="OK")
    summary.add_result(result)

    assert summary.total == 1
    assert summary.cloned == 1
    assert summary.updated == 0
    assert summary.failed == 0

    # Add updated result
    result = MirrorResult(repo=repo, success=True, action="updated", message="OK")
    summary.add_result(result)

    assert summary.total == 2
    assert summary.cloned == 1
    assert summary.updated == 1

    # Add failed result
    result = MirrorResult(repo=repo, success=False, action="failed", error="Something went wrong")
    summary.add_result(result)

    assert summary.total == 3
    assert summary.failed == 1
    assert len(summary.errors) == 1
    assert "Something went wrong" in summary.errors[0]


def test_mirror_summary_properties() -> None:
    """Test mirror summary computed properties."""
    summary = MirrorSummary()
    repo = Repository(
        name="test",
        full_name="owner/test",
        owner="owner",
        ssh_url="git@github.com:owner/test.git",
        clone_url="https://github.com/owner/test.git",
        default_branch="main",
    )

    summary.add_result(MirrorResult(repo=repo, success=True, action="cloned"))
    summary.add_result(MirrorResult(repo=repo, success=True, action="updated"))
    summary.add_result(MirrorResult(repo=repo, success=True, action="skipped"))
    summary.add_result(MirrorResult(repo=repo, success=False, action="failed", error="Error"))

    assert summary.success_count == 3
    assert summary.has_failures is True


def test_visibility_enum() -> None:
    """Test visibility enum values."""
    assert Visibility.PUBLIC.value == "public"
    assert Visibility.PRIVATE.value == "private"
    assert Visibility.ALL.value == "all"


def test_target_type_enum() -> None:
    """Test target type enum values."""
    assert TargetType.USER.value == "user"
    assert TargetType.ORG.value == "org"
