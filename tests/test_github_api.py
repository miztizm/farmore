"""
Tests for GitHub API client.

"Mock the API. Trust nothing. Test everything." — schema.cx
"""

from pathlib import Path

import pytest
import responses

from farmore.github_api import GitHubAPIClient, GitHubAPIError
from farmore.models import Config, TargetType, Visibility


@pytest.fixture
def user_config() -> Config:
    """Create a test config for a user."""
    return Config(
        target_type=TargetType.USER,
        target_name="testuser",
        dest=Path("/tmp/backups"),
        token="test_token",
    )


@pytest.fixture
def org_config() -> Config:
    """Create a test config for an organization."""
    return Config(
        target_type=TargetType.ORG,
        target_name="testorg",
        dest=Path("/tmp/backups"),
        token="test_token",
    )


@responses.activate
def test_get_repositories_user(user_config: Config) -> None:
    """Test fetching repositories for a user."""
    # Mock API response
    responses.add(
        responses.GET,
        "https://api.github.com/users/testuser/repos",
        json=[
            {
                "name": "repo1",
                "full_name": "testuser/repo1",
                "owner": {"login": "testuser"},
                "ssh_url": "git@github.com:testuser/repo1.git",
                "clone_url": "https://github.com/testuser/repo1.git",
                "default_branch": "main",
                "private": False,
                "fork": False,
                "archived": False,
            }
        ],
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.get_repositories()

    assert len(repos) == 1
    assert repos[0].name == "repo1"
    assert repos[0].owner == "testuser"


@responses.activate
def test_get_repositories_org(org_config: Config) -> None:
    """Test fetching repositories for an organization."""
    responses.add(
        responses.GET,
        "https://api.github.com/orgs/testorg/repos",
        json=[
            {
                "name": "org-repo",
                "full_name": "testorg/org-repo",
                "owner": {"login": "testorg"},
                "ssh_url": "git@github.com:testorg/org-repo.git",
                "clone_url": "https://github.com/testorg/org-repo.git",
                "default_branch": "main",
                "private": True,
                "fork": False,
                "archived": False,
            }
        ],
        status=200,
    )

    client = GitHubAPIClient(org_config)
    repos = client.get_repositories()

    assert len(repos) == 1
    assert repos[0].name == "org-repo"
    assert repos[0].private is True


@responses.activate
def test_pagination(user_config: Config) -> None:
    """Test pagination handling."""
    # First page
    responses.add(
        responses.GET,
        "https://api.github.com/users/testuser/repos",
        json=[
            {
                "name": f"repo{i}",
                "full_name": f"testuser/repo{i}",
                "owner": {"login": "testuser"},
                "ssh_url": f"git@github.com:testuser/repo{i}.git",
                "clone_url": f"https://github.com/testuser/repo{i}.git",
                "default_branch": "main",
                "private": False,
                "fork": False,
                "archived": False,
            }
            for i in range(1, 3)
        ],
        status=200,
        headers={"Link": '<https://api.github.com/users/testuser/repos?page=2>; rel="next"'},
    )

    # Second page
    responses.add(
        responses.GET,
        "https://api.github.com/users/testuser/repos?page=2",
        json=[
            {
                "name": "repo3",
                "full_name": "testuser/repo3",
                "owner": {"login": "testuser"},
                "ssh_url": "git@github.com:testuser/repo3.git",
                "clone_url": "https://github.com/testuser/repo3.git",
                "default_branch": "main",
                "private": False,
                "fork": False,
                "archived": False,
            }
        ],
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.get_repositories()

    assert len(repos) == 3


@responses.activate
def test_filter_visibility_public(user_config: Config) -> None:
    """Test filtering by public visibility."""
    user_config.visibility = Visibility.PUBLIC

    responses.add(
        responses.GET,
        "https://api.github.com/users/testuser/repos",
        json=[
            {
                "name": "public-repo",
                "full_name": "testuser/public-repo",
                "owner": {"login": "testuser"},
                "ssh_url": "git@github.com:testuser/public-repo.git",
                "clone_url": "https://github.com/testuser/public-repo.git",
                "default_branch": "main",
                "private": False,
                "fork": False,
                "archived": False,
            },
            {
                "name": "private-repo",
                "full_name": "testuser/private-repo",
                "owner": {"login": "testuser"},
                "ssh_url": "git@github.com:testuser/private-repo.git",
                "clone_url": "https://github.com/testuser/private-repo.git",
                "default_branch": "main",
                "private": True,
                "fork": False,
                "archived": False,
            },
        ],
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.get_repositories()

    assert len(repos) == 1
    assert repos[0].name == "public-repo"


@responses.activate
def test_filter_forks(user_config: Config) -> None:
    """Test filtering out forks."""
    user_config.include_forks = False

    responses.add(
        responses.GET,
        "https://api.github.com/users/testuser/repos",
        json=[
            {
                "name": "original",
                "full_name": "testuser/original",
                "owner": {"login": "testuser"},
                "ssh_url": "git@github.com:testuser/original.git",
                "clone_url": "https://github.com/testuser/original.git",
                "default_branch": "main",
                "private": False,
                "fork": False,
                "archived": False,
            },
            {
                "name": "forked",
                "full_name": "testuser/forked",
                "owner": {"login": "testuser"},
                "ssh_url": "git@github.com:testuser/forked.git",
                "clone_url": "https://github.com/testuser/forked.git",
                "default_branch": "main",
                "private": False,
                "fork": True,
                "archived": False,
            },
        ],
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.get_repositories()

    assert len(repos) == 1
    assert repos[0].name == "original"


@responses.activate
def test_api_error_404(user_config: Config) -> None:
    """Test handling of 404 error."""
    responses.add(
        responses.GET,
        "https://api.github.com/users/testuser/repos",
        json={"message": "Not Found"},
        status=404,
    )

    client = GitHubAPIClient(user_config)

    with pytest.raises(GitHubAPIError, match="not found"):
        client.get_repositories()


@responses.activate
def test_api_error_rate_limit(user_config: Config) -> None:
    """Test handling of rate limit error."""
    responses.add(
        responses.GET,
        "https://api.github.com/users/testuser/repos",
        json={"message": "API rate limit exceeded"},
        status=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"},
    )

    client = GitHubAPIClient(user_config)

    with pytest.raises(GitHubAPIError, match="rate limit"):
        client.get_repositories()


# ============================================================================
# Search Repositories Tests
# ============================================================================


@responses.activate
def test_search_repositories_basic(user_config: Config) -> None:
    """Test basic repository search."""
    # Mock search API response
    responses.add(
        responses.GET,
        "https://api.github.com/search/repositories",
        json={
            "total_count": 2,
            "items": [
                {
                    "name": "test-repo-1",
                    "full_name": "owner1/test-repo-1",
                    "owner": {"login": "owner1", "type": "User"},
                    "ssh_url": "git@github.com:owner1/test-repo-1.git",
                    "clone_url": "https://github.com/owner1/test-repo-1.git",
                    "default_branch": "main",
                    "private": False,
                    "fork": False,
                    "archived": False,
                },
                {
                    "name": "test-repo-2",
                    "full_name": "owner2/test-repo-2",
                    "owner": {"login": "owner2", "type": "User"},
                    "ssh_url": "git@github.com:owner2/test-repo-2.git",
                    "clone_url": "https://github.com/owner2/test-repo-2.git",
                    "default_branch": "master",
                    "private": False,
                    "fork": False,
                    "archived": False,
                },
            ],
        },
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.search_repositories(query="test", limit=10)

    assert len(repos) == 2
    assert repos[0].name == "test-repo-1"
    assert repos[0].owner == "owner1"
    assert repos[1].name == "test-repo-2"
    assert repos[1].owner == "owner2"


@responses.activate
def test_search_repositories_with_language_filter(user_config: Config) -> None:
    """Test repository search with language filter."""
    responses.add(
        responses.GET,
        "https://api.github.com/search/repositories",
        json={
            "total_count": 1,
            "items": [
                {
                    "name": "python-repo",
                    "full_name": "owner/python-repo",
                    "owner": {"login": "owner", "type": "User"},
                    "ssh_url": "git@github.com:owner/python-repo.git",
                    "clone_url": "https://github.com/owner/python-repo.git",
                    "default_branch": "main",
                    "private": False,
                    "fork": False,
                    "archived": False,
                },
            ],
        },
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.search_repositories(query="test", language="python", limit=10)

    assert len(repos) == 1
    assert repos[0].name == "python-repo"


@responses.activate
def test_search_repositories_with_min_stars(user_config: Config) -> None:
    """Test repository search with minimum stars filter."""
    responses.add(
        responses.GET,
        "https://api.github.com/search/repositories",
        json={
            "total_count": 1,
            "items": [
                {
                    "name": "popular-repo",
                    "full_name": "owner/popular-repo",
                    "owner": {"login": "owner", "type": "User"},
                    "ssh_url": "git@github.com:owner/popular-repo.git",
                    "clone_url": "https://github.com/owner/popular-repo.git",
                    "default_branch": "main",
                    "private": False,
                    "fork": False,
                    "archived": False,
                },
            ],
        },
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.search_repositories(query="test", min_stars=1000, limit=10)

    assert len(repos) == 1
    assert repos[0].name == "popular-repo"


@responses.activate
def test_search_repositories_with_sorting(user_config: Config) -> None:
    """Test repository search with sorting options."""
    responses.add(
        responses.GET,
        "https://api.github.com/search/repositories",
        json={
            "total_count": 2,
            "items": [
                {
                    "name": "repo-1",
                    "full_name": "owner/repo-1",
                    "owner": {"login": "owner", "type": "User"},
                    "ssh_url": "git@github.com:owner/repo-1.git",
                    "clone_url": "https://github.com/owner/repo-1.git",
                    "default_branch": "main",
                    "private": False,
                    "fork": False,
                    "archived": False,
                },
                {
                    "name": "repo-2",
                    "full_name": "owner/repo-2",
                    "owner": {"login": "owner", "type": "User"},
                    "ssh_url": "git@github.com:owner/repo-2.git",
                    "clone_url": "https://github.com/owner/repo-2.git",
                    "default_branch": "main",
                    "private": False,
                    "fork": False,
                    "archived": False,
                },
            ],
        },
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.search_repositories(query="test", sort="stars", order="desc", limit=10)

    assert len(repos) == 2


@responses.activate
def test_search_repositories_empty_results(user_config: Config) -> None:
    """Test repository search with no results."""
    responses.add(
        responses.GET,
        "https://api.github.com/search/repositories",
        json={"total_count": 0, "items": []},
        status=200,
    )

    client = GitHubAPIClient(user_config)
    repos = client.search_repositories(query="nonexistent-keyword-xyz", limit=10)

    assert len(repos) == 0


@responses.activate
def test_search_repositories_limit_validation(user_config: Config) -> None:
    """Test that search validates limit parameter."""
    client = GitHubAPIClient(user_config)

    # Test limit too low
    with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
        client.search_repositories(query="test", limit=0)

    # Test limit too high
    with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
        client.search_repositories(query="test", limit=101)


@responses.activate
def test_search_repositories_invalid_query(user_config: Config) -> None:
    """Test handling of invalid search query."""
    responses.add(
        responses.GET,
        "https://api.github.com/search/repositories",
        json={"message": "Validation Failed"},
        status=422,
    )

    client = GitHubAPIClient(user_config)

    with pytest.raises(GitHubAPIError, match="Invalid search query"):
        client.search_repositories(query="invalid:::query", limit=10)


@responses.activate
def test_search_repositories_api_error(user_config: Config) -> None:
    """Test handling of API errors during search."""
    responses.add(
        responses.GET,
        "https://api.github.com/search/repositories",
        json={"message": "Internal Server Error"},
        status=500,
    )

    client = GitHubAPIClient(user_config)

    with pytest.raises(GitHubAPIError, match="Search failed"):
        client.search_repositories(query="test", limit=10)
