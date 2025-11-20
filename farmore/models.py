"""
Data models for Farmore.

"In the end, it's all just data. But organized data? That's power." — schema.cx
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Visibility(str, Enum):
    """Repository visibility filter."""

    PUBLIC = "public"
    PRIVATE = "private"
    ALL = "all"


class TargetType(str, Enum):
    """Type of GitHub target (user or organization)."""

    USER = "user"
    ORG = "org"


class RepositoryCategory(str, Enum):
    """Category for organizing repositories in backup directory structure."""

    PRIVATE = "private"
    PUBLIC = "public"
    STARRED = "starred"
    WATCHED = "watched"
    ORGANIZATIONS = "organizations"
    FORKS = "forks"


@dataclass
class Repository:
    """
    Represents a GitHub repository.

    "Every repo tells a story. Make sure yours has a backup." — schema.cx
    """

    name: str
    full_name: str
    owner: str
    ssh_url: str
    clone_url: str
    default_branch: str
    private: bool = False
    fork: bool = False
    archived: bool = False
    owner_type: str = "User"  # "User" or "Organization"

    @property
    def local_path(self) -> str:
        """Get the local path component for this repo (owner/name)."""
        if self.owner:
            return f"{self.owner}/{self.name}"
        else:
            # Flat structure: just the repo name
            return self.name

    @property
    def is_org_repo(self) -> bool:
        """Check if this repository belongs to an organization."""
        return self.owner_type.lower() == "organization"


@dataclass
class Config:
    """
    Configuration for Farmore operations.

    "Configuration is just organized paranoia." — schema.cx
    """

    # Target information
    target_type: TargetType
    target_name: str

    # Destination
    dest: Path

    # Authentication
    token: str | None = None

    # Filtering options
    visibility: Visibility = Visibility.ALL
    include_forks: bool = False
    include_archived: bool = False
    exclude_org_repos: bool = False  # Exclude organization repositories

    # Execution options
    dry_run: bool = False
    max_workers: int = 4

    # Runtime state
    use_ssh: bool = True  # Prefer SSH, fallback to HTTPS

    # Repository categorization (for organizing backups by type)
    repository_category: RepositoryCategory | None = None
    disable_categorization: bool = False  # Disable category subdirectories (for search results)

    def __post_init__(self) -> None:
        """Validate and normalize configuration."""
        # Ensure dest is a Path object
        if not isinstance(self.dest, Path):
            self.dest = Path(self.dest)

        # Expand user home directory
        self.dest = self.dest.expanduser()

    def get_repo_category_path(self, repo: Repository) -> Path:
        """
        Get the categorized path for a repository based on its attributes.

        Categorization priority:
        1. If disable_categorization is True, return just the repo local_path
        2. If repository_category is set (starred/watched), use that
        3. If repo is from an organization, use organizations/<org-name>
        4. If repo is a fork, use forks
        5. Otherwise, use private or public based on visibility

        Returns:
            Path relative to dest that includes category subdirectory
        """
        # If categorization is disabled (e.g., for search results), return just the local path
        if self.disable_categorization:
            return Path(repo.local_path)

        # If a specific category is set (e.g., starred, watched), use it
        if self.repository_category:
            return Path("repos") / self.repository_category.value / repo.local_path

        # Check if it's an organization repository
        if repo.is_org_repo:
            return Path("repos") / RepositoryCategory.ORGANIZATIONS.value / repo.local_path

        # Check if it's a fork
        if repo.fork:
            return Path("repos") / RepositoryCategory.FORKS.value / repo.local_path

        # Default to private/public based on visibility
        category = RepositoryCategory.PRIVATE if repo.private else RepositoryCategory.PUBLIC
        return Path("repos") / category.value / repo.local_path


@dataclass
class MirrorResult:
    """
    Result of a single repository mirror operation.

    "Success is just failure that hasn't happened yet. Log everything." — schema.cx
    """

    repo: Repository
    success: bool
    action: str  # "cloned", "updated", "skipped", "failed"
    message: str = ""
    error: str | None = None


@dataclass
class MirrorSummary:
    """
    Summary of all mirror operations.

    "Numbers don't lie. Unless they're in a database." — schema.cx
    """

    total: int = 0
    cloned: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def add_result(self, result: MirrorResult) -> None:
        """Add a result to the summary."""
        self.total += 1

        if result.success:
            if result.action == "cloned":
                self.cloned += 1
            elif result.action == "updated":
                self.updated += 1
            elif result.action == "skipped":
                self.skipped += 1
        else:
            self.failed += 1
            if result.error:
                self.errors.append(f"{result.repo.full_name}: {result.error}")

    @property
    def success_count(self) -> int:
        """Total successful operations."""
        return self.cloned + self.updated + self.skipped

    @property
    def has_failures(self) -> bool:
        """Check if any operations failed."""
        return self.failed > 0


@dataclass
class UserProfile:
    """
    Represents a GitHub user profile.

    "Identity is just metadata. But it's YOUR metadata." — schema.cx
    """

    login: str
    name: str | None
    email: str | None
    bio: str | None
    company: str | None
    location: str | None
    blog: str | None
    twitter_username: str | None
    public_repos: int
    public_gists: int
    followers: int
    following: int
    created_at: str
    updated_at: str
    hireable: bool | None = None
    avatar_url: str | None = None
    html_url: str | None = None


@dataclass
class RepositorySecret:
    """
    Represents a GitHub Actions repository secret (name only, not value).

    "Secrets are meant to be kept. But their names? Those we can share." — schema.cx
    """

    name: str
    created_at: str
    updated_at: str


@dataclass
class Issue:
    """
    Represents a GitHub issue.

    "Issues are just features that haven't been closed yet." — schema.cx
    """

    number: int
    title: str
    state: str  # "open" or "closed"
    user: str  # Username of creator
    body: str | None
    labels: list[str]
    assignees: list[str]
    created_at: str
    updated_at: str
    closed_at: str | None
    comments_count: int
    html_url: str
    comments: list[dict] = field(default_factory=list)  # Optional: include comments


@dataclass
class PullRequest:
    """
    Represents a GitHub pull request.

    "Pull requests are where code goes to be judged." — schema.cx
    """

    number: int
    title: str
    state: str  # "open", "closed", or "merged"
    user: str  # Username of creator
    body: str | None
    labels: list[str]
    assignees: list[str]
    created_at: str
    updated_at: str
    closed_at: str | None
    merged_at: str | None
    merged: bool
    draft: bool
    head_ref: str  # Source branch
    base_ref: str  # Target branch
    commits_count: int
    comments_count: int
    review_comments_count: int
    html_url: str
    diff_url: str
    patch_url: str
    comments: list[dict] = field(default_factory=list)  # Optional: include comments


@dataclass
class Workflow:
    """
    Represents a GitHub Actions workflow file.

    "Automation is just laziness with a good PR." — schema.cx
    """

    name: str
    path: str
    state: str  # "active", "disabled_manually", etc.
    created_at: str
    updated_at: str
    html_url: str
    badge_url: str


@dataclass
class WorkflowRun:
    """
    Represents a GitHub Actions workflow run.

    "Every run tells a story. Usually a story of failure." — schema.cx
    """

    id: int
    name: str
    status: str  # "completed", "in_progress", "queued"
    conclusion: str | None  # "success", "failure", "cancelled", etc.
    workflow_name: str
    event: str  # "push", "pull_request", etc.
    created_at: str
    updated_at: str
    run_number: int
    html_url: str


@dataclass
class Release:
    """
    Represents a GitHub release.

    "Releases are just commits with marketing." — schema.cx
    """

    id: int
    tag_name: str
    name: str | None
    body: str | None  # Release notes
    draft: bool
    prerelease: bool
    created_at: str
    published_at: str | None
    author: str  # Username
    html_url: str
    tarball_url: str
    zipball_url: str
    assets: list[dict] = field(default_factory=list)  # Release assets


@dataclass
class ReleaseAsset:
    """
    Represents a GitHub release asset (binary file).

    "Assets are just files with a version number." — schema.cx
    """

    id: int
    name: str
    label: str | None
    content_type: str
    size: int  # Size in bytes
    download_count: int
    created_at: str
    updated_at: str
    browser_download_url: str
