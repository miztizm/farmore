"""
GitHub API client with pagination support.

"The API is just a door. Your token is the key. Don't lose it." — schema.cx
"""

import re
import time
from datetime import datetime
from functools import wraps
from typing import Callable, TypeVar

import requests

from .models import (
    Config,
    Discussion,
    Follower,
    Issue,
    Label,
    Milestone,
    Project,
    PullRequest,
    Release,
    ReleaseAsset,
    Repository,
    RepositorySecret,
    TargetType,
    UserProfile,
    Visibility,
    Webhook,
    Workflow,
    WorkflowRun,
)
from .rich_utils import console, print_panel, print_warning


class GitHubAPIError(Exception):
    """GitHub API error."""

    pass


class RateLimitError(GitHubAPIError):
    """Rate limit exceeded error."""

    pass


# Type variable for retry decorator
T = TypeVar("T")


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 5.0,
    backoff: float = 2.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to retry on transient API failures.

    "Persistence is the difference between a bug and a feature." — schema.cx

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay on each retry (exponential backoff)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error: Exception | None = None
            current_delay = delay

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.ChunkedEncodingError,
                ) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        console.print(
                            f"[yellow]⏳ Request failed ({type(e).__name__}), "
                            f"retrying in {current_delay:.1f}s... "
                            f"(attempt {attempt + 2}/{max_retries})[/yellow]"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                except requests.exceptions.HTTPError as e:
                    # Retry on server errors (502, 503, 504)
                    if e.response is not None and e.response.status_code in (502, 503, 504):
                        last_error = e
                        if attempt < max_retries - 1:
                            console.print(
                                f"[yellow]⏳ Server error ({e.response.status_code}), "
                                f"retrying in {current_delay:.1f}s...[/yellow]"
                            )
                            time.sleep(current_delay)
                            current_delay *= backoff
                    else:
                        raise

            if last_error:
                raise last_error
            raise RuntimeError("Unexpected state in retry decorator")

        return wrapper

    return decorator


class GitHubAPIClient:
    """
    GitHub REST API v3 client.

    "They track everything. Might as well use their API." — schema.cx
    """

    PER_PAGE = 100  # Maximum allowed by GitHub

    def __init__(self, config: Config) -> None:
        """Initialize the GitHub API client."""
        self.config = config
        self.session = requests.Session()

        # Support GitHub Enterprise with custom hostname
        if config.github_host:
            self.BASE_URL = f"https://{config.github_host}/api/v3"
            console.print(f"[cyan]🏢 Using GitHub Enterprise: {config.github_host}[/cyan]")
        else:
            self.BASE_URL = "https://api.github.com"

        # Set up authentication headers
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Farmore/0.6.0 (https://github.com/miztizm/farmore)",
        }

        if config.token:
            headers["Authorization"] = f"token {config.token}"

        self.session.headers.update(headers)

        # Cache authenticated username for filtering
        self._authenticated_username: str | None = None

    def __enter__(self) -> "GitHubAPIClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close session."""
        self.close()

    def close(self) -> None:
        """Close the HTTP session and release resources."""
        if self.session:
            self.session.close()

    def __del__(self) -> None:
        """Cleanup when object is garbage collected."""
        try:
            self.close()
        except Exception:
            # Silently ignore errors during cleanup
            pass

    def _get_authenticated_user(self) -> str | None:
        """
        Get the username of the authenticated user.

        Returns None if not authenticated or if the request fails.
        """
        if not self.config.token:
            return None

        try:
            response = self.session.get(f"{self.BASE_URL}/user")
            response.raise_for_status()
            return response.json().get("login")
        except Exception:
            return None

    def get_repository(self, owner: str, repo: str) -> Repository | None:
        """
        Get a single repository by owner and name.

        "One repo to rule them all. Or at least to back up." — schema.cx

        Args:
            owner: Repository owner (user or organization)
            repo: Repository name

        Returns:
            Repository object or None if not found
        """
        endpoint = f"/repos/{owner}/{repo}"
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = self._make_request(url)
            data = response.json()

            return Repository(
                name=data["name"],
                full_name=data["full_name"],
                owner=data["owner"]["login"],
                ssh_url=data["ssh_url"],
                clone_url=data["clone_url"],
                default_branch=data.get("default_branch", "main"),
                private=data["private"],
                fork=data["fork"],
                archived=data["archived"],
                owner_type=data["owner"]["type"],
            )
        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                return None
            raise

    def get_repositories(self) -> list[Repository]:
        """
        Fetch all repositories for the configured target.

        "Pagination is just recursion with extra steps." — schema.cx
        """
        if self.config.target_type == TargetType.USER:
            # Check if we're querying the authenticated user's own repos
            authenticated_user = self._get_authenticated_user()
            # Cache for filtering later
            self._authenticated_username = authenticated_user

            if authenticated_user and authenticated_user.lower() == self.config.target_name.lower():
                # Use /user/repos endpoint for authenticated user's own repos
                # This endpoint returns both public AND private repos
                endpoint = "/user/repos"
                params = {"type": "all"}
                console.print(f"\n[cyan]🔍 Fetching YOUR repositories (authenticated as {authenticated_user})[/cyan]")
                console.print(f"   [dim]Using /user/repos endpoint for public + private access[/dim]")
            else:
                # Use /users/{username}/repos for other users (public only)
                endpoint = f"/users/{self.config.target_name}/repos"
                params = {"type": "all"}
                if authenticated_user:
                    console.print(f"\n[cyan]🔍 Fetching repositories for user '{self.config.target_name}' (you are {authenticated_user})[/cyan]")
                    print_warning("Can only access PUBLIC repos for other users", prefix="⚠️")
                else:
                    console.print(f"\n[cyan]🔍 Fetching repositories without authentication (public only)[/cyan]")
        else:  # ORG
            endpoint = f"/orgs/{self.config.target_name}/repos"
            # Add type=all parameter to get all org repos (public + private)
            params = {"type": "all"}
            console.print(f"\n[cyan]🔍 Fetching repositories for organization '{self.config.target_name}'[/cyan]")

        repos: list[Repository] = []
        url: str | None = f"{self.BASE_URL}{endpoint}"

        while url:
            response = self._make_request(url, initial_params=params if url == f"{self.BASE_URL}{endpoint}" else None)

            # Display rate limit info on first request
            if not repos:
                self._display_rate_limit_info(response)

            page_repos = self._parse_repositories(response.json())

            # Debug: Show how many repos we got and their visibility
            public_count = sum(1 for r in page_repos if not r.private)
            private_count = sum(1 for r in page_repos if r.private)
            console.print(f"   [dim]📦 Page: {len(page_repos)} repos ({public_count} public, {private_count} private)[/dim]")

            repos.extend(page_repos)

            # Get next page URL from Link header
            url = self._get_next_page_url(response)

        # Apply filters
        return self._filter_repositories(repos)

    def _make_request(self, url: str, retry_count: int = 0, initial_params: dict | None = None) -> requests.Response:
        """
        Make an API request with error handling and retry logic.

        "Persistence is key. Even when the API says no." — schema.cx
        """
        # Only add params if URL doesn't already have query parameters
        if "?" in url:
            params = {}
        else:
            params = {"per_page": self.PER_PAGE}
            # Merge in any initial params (like type=all)
            if initial_params:
                params.update(initial_params)
        max_retries = 3

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise GitHubAPIError(
                    f"Target '{self.config.target_name}' not found. "
                    f"Check the {self.config.target_type.value} name."
                ) from e
            elif e.response.status_code == 403:
                # Check if it's a rate limit issue
                if "X-RateLimit-Remaining" in e.response.headers:
                    remaining = e.response.headers.get("X-RateLimit-Remaining", "0")
                    reset_timestamp = e.response.headers.get("X-RateLimit-Reset", "0")

                    # Format reset time
                    try:
                        reset_dt = datetime.fromtimestamp(int(reset_timestamp))
                        reset_str = reset_dt.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, OSError):
                        reset_str = "unknown"

                    # Get rate limit type
                    auth_status = "authenticated" if self.config.token else "unauthenticated"
                    limit_info = (
                        f"\n\n📊 Rate Limit Information:"
                        f"\n  • Status: {auth_status}"
                        f"\n  • Remaining requests: {remaining}"
                        f"\n  • Limit resets at: {reset_str}"
                        f"\n\n💡 Rate Limits:"
                        f"\n  • Unauthenticated: 60 requests/hour"
                        f"\n  • Authenticated: 5,000 requests/hour"
                    )

                    if not self.config.token:
                        limit_info += (
                            "\n\n🔑 To increase your rate limit:"
                            "\n  1. Create a Personal Access Token at:"
                            "\n     https://github.com/settings/tokens"
                            "\n  2. Set it as an environment variable:"
                            "\n     export GITHUB_TOKEN=your_token_here"
                            "\n  3. Or use the --token flag"
                        )

                    # Retry with exponential backoff if we have retries left
                    if retry_count < max_retries:
                        wait_time = 2**retry_count  # Exponential backoff: 1s, 2s, 4s
                        console.print(
                            f"\n[yellow]⏳ Rate limit hit. Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{max_retries})[/yellow]"
                        )
                        time.sleep(wait_time)
                        return self._make_request(url, retry_count + 1, initial_params)

                    raise RateLimitError(f"GitHub API rate limit exceeded.{limit_info}") from e
                raise GitHubAPIError(f"Access forbidden: {e}") from e
            elif e.response.status_code == 401:
                raise GitHubAPIError("Authentication failed. Check your GITHUB_TOKEN.") from e
            else:
                raise GitHubAPIError(f"GitHub API error: {e}") from e
        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"Network error: {e}") from e

    def _display_rate_limit_info(self, response: requests.Response) -> None:
        """
        Display rate limit information from response headers.

        "Knowledge is power. Knowing your limits is wisdom." — schema.cx
        """
        limit = response.headers.get("X-RateLimit-Limit", "unknown")
        remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
        reset_timestamp = response.headers.get("X-RateLimit-Reset", "0")

        try:
            reset_dt = datetime.fromtimestamp(int(reset_timestamp))
            reset_str = reset_dt.strftime("%H:%M:%S")
        except (ValueError, OSError):
            reset_str = "unknown"

        auth_status = "[green]✓ Authenticated[/green]" if self.config.token else "[yellow]⚠ Unauthenticated[/yellow]"

        # Create rate limit info panel
        info_text = f"Status: {auth_status}\n"
        info_text += f"Limit: [cyan]{limit}[/cyan]/hour | Remaining: [cyan]{remaining}[/cyan] | Resets at: [cyan]{reset_str}[/cyan]"

        if not self.config.token:
            info_text += "\n\n[dim]💡 Tip: Use GITHUB_TOKEN for 5,000 requests/hour (vs 60 unauthenticated)[/dim]"

        print_panel(info_text, title="📊 GitHub API Rate Limit", style="cyan")

    def _get_next_page_url(self, response: requests.Response) -> str | None:
        """
        Extract next page URL from Link header.

        "Following links is how you find the truth. Or more repos." — schema.cx
        """
        link_header = response.headers.get("Link")
        if not link_header:
            return None

        # Parse Link header: <url>; rel="next", <url>; rel="last"
        links = {}
        for link in link_header.split(","):
            match = re.match(r'<([^>]+)>;\s*rel="([^"]+)"', link.strip())
            if match:
                url, rel = match.groups()
                links[rel] = url

        return links.get("next")

    def _parse_repositories(self, data: list[dict]) -> list[Repository]:
        """Parse repository data from API response."""
        repos = []
        for item in data:
            repo = Repository(
                name=item["name"],
                full_name=item["full_name"],
                owner=item["owner"]["login"],
                ssh_url=item["ssh_url"],
                clone_url=item["clone_url"],
                default_branch=item.get("default_branch", "main"),
                private=item.get("private", False),
                fork=item.get("fork", False),
                archived=item.get("archived", False),
                owner_type=item["owner"].get("type", "User"),
            )
            repos.append(repo)
        return repos

    def _filter_repositories(self, repos: list[Repository]) -> list[Repository]:
        """
        Apply configured filters to repository list.

        "Filters are just organized prejudice. But useful." — schema.cx
        """
        initial_count = len(repos)
        filtered = repos

        # Filter by visibility
        if self.config.visibility != Visibility.ALL:
            before = len(filtered)
            if self.config.visibility == Visibility.PUBLIC:
                filtered = [r for r in filtered if not r.private]
            elif self.config.visibility == Visibility.PRIVATE:
                filtered = [r for r in filtered if r.private]
            if len(filtered) < before:
                console.print(f"   [dim]🔍 Filtered by visibility: {before} → {len(filtered)}[/dim]")

        # Filter forks
        if not self.config.include_forks:
            before = len(filtered)
            forks = [r for r in filtered if r.fork]
            filtered = [r for r in filtered if not r.fork]
            if len(forks) > 0:
                console.print(f"   [dim]🔍 Filtered out {len(forks)} forks (use --include-forks to include them)[/dim]")

        # Filter archived
        if not self.config.include_archived:
            before = len(filtered)
            archived = [r for r in filtered if r.archived]
            filtered = [r for r in filtered if not r.archived]
            if len(archived) > 0:
                console.print(f"   [dim]🔍 Filtered out {len(archived)} archived repos (use --include-archived to include them)[/dim]")

        # Filter organization repositories
        if self.config.exclude_org_repos and self._authenticated_username:
            before = len(filtered)
            # Keep only repos where owner matches authenticated user
            org_repos = [r for r in filtered if r.owner.lower() != self._authenticated_username.lower()]
            filtered = [r for r in filtered if r.owner.lower() == self._authenticated_username.lower()]
            if len(org_repos) > 0:
                console.print(f"   [dim]🔍 Filtered out {len(org_repos)} organization repos (remove --exclude-orgs to include them)[/dim]")

        # Filter excluded repositories by name
        if self.config.exclude_repos:
            before = len(filtered)
            excluded = [r for r in filtered if r.name in self.config.exclude_repos]
            filtered = [r for r in filtered if r.name not in self.config.exclude_repos]
            if len(excluded) > 0:
                excluded_names = ", ".join(r.name for r in excluded)
                console.print(f"   [dim]🔍 Excluded {len(excluded)} repos by name: {excluded_names}[/dim]")

        # Filter by name regex pattern
        if self.config.name_regex:
            before = len(filtered)
            try:
                pattern = re.compile(self.config.name_regex)
                matched = [r for r in filtered if pattern.search(r.name)]
                excluded_count = len(filtered) - len(matched)
                filtered = matched
                if excluded_count > 0:
                    console.print(f"   [dim]🔍 Name regex '{self.config.name_regex}' matched {len(filtered)}/{before} repos[/dim]")
            except re.error as e:
                print_warning(f"Invalid regex pattern '{self.config.name_regex}': {e}", prefix="⚠️")

        if len(filtered) < initial_count:
            console.print(f"   [cyan]📊 Total after filtering: {initial_count} → {len(filtered)} repositories[/cyan]")

        return filtered

    def search_repositories(
        self,
        query: str,
        language: str | None = None,
        min_stars: int | None = None,
        sort: str = "best-match",
        order: str = "desc",
        limit: int = 10,
    ) -> list[Repository]:
        """
        Search for repositories on GitHub using the Search API.

        "Search is just organized guessing. But with better results." — schema.cx

        Args:
            query: Search query string (e.g., "smsbomber", "machine learning")
            language: Filter by programming language (e.g., "python", "javascript")
            min_stars: Minimum number of stars required
            sort: Sort order - "stars", "forks", "updated", or "best-match" (default)
            order: Sort direction - "asc" or "desc" (default)
            limit: Maximum number of repositories to return (1-100)

        Returns:
            List of Repository objects matching the search criteria

        Raises:
            GitHubAPIError: If the API request fails
            ValueError: If limit is out of range (1-100)
        """
        # Validate limit
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")

        # Build search query with qualifiers
        search_query = query.strip()

        if language:
            search_query += f" language:{language}"

        if min_stars is not None:
            search_query += f" stars:>={min_stars}"

        # Prepare API request
        endpoint = "/search/repositories"
        url = f"{self.BASE_URL}{endpoint}"

        # Map "best-match" to empty string (GitHub's default)
        api_sort = "" if sort == "best-match" else sort

        params = {
            "q": search_query,
            "per_page": min(limit, 100),  # GitHub max is 100 per page
            "page": 1,
        }

        if api_sort:
            params["sort"] = api_sort
            params["order"] = order

        console.print(f"\n[cyan]🔍 Searching GitHub repositories...[/cyan]")
        console.print(f"   [dim]Query: {search_query}[/dim]")
        console.print(f"   [dim]Sort: {sort} ({order})[/dim]")
        console.print(f"   [dim]Limit: {limit} repositories[/dim]")

        try:
            response = self._make_request(url, initial_params=params)

            # Display rate limit info
            self._display_rate_limit_info(response)

            data = response.json()

            # Check if we got results
            total_count = data.get("total_count", 0)
            items = data.get("items", [])

            if total_count == 0:
                console.print(f"\n[yellow]ℹ️  No repositories found matching your query[/yellow]")
                return []

            console.print(f"\n[cyan]📊 Found {total_count:,} total results (showing {len(items)})[/cyan]")

            # Parse repositories from search results
            repos = []
            for item in items:
                repo = Repository(
                    name=item["name"],
                    full_name=item["full_name"],
                    owner=item["owner"]["login"],
                    ssh_url=item["ssh_url"],
                    clone_url=item["clone_url"],
                    default_branch=item.get("default_branch", "main"),
                    private=item.get("private", False),
                    fork=item.get("fork", False),
                    archived=item.get("archived", False),
                    owner_type=item["owner"].get("type", "User"),
                )
                repos.append(repo)

            return repos

        except GitHubAPIError as e:
            # Re-raise with more specific error messages for search
            error_msg = str(e)
            if "422" in error_msg or "Unprocessable" in error_msg:
                raise GitHubAPIError(
                    f"Invalid search query: {search_query}. "
                    "Check GitHub's search syntax: https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories"
                ) from e
            elif "500" in error_msg or "Server Error" in error_msg:
                raise GitHubAPIError(f"Search failed: GitHub API returned a server error") from e
            else:
                # Re-raise the original error
                raise

    def get_user_profile(self, username: str | None = None) -> UserProfile:
        """
        Fetch user profile information.

        If username is None, fetches the authenticated user's profile.
        "Identity is just metadata. But it's YOUR metadata." — schema.cx
        """
        if username:
            endpoint = f"/users/{username}"
            console.print(f"\n[cyan]👤 Fetching profile for user: {username}[/cyan]")
        else:
            endpoint = "/user"
            console.print(f"\n[cyan]👤 Fetching YOUR profile (authenticated user)[/cyan]")

        response = self._make_request(f"{self.BASE_URL}{endpoint}")
        data = response.json()

        return UserProfile(
            login=data["login"],
            name=data.get("name"),
            email=data.get("email"),
            bio=data.get("bio"),
            company=data.get("company"),
            location=data.get("location"),
            blog=data.get("blog"),
            twitter_username=data.get("twitter_username"),
            public_repos=data.get("public_repos", 0),
            public_gists=data.get("public_gists", 0),
            followers=data.get("followers", 0),
            following=data.get("following", 0),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            hireable=data.get("hireable"),
            avatar_url=data.get("avatar_url"),
            html_url=data.get("html_url"),
        )

    def get_starred_repositories(self, username: str | None = None) -> list[Repository]:
        """
        Fetch repositories starred by a user.

        If username is None, fetches the authenticated user's starred repos.
        "Stars are just bookmarks. But they tell a story." — schema.cx
        """
        if username:
            endpoint = f"/users/{username}/starred"
            console.print(f"\n[cyan]⭐ Fetching starred repositories for user: {username}[/cyan]")
        else:
            endpoint = "/user/starred"
            authenticated_user = self._get_authenticated_user()
            console.print(f"\n[cyan]⭐ Fetching YOUR starred repositories (authenticated as {authenticated_user})[/cyan]")

        all_repos = []
        next_url = f"{self.BASE_URL}{endpoint}"
        params = {"per_page": self.PER_PAGE}

        while next_url:
            response = self._make_request(next_url, initial_params=params if next_url == f"{self.BASE_URL}{endpoint}" else None)
            data = response.json()

            repos = self._parse_repositories(data)
            all_repos.extend(repos)

            next_url = self._get_next_page_url(response)
            params = None  # Only use params on first request

        console.print(f"   [green]✓ Found {len(all_repos)} starred repositories[/green]")
        return all_repos

    def get_watched_repositories(self, username: str | None = None) -> list[Repository]:
        """
        Fetch repositories watched by a user.

        If username is None, fetches the authenticated user's watched repos.
        "Watching is caring. Or stalking. Depends on perspective." — schema.cx
        """
        if username:
            endpoint = f"/users/{username}/subscriptions"
            console.print(f"\n[cyan]👁 Fetching watched repositories for user: {username}[/cyan]")
        else:
            endpoint = "/user/subscriptions"
            authenticated_user = self._get_authenticated_user()
            console.print(f"\n[cyan]👁 Fetching YOUR watched repositories (authenticated as {authenticated_user})[/cyan]")

        all_repos = []
        next_url = f"{self.BASE_URL}{endpoint}"
        params = {"per_page": self.PER_PAGE}

        while next_url:
            response = self._make_request(next_url, initial_params=params if next_url == f"{self.BASE_URL}{endpoint}" else None)
            data = response.json()

            repos = self._parse_repositories(data)
            all_repos.extend(repos)

            next_url = self._get_next_page_url(response)
            params = None  # Only use params on first request

        console.print(f"   [green]✓ Found {len(all_repos)} watched repositories[/green]")
        return all_repos

    def get_repository_secrets(self, owner: str, repo: str) -> list[RepositorySecret]:
        """
        Fetch repository secrets (names only, not values).

        "Secrets are meant to be kept. But their names? Those we can share." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/actions/secrets"
        console.print(f"\n[cyan]🔐 Fetching secrets for repository: {owner}/{repo}[/cyan]")
        print_warning("Note: GitHub API only returns secret names, not values", prefix="⚠️")

        try:
            response = self._make_request(f"{self.BASE_URL}{endpoint}")
            data = response.json()

            secrets = []
            for item in data.get("secrets", []):
                secret = RepositorySecret(
                    name=item["name"],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                )
                secrets.append(secret)

            console.print(f"   [green]✓ Found {len(secrets)} secrets[/green]")
            return secrets
        except GitHubAPIError as e:
            if "404" in str(e):
                print_warning("Repository not found or no access to secrets", prefix="⚠️")
                return []
            raise

    def delete_repository(self, owner: str, repo: str) -> bool:
        """
        Delete a repository.

        "Deletion is permanent. There's no undo button in the cloud." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}"
        console.print(f"\n[red]🗑️  Deleting repository: {owner}/{repo}[/red]")

        try:
            response = self.session.delete(f"{self.BASE_URL}{endpoint}")
            response.raise_for_status()
            console.print(f"   [green]✓ Repository deleted successfully[/green]")
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise GitHubAPIError(
                    f"Permission denied. Ensure your token has 'delete_repo' scope."
                ) from e
            elif e.response.status_code == 404:
                raise GitHubAPIError(f"Repository not found: {owner}/{repo}") from e
            else:
                raise GitHubAPIError(f"Failed to delete repository: {e}") from e
        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"Network error: {e}") from e

    def get_issues(
        self, owner: str, repo: str, state: str = "all", include_comments: bool = False
    ) -> list[Issue]:
        """
        Fetch all issues for a repository.

        "Issues are just TODOs that escaped into the wild." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/issues"
        console.print(f"\n[cyan]📋 Fetching issues for repository: {owner}/{repo}[/cyan]")
        console.print(f"   [dim]State filter: {state}[/dim]")

        all_issues = []
        params = {"state": state, "per_page": self.PER_PAGE, "page": 1}

        while True:
            response = self._make_request(f"{self.BASE_URL}{endpoint}", initial_params=params)
            data = response.json()

            if not data:
                break

            for item in data:
                # Skip pull requests (they appear in issues API but have 'pull_request' key)
                if "pull_request" in item:
                    continue

                try:
                    issue = Issue(
                        number=item["number"],
                        title=item["title"],
                        state=item["state"],
                        user=item["user"]["login"] if item.get("user") else "ghost",
                        body=item.get("body"),
                        labels=[label["name"] for label in item.get("labels", [])],
                        assignees=[assignee["login"] for assignee in item.get("assignees", [])],
                        created_at=item["created_at"],
                        updated_at=item["updated_at"],
                        closed_at=item.get("closed_at"),
                        comments_count=item.get("comments", 0),
                        html_url=item["html_url"],
                    )

                    # Optionally fetch comments
                    if include_comments and issue.comments_count > 0:
                        comments = self._get_issue_comments(owner, repo, issue.number)
                        issue.comments = comments

                    all_issues.append(issue)
                except Exception as e:
                    print_warning(f"Skipping issue #{item.get('number', '?')}: {e}", prefix="⚠️")
                    continue

            # Check for next page
            if "next" not in response.links:
                break

            params["page"] += 1

        console.print(f"   [green]✓ Found {len(all_issues)} issues[/green]")
        return all_issues

    def _get_issue_comments(self, owner: str, repo: str, issue_number: int) -> list[dict]:
        """Fetch comments for a specific issue."""
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        response = self._make_request(f"{self.BASE_URL}{endpoint}")
        data = response.json()

        return [
            {
                "user": comment["user"]["login"],
                "body": comment["body"],
                "created_at": comment["created_at"],
                "updated_at": comment["updated_at"],
            }
            for comment in data
        ]

    def get_pull_requests(
        self, owner: str, repo: str, state: str = "all", include_comments: bool = False
    ) -> list[PullRequest]:
        """
        Fetch all pull requests for a repository.

        "Pull requests: where code goes to be judged by its peers." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/pulls"
        console.print(f"\n[cyan]🔀 Fetching pull requests for repository: {owner}/{repo}[/cyan]")
        console.print(f"   [dim]State filter: {state}[/dim]")

        all_prs = []
        params = {"state": state, "per_page": self.PER_PAGE, "page": 1}

        while True:
            response = self._make_request(f"{self.BASE_URL}{endpoint}", initial_params=params)
            data = response.json()

            if not data:
                break

            for item in data:
                pr = PullRequest(
                    number=item["number"],
                    title=item["title"],
                    state=item["state"],
                    user=item["user"]["login"] if item.get("user") else "ghost",
                    body=item.get("body"),
                    labels=[label["name"] for label in item.get("labels", [])],
                    assignees=[assignee["login"] for assignee in item.get("assignees", [])],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    closed_at=item.get("closed_at"),
                    merged_at=item.get("merged_at"),
                    merged=item.get("merged", False),
                    draft=item.get("draft", False),
                    head_ref=item["head"]["ref"],
                    base_ref=item["base"]["ref"],
                    commits_count=item.get("commits", 0),
                    comments_count=item.get("comments", 0),
                    review_comments_count=item.get("review_comments", 0),
                    html_url=item["html_url"],
                    diff_url=item["diff_url"],
                    patch_url=item["patch_url"],
                )

                # Optionally fetch comments
                if include_comments and pr.comments_count > 0:
                    comments = self._get_pr_comments(owner, repo, pr.number)
                    pr.comments = comments

                all_prs.append(pr)

            # Check for next page
            if "next" not in response.links:
                break

            params["page"] += 1

        console.print(f"   [green]✓ Found {len(all_prs)} pull requests[/green]")
        return all_prs

    def _get_pr_comments(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Fetch comments for a specific pull request."""
        endpoint = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
        response = self._make_request(f"{self.BASE_URL}{endpoint}")
        data = response.json()

        return [
            {
                "user": comment["user"]["login"],
                "body": comment["body"],
                "created_at": comment["created_at"],
                "updated_at": comment["updated_at"],
            }
            for comment in data
        ]

    def get_workflows(self, owner: str, repo: str) -> tuple[list[Workflow], list[dict]]:
        """
        Fetch GitHub Actions workflows and their content.

        Returns tuple of (workflows metadata, workflow files content)

        "Automation is just laziness with a good PR." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/actions/workflows"
        console.print(f"\n[cyan]⚙️  Fetching GitHub Actions workflows for: {owner}/{repo}[/cyan]")

        try:
            response = self._make_request(f"{self.BASE_URL}{endpoint}")
            data = response.json()

            workflows = []
            workflow_files = []

            for item in data.get("workflows", []):
                workflow = Workflow(
                    name=item["name"],
                    path=item["path"],
                    state=item["state"],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    html_url=item["html_url"],
                    badge_url=item["badge_url"],
                )
                workflows.append(workflow)

                # Fetch workflow file content
                file_content = self._get_workflow_file(owner, repo, item["path"])
                if file_content:
                    workflow_files.append(
                        {"path": item["path"], "name": item["name"], "content": file_content}
                    )

            console.print(f"   [green]✓ Found {len(workflows)} workflows[/green]")
            return workflows, workflow_files

        except GitHubAPIError as e:
            if "404" in str(e):
                print_warning("No workflows found or repository not accessible", prefix="⚠️")
                return [], []
            raise

    def _get_workflow_file(self, owner: str, repo: str, path: str) -> str | None:
        """Fetch the content of a workflow file."""
        try:
            endpoint = f"/repos/{owner}/{repo}/contents/{path}"
            response = self._make_request(f"{self.BASE_URL}{endpoint}")
            data = response.json()

            # GitHub returns base64-encoded content
            import base64

            content = base64.b64decode(data["content"]).decode("utf-8")
            return content
        except Exception:
            return None

    def get_workflow_runs(
        self, owner: str, repo: str, limit: int = 100
    ) -> list[WorkflowRun]:
        """
        Fetch recent workflow runs for a repository.

        "Every run tells a story. Usually a story of failure." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/actions/runs"
        console.print(f"\n[cyan]📊 Fetching workflow runs for: {owner}/{repo} (limit: {limit})[/cyan]")

        try:
            response = self._make_request(
                f"{self.BASE_URL}{endpoint}", initial_params={"per_page": min(limit, 100)}
            )
            data = response.json()

            runs = []
            for item in data.get("workflow_runs", [])[:limit]:
                run = WorkflowRun(
                    id=item["id"],
                    name=item["name"],
                    status=item["status"],
                    conclusion=item.get("conclusion"),
                    workflow_name=item["name"],
                    event=item["event"],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    run_number=item["run_number"],
                    html_url=item["html_url"],
                )
                runs.append(run)

            console.print(f"   [green]✓ Found {len(runs)} workflow runs[/green]")
            return runs

        except GitHubAPIError as e:
            if "404" in str(e):
                print_warning("No workflow runs found", prefix="⚠️")
                return []
            raise

    def get_releases(self, owner: str, repo: str) -> list[Release]:
        """
        Fetch all releases for a repository.

        "Releases are just commits with marketing." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/releases"
        console.print(f"\n[cyan]🚀 Fetching releases for repository: {owner}/{repo}[/cyan]")

        all_releases = []
        params = {"per_page": self.PER_PAGE, "page": 1}

        try:
            while True:
                response = self._make_request(f"{self.BASE_URL}{endpoint}", initial_params=params)
                data = response.json()

                if not data:
                    break

                for item in data:
                    # Parse assets
                    assets = []
                    for asset in item.get("assets", []):
                        assets.append(
                            {
                                "id": asset["id"],
                                "name": asset["name"],
                                "label": asset.get("label"),
                                "content_type": asset["content_type"],
                                "size": asset["size"],
                                "download_count": asset["download_count"],
                                "created_at": asset["created_at"],
                                "updated_at": asset["updated_at"],
                                "browser_download_url": asset["browser_download_url"],
                            }
                        )

                    release = Release(
                        id=item["id"],
                        tag_name=item["tag_name"],
                        name=item.get("name"),
                        body=item.get("body"),
                        draft=item["draft"],
                        prerelease=item["prerelease"],
                        created_at=item["created_at"],
                        published_at=item.get("published_at"),
                        author=item["author"]["login"],
                        html_url=item["html_url"],
                        tarball_url=item["tarball_url"],
                        zipball_url=item["zipball_url"],
                        assets=assets,
                    )
                    all_releases.append(release)

                # Check for next page
                if "next" not in response.links:
                    break

                params["page"] += 1
                params = None

            console.print(f"   [green]✓ Found {len(all_releases)} releases[/green]")
            return all_releases

        except GitHubAPIError as e:
            if "404" in str(e):
                print_warning("No releases found or repository not accessible", prefix="⚠️")
                return []
            raise

    def check_wiki_exists(self, owner: str, repo: str) -> bool:
        """
        Check if a repository has a wiki enabled.

        "Wikis are where documentation goes to die. But at least it's organized." — schema.cx
        """
        # GitHub doesn't have a direct API to check if wiki exists
        # We check if the wiki git repository is accessible
        wiki_url = f"https://github.com/{owner}/{repo}.wiki.git"

        try:
            # Try to get repository info which includes 'has_wiki' flag
            endpoint = f"/repos/{owner}/{repo}"
            response = self._make_request(f"{self.BASE_URL}{endpoint}")
            data = response.json()
            return data.get("has_wiki", False)
        except Exception:
            return False

    def get_labels(self, owner: str, repo: str) -> list[Label]:
        """
        Fetch all labels for a repository.

        "Labels are just tags with prettier colors." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/labels"
        console.print(f"\n[cyan]🏷️  Fetching labels for repository: {owner}/{repo}[/cyan]")

        all_labels = []
        params = {"per_page": self.PER_PAGE, "page": 1}

        try:
            while True:
                response = self._make_request(f"{self.BASE_URL}{endpoint}", initial_params=params)
                data = response.json()

                if not data:
                    break

                for item in data:
                    label = Label(
                        id=item["id"],
                        name=item["name"],
                        description=item.get("description"),
                        color=item["color"],
                    )
                    all_labels.append(label)

                # Check for next page
                if "next" not in response.links:
                    break

                params["page"] += 1

            console.print(f"   [green]✓ Found {len(all_labels)} labels[/green]")
            return all_labels

        except GitHubAPIError as e:
            if "404" in str(e):
                print_warning("Repository not accessible", prefix="⚠️")
                return []
            raise

    def get_milestones(self, owner: str, repo: str, state: str = "all") -> list[Milestone]:
        """
        Fetch all milestones for a repository.

        "Milestones are just deadlines you can see coming." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/milestones"
        console.print(f"\n[cyan]🎯 Fetching milestones for repository: {owner}/{repo}[/cyan]")

        all_milestones = []
        params = {"state": state, "per_page": self.PER_PAGE, "page": 1}

        try:
            while True:
                response = self._make_request(f"{self.BASE_URL}{endpoint}", initial_params=params)
                data = response.json()

                if not data:
                    break

                for item in data:
                    milestone = Milestone(
                        id=item["id"],
                        number=item["number"],
                        title=item["title"],
                        description=item.get("description"),
                        state=item["state"],
                        open_issues=item["open_issues"],
                        closed_issues=item["closed_issues"],
                        created_at=item["created_at"],
                        updated_at=item["updated_at"],
                        due_on=item.get("due_on"),
                        closed_at=item.get("closed_at"),
                        html_url=item["html_url"],
                    )
                    all_milestones.append(milestone)

                # Check for next page
                if "next" not in response.links:
                    break

                params["page"] += 1

            console.print(f"   [green]✓ Found {len(all_milestones)} milestones[/green]")
            return all_milestones

        except GitHubAPIError as e:
            if "404" in str(e):
                print_warning("Repository not accessible", prefix="⚠️")
                return []
            raise

    def get_webhooks(self, owner: str, repo: str) -> list[Webhook]:
        """
        Fetch all webhooks for a repository.

        Requires admin access to the repository.
        "Webhooks are just callbacks with trust issues." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/hooks"
        console.print(f"\n[cyan]🔗 Fetching webhooks for repository: {owner}/{repo}[/cyan]")
        print_warning("Webhooks require admin access to the repository", prefix="ℹ️")

        all_webhooks = []
        params = {"per_page": self.PER_PAGE, "page": 1}

        try:
            while True:
                response = self._make_request(f"{self.BASE_URL}{endpoint}", initial_params=params)
                data = response.json()

                if not data:
                    break

                for item in data:
                    # Redact sensitive config info
                    config = item.get("config", {})
                    safe_config = {
                        "url": config.get("url", ""),
                        "content_type": config.get("content_type", "json"),
                        "insecure_ssl": config.get("insecure_ssl", "0"),
                    }

                    webhook = Webhook(
                        id=item["id"],
                        name=item.get("name", "web"),
                        active=item["active"],
                        events=item.get("events", []),
                        config=safe_config,
                        created_at=item["created_at"],
                        updated_at=item["updated_at"],
                    )
                    all_webhooks.append(webhook)

                # Check for next page
                if "next" not in response.links:
                    break

                params["page"] += 1

            console.print(f"   [green]✓ Found {len(all_webhooks)} webhooks[/green]")
            return all_webhooks

        except GitHubAPIError as e:
            if "404" in str(e) or "403" in str(e):
                print_warning("No access to webhooks (requires admin)", prefix="⚠️")
                return []
            raise

    def get_followers(self, username: str | None = None) -> list[Follower]:
        """
        Fetch all followers for a user.

        "Followers are just watchers for humans." — schema.cx
        """
        if username:
            endpoint = f"/users/{username}/followers"
            console.print(f"\n[cyan]👥 Fetching followers for user: {username}[/cyan]")
        else:
            endpoint = "/user/followers"
            authenticated_user = self._get_authenticated_user()
            console.print(f"\n[cyan]👥 Fetching YOUR followers (authenticated as {authenticated_user})[/cyan]")

        all_followers = []
        params = {"per_page": self.PER_PAGE, "page": 1}

        try:
            while True:
                response = self._make_request(f"{self.BASE_URL}{endpoint}", initial_params=params)
                data = response.json()

                if not data:
                    break

                for item in data:
                    follower = Follower(
                        login=item["login"],
                        id=item["id"],
                        avatar_url=item["avatar_url"],
                        html_url=item["html_url"],
                        type=item.get("type", "User"),
                    )
                    all_followers.append(follower)

                # Check for next page
                if "next" not in response.links:
                    break

                params["page"] += 1

            console.print(f"   [green]✓ Found {len(all_followers)} followers[/green]")
            return all_followers

        except GitHubAPIError as e:
            if "404" in str(e):
                print_warning("User not found", prefix="⚠️")
                return []
            raise

    def get_following(self, username: str | None = None) -> list[Follower]:
        """
        Fetch all users that a user is following.

        "Following is just stalking with consent." — schema.cx
        """
        if username:
            endpoint = f"/users/{username}/following"
            console.print(f"\n[cyan]👤 Fetching users that {username} is following[/cyan]")
        else:
            endpoint = "/user/following"
            authenticated_user = self._get_authenticated_user()
            console.print(f"\n[cyan]👤 Fetching users YOU are following (authenticated as {authenticated_user})[/cyan]")

        all_following = []
        params = {"per_page": self.PER_PAGE, "page": 1}

        try:
            while True:
                response = self._make_request(f"{self.BASE_URL}{endpoint}", initial_params=params)
                data = response.json()

                if not data:
                    break

                for item in data:
                    following = Follower(
                        login=item["login"],
                        id=item["id"],
                        avatar_url=item["avatar_url"],
                        html_url=item["html_url"],
                        type=item.get("type", "User"),
                    )
                    all_following.append(following)

                # Check for next page
                if "next" not in response.links:
                    break

                params["page"] += 1

            console.print(f"   [green]✓ Found {len(all_following)} users being followed[/green]")
            return all_following

        except GitHubAPIError as e:
            if "404" in str(e):
                print_warning("User not found", prefix="⚠️")
                return []
            raise

    def get_discussions(self, owner: str, repo: str) -> list[Discussion]:
        """
        Fetch all discussions for a repository using GraphQL API.

        "Discussions are just issues that went to therapy." — schema.cx
        """
        console.print(f"\n[cyan]💬 Fetching discussions for repository: {owner}/{repo}[/cyan]")

        # GraphQL query for discussions
        query = """
        query($owner: String!, $repo: String!, $cursor: String) {
            repository(owner: $owner, name: $repo) {
                discussions(first: 100, after: $cursor) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        id
                        number
                        title
                        body
                        author {
                            login
                        }
                        category {
                            name
                        }
                        answerChosenAt
                        locked
                        createdAt
                        updatedAt
                        url
                        comments {
                            totalCount
                        }
                        upvoteCount
                    }
                }
            }
        }
        """

        all_discussions = []
        cursor = None

        try:
            while True:
                variables = {"owner": owner, "repo": repo, "cursor": cursor}
                response = self.session.post(
                    "https://api.github.com/graphql",
                    json={"query": query, "variables": variables},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                if "errors" in data:
                    error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
                    if "Could not resolve" in error_msg or "NOT_FOUND" in str(data):
                        print_warning("Discussions not enabled for this repository", prefix="⚠️")
                        return []
                    raise GitHubAPIError(f"GraphQL error: {error_msg}")

                discussions_data = data.get("data", {}).get("repository", {}).get("discussions", {})
                nodes = discussions_data.get("nodes", [])

                if not nodes:
                    break

                for item in nodes:
                    discussion = Discussion(
                        id=item["id"],
                        number=item["number"],
                        title=item["title"],
                        body=item.get("body"),
                        author=item["author"]["login"] if item.get("author") else "ghost",
                        category=item["category"]["name"] if item.get("category") else "General",
                        answer_chosen=item.get("answerChosenAt") is not None,
                        locked=item.get("locked", False),
                        created_at=item["createdAt"],
                        updated_at=item["updatedAt"],
                        html_url=item["url"],
                        comments_count=item["comments"]["totalCount"],
                        upvote_count=item.get("upvoteCount", 0),
                    )
                    all_discussions.append(discussion)

                page_info = discussions_data.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")

            console.print(f"   [green]✓ Found {len(all_discussions)} discussions[/green]")
            return all_discussions

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print_warning("GraphQL API requires authentication", prefix="⚠️")
                return []
            raise GitHubAPIError(f"Failed to fetch discussions: {e}") from e
        except Exception as e:
            print_warning(f"Failed to fetch discussions: {e}", prefix="⚠️")
            return []

    def get_projects(self, owner: str, repo: str | None = None) -> list[Project]:
        """
        Fetch all projects for a user/org or repository using GraphQL API.

        "Projects are just spreadsheets with delusions of grandeur." — schema.cx
        """
        if repo:
            console.print(f"\n[cyan]📋 Fetching projects for repository: {owner}/{repo}[/cyan]")
        else:
            console.print(f"\n[cyan]📋 Fetching projects for: {owner}[/cyan]")

        # GraphQL query for projects v2
        if repo:
            query = """
            query($owner: String!, $repo: String!, $cursor: String) {
                repository(owner: $owner, name: $repo) {
                    projectsV2(first: 100, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            id
                            number
                            title
                            shortDescription
                            public
                            closed
                            createdAt
                            updatedAt
                            url
                            items {
                                totalCount
                            }
                            fields(first: 20) {
                                nodes {
                                    ... on ProjectV2Field {
                                        id
                                        name
                                        dataType
                                    }
                                    ... on ProjectV2SingleSelectField {
                                        id
                                        name
                                        dataType
                                        options {
                                            id
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
            variables = {"owner": owner, "repo": repo, "cursor": None}
        else:
            # User/org level projects
            query = """
            query($owner: String!, $cursor: String) {
                user(login: $owner) {
                    projectsV2(first: 100, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            id
                            number
                            title
                            shortDescription
                            public
                            closed
                            createdAt
                            updatedAt
                            url
                            items {
                                totalCount
                            }
                            fields(first: 20) {
                                nodes {
                                    ... on ProjectV2Field {
                                        id
                                        name
                                        dataType
                                    }
                                    ... on ProjectV2SingleSelectField {
                                        id
                                        name
                                        dataType
                                        options {
                                            id
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
            variables = {"owner": owner, "cursor": None}

        all_projects = []

        try:
            while True:
                response = self.session.post(
                    "https://api.github.com/graphql",
                    json={"query": query, "variables": variables},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                if "errors" in data:
                    error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
                    if "Could not resolve" in error_msg:
                        print_warning("Projects not found", prefix="⚠️")
                        return []
                    raise GitHubAPIError(f"GraphQL error: {error_msg}")

                # Extract projects data
                if repo:
                    projects_data = data.get("data", {}).get("repository", {}).get("projectsV2", {})
                else:
                    projects_data = data.get("data", {}).get("user", {}).get("projectsV2", {})

                nodes = projects_data.get("nodes", [])

                if not nodes:
                    break

                for item in nodes:
                    # Parse fields
                    fields = []
                    for field in item.get("fields", {}).get("nodes", []):
                        if field:
                            field_data = {
                                "id": field.get("id"),
                                "name": field.get("name"),
                                "type": field.get("dataType"),
                            }
                            if "options" in field:
                                field_data["options"] = field["options"]
                            fields.append(field_data)

                    project = Project(
                        id=item["id"],
                        number=item["number"],
                        title=item["title"],
                        description=item.get("shortDescription"),
                        public=item.get("public", False),
                        closed=item.get("closed", False),
                        created_at=item["createdAt"],
                        updated_at=item["updatedAt"],
                        html_url=item["url"],
                        items_count=item["items"]["totalCount"],
                        fields=fields,
                    )
                    all_projects.append(project)

                page_info = projects_data.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                variables["cursor"] = page_info.get("endCursor")

            console.print(f"   [green]✓ Found {len(all_projects)} projects[/green]")
            return all_projects

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print_warning("GraphQL API requires authentication", prefix="⚠️")
                return []
            raise GitHubAPIError(f"Failed to fetch projects: {e}") from e
        except Exception as e:
            print_warning(f"Failed to fetch projects: {e}", prefix="⚠️")
            return []
