"""
GitHub repository transfer functionality.

"Moving repos is like moving houses. Don't forget the keys." — schema.cx
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests

from .rich_utils import console, print_error, print_info, print_success, print_warning


class TransferError(Exception):
    """Raised when a repository transfer operation fails."""

    pass


@dataclass
class TransferResult:
    """Result of a single repository transfer operation."""

    repo_name: str
    source_owner: str
    target_org: str
    success: bool = False
    new_name: str | None = None
    message: str = ""
    error: str | None = None
    http_status: int | None = None
    validation_errors: list[str] = field(default_factory=list)

    @property
    def new_url(self) -> str | None:
        """Get the new repository URL after transfer."""
        if self.success:
            name = self.new_name or self.repo_name
            return f"https://github.com/{self.target_org}/{name}"
        return None


@dataclass
class TransferSummary:
    """Summary of all transfer operations."""

    total: int = 0
    successful: int = 0
    failed: int = 0
    results: list[TransferResult] = field(default_factory=list)

    def add_result(self, result: TransferResult) -> None:
        """Add a result to the summary."""
        self.total += 1
        if result.success:
            self.successful += 1
        else:
            self.failed += 1
        self.results.append(result)

    @property
    def failed_repos(self) -> list[TransferResult]:
        """Get list of failed transfers."""
        return [r for r in self.results if not r.success]


class TransferClient:
    """
    Client for GitHub repository transfer operations.

    "Transfer with care. There's no undo button." — schema.cx
    """

    API_VERSION = "2022-11-28"
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str) -> None:
        """Initialize the transfer client."""
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": self.API_VERSION,
            "User-Agent": "Farmore/0.10.0 (https://github.com/miztizm/farmore)",
        })
        self._authenticated_user: str | None = None

    def __enter__(self) -> "TransferClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close session."""
        self.close()

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()

    def get_authenticated_user(self) -> str:
        """Get the authenticated user's username."""
        if self._authenticated_user:
            return self._authenticated_user

        response = self.session.get(f"{self.BASE_URL}/user")
        self._handle_response_error(response, "get authenticated user")
        self._authenticated_user = response.json()["login"]
        return self._authenticated_user

    def _handle_response_error(
        self, response: requests.Response, action: str
    ) -> None:
        """Handle API response errors with specific messages."""
        if response.ok:
            return

        error_data = {}
        try:
            error_data = response.json()
        except ValueError:
            pass

        message = error_data.get("message", response.text)
        doc_url = error_data.get("documentation_url", "")

        # Check rate limit
        remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
        reset_ts = response.headers.get("X-RateLimit-Reset", "0")

        if response.status_code == 401:
            raise TransferError(
                f"Invalid or expired GitHub token. Please check GITHUB_TOKEN in .env file"
            )
        elif response.status_code == 403:
            if remaining == "0":
                reset_time = self._format_reset_time(reset_ts)
                raise TransferError(
                    f"GitHub API rate limit exceeded. Resets at {reset_time}"
                )
            raise TransferError(
                f"Insufficient permissions to {action}. "
                f"Ensure token has 'repo' scope and you have admin access. "
                f"Details: {message}"
            )
        elif response.status_code == 404:
            raise TransferError(f"Not found: {message}")
        elif response.status_code == 422:
            raise TransferError(
                f"Validation error: {message}. "
                f"Check if repository name already exists in target organization."
            )
        else:
            error_msg = f"GitHub API error ({response.status_code}): {message}"
            if doc_url:
                error_msg += f"\nDocumentation: {doc_url}"
            raise TransferError(error_msg)

    def _format_reset_time(self, timestamp: str) -> str:
        """Format rate limit reset timestamp."""
        try:
            reset_dt = datetime.fromtimestamp(int(timestamp))
            return reset_dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            return "unknown"

    def check_repo_admin_access(self, owner: str, repo: str) -> tuple[bool, str]:
        """
        Check if the authenticated user has admin access to a repository.

        Returns:
            Tuple of (has_admin, message)
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        response = self.session.get(url)

        if response.status_code == 404:
            return False, f"Repository '{owner}/{repo}' not found"

        if not response.ok:
            return False, f"Failed to check repository: {response.status_code}"

        data = response.json()
        permissions = data.get("permissions", {})

        if permissions.get("admin", False):
            return True, "Admin access confirmed"
        return False, "You do not have admin permissions on this repository"

    def check_org_exists(self, org: str) -> tuple[bool, str]:
        """
        Check if an organization exists and is accessible.

        Returns:
            Tuple of (exists, message)
        """
        url = f"{self.BASE_URL}/orgs/{org}"
        response = self.session.get(url)

        if response.status_code == 404:
            return False, f"Organization '{org}' not found"
        if not response.ok:
            return False, f"Failed to check organization: {response.status_code}"

        return True, "Organization exists and is accessible"

    def check_org_membership(self, org: str, username: str) -> tuple[bool, str]:
        """
        Check if user has permission to create repositories in the organization.

        Returns:
            Tuple of (has_permission, message)
        """
        url = f"{self.BASE_URL}/orgs/{org}/memberships/{username}"
        response = self.session.get(url)

        if response.status_code == 404:
            return False, f"User '{username}' is not a member of organization '{org}'"
        if not response.ok:
            return False, f"Failed to check membership: {response.status_code}"

        data = response.json()
        role = data.get("role", "")
        state = data.get("state", "")

        if state != "active":
            return False, f"Membership is not active (state: {state})"

        # Members and admins can typically create repos, but it depends on org settings
        # For safety, we just confirm membership exists
        return True, f"Member of organization with role: {role}"

    def check_repo_name_available(
        self, org: str, repo_name: str
    ) -> tuple[bool, str]:
        """
        Check if a repository name is available in the target organization.

        Returns:
            Tuple of (available, message)
        """
        url = f"{self.BASE_URL}/repos/{org}/{repo_name}"
        response = self.session.get(url)

        if response.status_code == 404:
            return True, "Repository name is available"
        if response.ok:
            return False, f"Repository '{org}/{repo_name}' already exists"

        return False, f"Failed to check repository: {response.status_code}"

    def validate_transfer(
        self,
        source_owner: str,
        repo_name: str,
        target_org: str,
        new_name: str | None = None,
    ) -> list[tuple[str, bool, str]]:
        """
        Perform all pre-transfer validation checks.

        Returns:
            List of (check_name, passed, message) tuples
        """
        checks = []

        # 1. Check admin access on source repository
        has_admin, msg = self.check_repo_admin_access(source_owner, repo_name)
        checks.append(("Admin access on source repo", has_admin, msg))

        if not has_admin:
            # Skip remaining checks if we can't access the source repo
            return checks

        # 2. Check target organization exists
        org_exists, msg = self.check_org_exists(target_org)
        checks.append(("Target organization exists", org_exists, msg))

        if not org_exists:
            return checks

        # 3. Check membership in target organization
        username = self.get_authenticated_user()
        has_membership, msg = self.check_org_membership(target_org, username)
        checks.append(("Organization membership", has_membership, msg))

        # 4. Check repository name availability
        check_name = new_name or repo_name
        available, msg = self.check_repo_name_available(target_org, check_name)
        checks.append((f"Name '{check_name}' available in org", available, msg))

        return checks

    def transfer_repository(
        self,
        source_owner: str,
        repo_name: str,
        target_org: str,
        new_name: str | None = None,
        team_ids: list[int] | None = None,
        dry_run: bool = False,
    ) -> TransferResult:
        """
        Transfer a repository to a target organization.

        Args:
            source_owner: Current owner of the repository
            repo_name: Name of the repository to transfer
            target_org: Target organization name
            new_name: Optional new name for the repository
            team_ids: Optional list of team IDs to grant access
            dry_run: If True, perform validation only without actual transfer

        Returns:
            TransferResult with transfer status
        """
        result = TransferResult(
            repo_name=repo_name,
            source_owner=source_owner,
            target_org=target_org,
            new_name=new_name,
        )

        # Perform validation checks
        console.print(f"\n[cyan]🔍 Validating transfer for: {source_owner}/{repo_name}[/cyan]")
        checks = self.validate_transfer(source_owner, repo_name, target_org, new_name)

        all_passed = True
        for check_name, passed, message in checks:
            if passed:
                console.print(f"   [green]✓[/green] {check_name}: {message}")
            else:
                console.print(f"   [red]✗[/red] {check_name}: {message}")
                result.validation_errors.append(f"{check_name}: {message}")
                all_passed = False

        if not all_passed:
            result.success = False
            result.error = "Pre-transfer validation failed"
            result.message = "; ".join(result.validation_errors)
            return result

        if dry_run:
            result.success = True
            result.message = "Dry run - validation passed, transfer not executed"
            console.print(f"   [yellow]⚠ DRY RUN - Would transfer to: {target_org}/{new_name or repo_name}[/yellow]")
            return result

        # Execute the transfer
        return self._execute_transfer(
            source_owner, repo_name, target_org, new_name, team_ids, result
        )

    def _execute_transfer(
        self,
        source_owner: str,
        repo_name: str,
        target_org: str,
        new_name: str | None,
        team_ids: list[int] | None,
        result: TransferResult,
    ) -> TransferResult:
        """Execute the actual repository transfer."""
        url = f"{self.BASE_URL}/repos/{source_owner}/{repo_name}/transfer"

        body: dict = {"new_owner": target_org}
        if new_name:
            body["new_name"] = new_name
        if team_ids:
            body["team_ids"] = team_ids

        console.print(f"   [cyan]🚀 Initiating transfer...[/cyan]")

        try:
            response = self.session.post(url, json=body)
            result.http_status = response.status_code

            if response.status_code == 202:
                # Success - transfer initiated (async operation)
                result.success = True
                final_name = new_name or repo_name
                result.message = f"Transfer initiated successfully"
                console.print(f"   [green]✓[/green] Transfer accepted (HTTP 202)")
                console.print(f"   [green]📍 New URL: https://github.com/{target_org}/{final_name}[/green]")
                return result

            # Handle error responses
            error_data = {}
            try:
                error_data = response.json()
            except ValueError:
                pass

            message = error_data.get("message", response.text)
            doc_url = error_data.get("documentation_url", "")

            result.success = False
            result.error = f"HTTP {response.status_code}: {message}"
            if doc_url:
                result.error += f" (See: {doc_url})"

            console.print(f"   [red]✗[/red] Transfer failed: {result.error}")
            return result

        except requests.RequestException as e:
            result.success = False
            result.error = f"Network error: {str(e)}"
            console.print(f"   [red]✗[/red] {result.error}")
            return result


def validate_repo_name(name: str) -> tuple[bool, str]:
    """
    Validate repository name against GitHub naming rules.

    GitHub allows: alphanumeric, hyphens, underscores, and periods.
    Cannot start or end with a period.
    Cannot contain consecutive periods.
    """
    if not name:
        return False, "Repository name cannot be empty"

    if len(name) > 100:
        return False, "Repository name cannot exceed 100 characters"

    # GitHub's allowed pattern
    pattern = r'^[a-zA-Z0-9._-]+$'
    if not re.match(pattern, name):
        return False, "Repository name contains invalid characters (allowed: alphanumeric, '.', '-', '_')"

    if name.startswith('.') or name.endswith('.'):
        return False, "Repository name cannot start or end with a period"

    if '..' in name:
        return False, "Repository name cannot contain consecutive periods"

    return True, "Valid repository name"


def validate_org_name(name: str) -> tuple[bool, str]:
    """Validate organization name."""
    if not name:
        return False, "Organization name cannot be empty"

    if len(name) > 39:
        return False, "Organization name cannot exceed 39 characters"

    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$'
    if not re.match(pattern, name):
        return False, "Organization name contains invalid characters"

    return True, "Valid organization name"


def parse_repo_list(repo_arg: str) -> list[str]:
    """
    Parse repository argument which can be:
    - Single repo name: "my-repo"
    - Comma-separated: "repo1,repo2,repo3"
    - File reference: "@repos.txt"

    Returns:
        List of repository names
    """
    repos = []

    if repo_arg.startswith("@"):
        # File reference
        file_path = Path(repo_arg[1:])
        if not file_path.exists():
            raise ValueError(f"Repository file not found: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    repos.append(line)
    else:
        # Single or comma-separated repos
        repos = [r.strip() for r in repo_arg.split(",") if r.strip()]

    return repos


def parse_team_ids(team_ids_str: str | None) -> list[int] | None:
    """Parse comma-separated team IDs string into list of integers."""
    if not team_ids_str:
        return None

    try:
        ids = [int(id_str.strip()) for id_str in team_ids_str.split(",")]
        for id_val in ids:
            if id_val <= 0:
                raise ValueError(f"Team ID must be a positive integer: {id_val}")
        return ids
    except ValueError as e:
        raise ValueError(f"Invalid team IDs format: {e}")

