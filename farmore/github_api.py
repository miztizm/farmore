"""
GitHub API client with pagination support.

"The API is just a door. Your token is the key. Don't lose it." — schema.cx
"""

import re
import time
from datetime import datetime

import requests

from .models import (
    Config,
    Issue,
    PullRequest,
    Release,
    ReleaseAsset,
    Repository,
    RepositorySecret,
    TargetType,
    UserProfile,
    Visibility,
    Workflow,
    WorkflowRun,
)


class GitHubAPIError(Exception):
    """GitHub API error."""

    pass


class RateLimitError(GitHubAPIError):
    """Rate limit exceeded error."""

    pass


class GitHubAPIClient:
    """
    GitHub REST API v3 client.

    "They track everything. Might as well use their API." — schema.cx
    """

    BASE_URL = "https://api.github.com"
    PER_PAGE = 100  # Maximum allowed by GitHub

    def __init__(self, config: Config) -> None:
        """Initialize the GitHub API client."""
        self.config = config
        self.session = requests.Session()

        # Set up authentication headers
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Farmore/0.1.0 (https://github.com/miztizm/farmore)",
        }

        if config.token:
            headers["Authorization"] = f"token {config.token}"

        self.session.headers.update(headers)

        # Cache authenticated username for filtering
        self._authenticated_username: str | None = None

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
                print(f"\n🔍 Fetching YOUR repositories (authenticated as {authenticated_user})")
                print(f"   Using /user/repos endpoint for public + private access")
            else:
                # Use /users/{username}/repos for other users (public only)
                endpoint = f"/users/{self.config.target_name}/repos"
                params = {"type": "all"}
                if authenticated_user:
                    print(f"\n🔍 Fetching repositories for user '{self.config.target_name}' (you are {authenticated_user})")
                    print(f"   ⚠️  Can only access PUBLIC repos for other users")
                else:
                    print(f"\n🔍 Fetching repositories without authentication (public only)")
        else:  # ORG
            endpoint = f"/orgs/{self.config.target_name}/repos"
            # Add type=all parameter to get all org repos (public + private)
            params = {"type": "all"}
            print(f"\n🔍 Fetching repositories for organization '{self.config.target_name}'")

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
            print(f"   📦 Page: {len(page_repos)} repos ({public_count} public, {private_count} private)")

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
                        print(
                            f"\n⏳ Rate limit hit. Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{max_retries})"
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

        auth_status = "✓ Authenticated" if self.config.token else "⚠ Unauthenticated"

        print(f"\n📊 GitHub API Rate Limit: {auth_status}")
        print(f"   Limit: {limit}/hour | Remaining: {remaining} | Resets at: {reset_str}")

        if not self.config.token:
            print("   💡 Tip: Use GITHUB_TOKEN for 5,000 requests/hour (vs 60 unauthenticated)")

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
                print(f"   🔍 Filtered by visibility: {before} → {len(filtered)}")

        # Filter forks
        if not self.config.include_forks:
            before = len(filtered)
            forks = [r for r in filtered if r.fork]
            filtered = [r for r in filtered if not r.fork]
            if len(forks) > 0:
                print(f"   🔍 Filtered out {len(forks)} forks (use --include-forks to include them)")

        # Filter archived
        if not self.config.include_archived:
            before = len(filtered)
            archived = [r for r in filtered if r.archived]
            filtered = [r for r in filtered if not r.archived]
            if len(archived) > 0:
                print(f"   🔍 Filtered out {len(archived)} archived repos (use --include-archived to include them)")

        # Filter organization repositories
        if self.config.exclude_org_repos and self._authenticated_username:
            before = len(filtered)
            # Keep only repos where owner matches authenticated user
            org_repos = [r for r in filtered if r.owner.lower() != self._authenticated_username.lower()]
            filtered = [r for r in filtered if r.owner.lower() == self._authenticated_username.lower()]
            if len(org_repos) > 0:
                print(f"   🔍 Filtered out {len(org_repos)} organization repos (remove --exclude-orgs to include them)")

        if len(filtered) < initial_count:
            print(f"   📊 Total after filtering: {initial_count} → {len(filtered)} repositories")

        return filtered

    def get_user_profile(self, username: str | None = None) -> UserProfile:
        """
        Fetch user profile information.

        If username is None, fetches the authenticated user's profile.
        "Identity is just metadata. But it's YOUR metadata." — schema.cx
        """
        if username:
            endpoint = f"/users/{username}"
            print(f"\n👤 Fetching profile for user: {username}")
        else:
            endpoint = "/user"
            print(f"\n👤 Fetching YOUR profile (authenticated user)")

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
            print(f"\n⭐ Fetching starred repositories for user: {username}")
        else:
            endpoint = "/user/starred"
            authenticated_user = self._get_authenticated_user()
            print(f"\n⭐ Fetching YOUR starred repositories (authenticated as {authenticated_user})")

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

        print(f"   ✓ Found {len(all_repos)} starred repositories")
        return all_repos

    def get_watched_repositories(self, username: str | None = None) -> list[Repository]:
        """
        Fetch repositories watched by a user.

        If username is None, fetches the authenticated user's watched repos.
        "Watching is caring. Or stalking. Depends on perspective." — schema.cx
        """
        if username:
            endpoint = f"/users/{username}/subscriptions"
            print(f"\n👁 Fetching watched repositories for user: {username}")
        else:
            endpoint = "/user/subscriptions"
            authenticated_user = self._get_authenticated_user()
            print(f"\n👁 Fetching YOUR watched repositories (authenticated as {authenticated_user})")

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

        print(f"   ✓ Found {len(all_repos)} watched repositories")
        return all_repos

    def get_repository_secrets(self, owner: str, repo: str) -> list[RepositorySecret]:
        """
        Fetch repository secrets (names only, not values).

        "Secrets are meant to be kept. But their names? Those we can share." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/actions/secrets"
        print(f"\n🔐 Fetching secrets for repository: {owner}/{repo}")
        print(f"   ⚠️  Note: GitHub API only returns secret names, not values")

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

            print(f"   ✓ Found {len(secrets)} secrets")
            return secrets
        except GitHubAPIError as e:
            if "404" in str(e):
                print(f"   ⚠️  Repository not found or no access to secrets")
                return []
            raise

    def delete_repository(self, owner: str, repo: str) -> bool:
        """
        Delete a repository.

        "Deletion is permanent. There's no undo button in the cloud." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}"
        print(f"\n🗑️  Deleting repository: {owner}/{repo}")

        try:
            response = self.session.delete(f"{self.BASE_URL}{endpoint}")
            response.raise_for_status()
            print(f"   ✓ Repository deleted successfully")
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
        print(f"\n📋 Fetching issues for repository: {owner}/{repo}")
        print(f"   State filter: {state}")

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
                    print(f"   ⚠️  Skipping issue #{item.get('number', '?')}: {e}")
                    continue

            # Check for next page
            if "next" not in response.links:
                break

            params["page"] += 1

        print(f"   ✓ Found {len(all_issues)} issues")
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
        print(f"\n🔀 Fetching pull requests for repository: {owner}/{repo}")
        print(f"   State filter: {state}")

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

        print(f"   ✓ Found {len(all_prs)} pull requests")
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
        print(f"\n⚙️  Fetching GitHub Actions workflows for: {owner}/{repo}")

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

            print(f"   ✓ Found {len(workflows)} workflows")
            return workflows, workflow_files

        except GitHubAPIError as e:
            if "404" in str(e):
                print(f"   ⚠️  No workflows found or repository not accessible")
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
        print(f"\n📊 Fetching workflow runs for: {owner}/{repo} (limit: {limit})")

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

            print(f"   ✓ Found {len(runs)} workflow runs")
            return runs

        except GitHubAPIError as e:
            if "404" in str(e):
                print(f"   ⚠️  No workflow runs found")
                return []
            raise

    def get_releases(self, owner: str, repo: str) -> list[Release]:
        """
        Fetch all releases for a repository.

        "Releases are just commits with marketing." — schema.cx
        """
        endpoint = f"/repos/{owner}/{repo}/releases"
        print(f"\n🚀 Fetching releases for repository: {owner}/{repo}")

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

            print(f"   ✓ Found {len(all_releases)} releases")
            return all_releases

        except GitHubAPIError as e:
            if "404" in str(e):
                print(f"   ⚠️  No releases found or repository not accessible")
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
