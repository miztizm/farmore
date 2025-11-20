"""
Tests for search command with flat structure option.

"Flat is better than nested. Unless you're organizing files." — schema.cx
"""

from dataclasses import replace

import pytest

from farmore.models import Repository


def test_flat_structure_no_duplicates() -> None:
    """Test flat structure with no duplicate repository names."""
    repos = [
        Repository(
            name="repo1",
            full_name="owner1/repo1",
            owner="owner1",
            ssh_url="git@github.com:owner1/repo1.git",
            clone_url="https://github.com/owner1/repo1.git",
            default_branch="main",
        ),
        Repository(
            name="repo2",
            full_name="owner2/repo2",
            owner="owner2",
            ssh_url="git@github.com:owner2/repo2.git",
            clone_url="https://github.com/owner2/repo2.git",
            default_branch="main",
        ),
        Repository(
            name="repo3",
            full_name="owner3/repo3",
            owner="owner3",
            ssh_url="git@github.com:owner3/repo3.git",
            clone_url="https://github.com/owner3/repo3.git",
            default_branch="main",
        ),
    ]

    # Simulate flat structure transformation
    repo_names = [repo.name for repo in repos]
    duplicates = [name for name in repo_names if repo_names.count(name) > 1]

    modified_repos = []
    for repo in repos:
        if repo.name in duplicates:
            modified_name = f"{repo.name}-{repo.owner}"
        else:
            modified_name = repo.name

        modified_repo = replace(repo, name=modified_name, owner="")
        modified_repos.append(modified_repo)

    # Verify no duplicates and owner is empty
    assert len(modified_repos) == 3
    assert all(repo.owner == "" for repo in modified_repos)
    assert modified_repos[0].name == "repo1"
    assert modified_repos[1].name == "repo2"
    assert modified_repos[2].name == "repo3"


def test_flat_structure_with_duplicates() -> None:
    """Test flat structure with duplicate repository names."""
    repos = [
        Repository(
            name="awesome",
            full_name="owner1/awesome",
            owner="owner1",
            ssh_url="git@github.com:owner1/awesome.git",
            clone_url="https://github.com/owner1/awesome.git",
            default_branch="main",
        ),
        Repository(
            name="awesome",
            full_name="owner2/awesome",
            owner="owner2",
            ssh_url="git@github.com:owner2/awesome.git",
            clone_url="https://github.com/owner2/awesome.git",
            default_branch="main",
        ),
        Repository(
            name="unique",
            full_name="owner3/unique",
            owner="owner3",
            ssh_url="git@github.com:owner3/unique.git",
            clone_url="https://github.com/owner3/unique.git",
            default_branch="main",
        ),
    ]

    # Simulate flat structure transformation
    repo_names = [repo.name for repo in repos]
    duplicates = [name for name in repo_names if repo_names.count(name) > 1]

    modified_repos = []
    for repo in repos:
        if repo.name in duplicates:
            modified_name = f"{repo.name}-{repo.owner}"
        else:
            modified_name = repo.name

        modified_repo = replace(repo, name=modified_name, owner="")
        modified_repos.append(modified_repo)

    # Verify duplicates are renamed with owner suffix
    assert len(modified_repos) == 3
    assert all(repo.owner == "" for repo in modified_repos)
    assert modified_repos[0].name == "awesome-owner1"
    assert modified_repos[1].name == "awesome-owner2"
    assert modified_repos[2].name == "unique"


def test_flat_structure_local_path() -> None:
    """Test that flat structure produces correct local paths."""
    repo = Repository(
        name="myrepo",
        full_name="owner/myrepo",
        owner="",  # Empty owner for flat structure
        ssh_url="git@github.com:owner/myrepo.git",
        clone_url="https://github.com/owner/myrepo.git",
        default_branch="main",
    )

    # With empty owner, local_path should be just the repo name
    assert repo.local_path == "/myrepo"


def test_flat_structure_multiple_duplicates() -> None:
    """Test flat structure with multiple sets of duplicate names."""
    repos = [
        Repository(
            name="cli",
            full_name="user1/cli",
            owner="user1",
            ssh_url="git@github.com:user1/cli.git",
            clone_url="https://github.com/user1/cli.git",
            default_branch="main",
        ),
        Repository(
            name="cli",
            full_name="user2/cli",
            owner="user2",
            ssh_url="git@github.com:user2/cli.git",
            clone_url="https://github.com/user2/cli.git",
            default_branch="main",
        ),
        Repository(
            name="api",
            full_name="org1/api",
            owner="org1",
            ssh_url="git@github.com:org1/api.git",
            clone_url="https://github.com/org1/api.git",
            default_branch="main",
        ),
    ]

    # Simulate flat structure transformation
    repo_names = [repo.name for repo in repos]
    duplicates = [name for name in repo_names if repo_names.count(name) > 1]

    modified_repos = []
    for repo in repos:
        if repo.name in duplicates:
            modified_name = f"{repo.name}-{repo.owner}"
        else:
            modified_name = repo.name

        modified_repo = replace(repo, name=modified_name, owner="")
        modified_repos.append(modified_repo)

    # Verify all duplicates are handled
    assert modified_repos[0].name == "cli-user1"
    assert modified_repos[1].name == "cli-user2"
    assert modified_repos[2].name == "api"
    assert all(repo.owner == "" for repo in modified_repos)

