"""
Farmore CLI interface.

"The command line is where the real work happens. Everything else is just theater." — schema.cx
"""

import json
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

import requests
import typer
import yaml
from dotenv import load_dotenv
from rich.table import Table

from .git_utils import GitOperations
from .github_api import GitHubAPIClient
from .mirror import MirrorOrchestrator
from .models import Config, RepositoryCategory, TargetType, Visibility
from .rich_utils import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from .validation import validate_repository_format as _validate_repo_format

# Load environment variables from .env file if it exists
# "Configuration is just organized secrets." — schema.cx
load_dotenv()

app = typer.Typer(
    name="farmore",
    help="🥔 Farmore - Mirror every repo you own — in one command.",
    add_completion=False,
)


def get_default_user_dest(username: str) -> Path:
    """
    Get the default destination path for a user's backups.

    Returns: backups/<username>/
    """
    return Path("backups") / username


def get_default_profile_dest(username: str, format: str = "json") -> Path:
    """
    Get the default destination path for a user's profile export.

    Returns: backups/<username>/profile.{json|yaml}
    """
    return Path("backups") / username / f"profile.{format}"


def get_default_secrets_dest(owner: str, repo: str, format: str = "json") -> Path:
    """
    Get the default destination path for repository secrets export.

    Returns: backups/<owner>/data/secrets/<owner>_<repo>_secrets.{json|yaml}
    """
    return Path("backups") / owner / "data" / "secrets" / f"{owner}_{repo}_secrets.{format}"


def get_default_issues_dest(owner: str, repo: str, format: str = "json") -> Path:
    """
    Get the default destination path for issues export.

    Returns: backups/<owner>/data/issues/<owner>_<repo>_issues.{json|yaml}
    """
    return Path("backups") / owner / "data" / "issues" / f"{owner}_{repo}_issues.{format}"


def get_default_pulls_dest(owner: str, repo: str, format: str = "json") -> Path:
    """
    Get the default destination path for pull requests export.

    Returns: backups/<owner>/data/pulls/<owner>_<repo>_pulls.{json|yaml}
    """
    return Path("backups") / owner / "data" / "pulls" / f"{owner}_{repo}_pulls.{format}"


def get_default_workflows_dest(owner: str, repo: str) -> Path:
    """
    Get the default destination path for workflows backup.

    Returns: backups/<owner>/data/workflows/<owner>_<repo>/
    """
    return Path("backups") / owner / "data" / "workflows" / f"{owner}_{repo}"


def get_default_releases_dest(owner: str, repo: str) -> Path:
    """
    Get the default destination path for releases backup.

    Returns: backups/<owner>/data/releases/<owner>_<repo>/
    """
    return Path("backups") / owner / "data" / "releases" / f"{owner}_{repo}"


def get_default_wiki_dest(owner: str, repo: str) -> Path:
    """
    Get the default destination path for wiki backup.

    Returns: backups/<owner>/data/wikis/<owner>_<repo>.wiki/
    """
    return Path("backups") / owner / "data" / "wikis" / f"{owner}_{repo}.wiki"


def sanitize_query_for_dirname(query: str, max_length: int = 50) -> str:
    """
    Sanitize a search query string for use as a directory name.

    Args:
        query: The search query string
        max_length: Maximum length of the sanitized string (default: 50)

    Returns:
        Sanitized string safe for use as a directory name

    Examples:
        "machine learning" -> "machine-learning"
        "Python CLI tools!" -> "python-cli-tools"
        "awesome-python" -> "awesome-python"
    """
    import re

    # Convert to lowercase
    sanitized = query.lower()

    # Replace spaces with hyphens
    sanitized = sanitized.replace(" ", "-")

    # Remove special characters (keep only alphanumeric, hyphens, and underscores)
    sanitized = re.sub(r"[^a-z0-9\-_]", "", sanitized)

    # Replace multiple consecutive hyphens with a single hyphen
    sanitized = re.sub(r"-+", "-", sanitized)

    # Remove leading/trailing hyphens
    sanitized = sanitized.strip("-")

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip("-")

    # Fallback if empty
    if not sanitized:
        sanitized = "search-results"

    return sanitized


def validate_repository_format(repository: str) -> tuple[str, str]:
    """
    Validate and parse repository string in 'owner/repo' format.
    
    This is a wrapper around the validation module function that converts
    ValidationError to ValueError for CLI backward compatibility.
    
    Args:
        repository: Repository string in format 'owner/repo'
    
    Returns:
        Tuple of (owner, repo) if valid
        
    Raises:
        ValueError: If format is invalid or contains disallowed characters
    """
    from .validation import ValidationError
    
    try:
        return _validate_repo_format(repository)
    except ValidationError as e:
        raise ValueError(str(e)) from e


def export_repository_data(
    client: GitHubAPIClient,
    repos: list,
    username: str,
    include_issues: bool,
    include_pulls: bool,
    include_workflows: bool,
    include_releases: bool,
    include_wikis: bool,
    token: str | None,
) -> None:
    """
    Export additional repository data (issues, PRs, workflows, releases, wikis).

    "Data without backups is just temporary data." — schema.cx
    """
    if not any([include_issues, include_pulls, include_workflows, include_releases, include_wikis]):
        return

    console.print(f"\n📊 Exporting additional repository data...")

    for repo in repos:
        owner = repo.owner
        repo_name = repo.name

        try:
            # Export issues
            if include_issues:
                dest = get_default_issues_dest(owner, repo_name, "json")
                dest.parent.mkdir(parents=True, exist_ok=True)

                issues_list = client.get_issues(owner, repo_name, state="all", include_comments=False)
                issues_data = {
                    "repository": f"{owner}/{repo_name}",
                    "total_issues": len(issues_list),
                    "exported_at": datetime.now().isoformat(),
                    "issues": [
                        {
                            "number": issue.number,
                            "title": issue.title,
                            "state": issue.state,
                            "user": issue.user,
                            "created_at": issue.created_at,
                            "html_url": issue.html_url,
                        }
                        for issue in issues_list
                    ],
                }
                with open(dest, "w") as f:
                    json.dump(issues_data, f, indent=2)
                console.print(f"   [green]✓ Issues exported: {owner}/{repo_name} ({len(issues_list)} issues)[/green]")

            # Export pull requests
            if include_pulls:
                dest = get_default_pulls_dest(owner, repo_name, "json")
                dest.parent.mkdir(parents=True, exist_ok=True)

                prs_list = client.get_pull_requests(owner, repo_name, state="all", include_comments=False)
                prs_data = {
                    "repository": f"{owner}/{repo_name}",
                    "total_pull_requests": len(prs_list),
                    "exported_at": datetime.now().isoformat(),
                    "pull_requests": [
                        {
                            "number": pr.number,
                            "title": pr.title,
                            "state": pr.state,
                            "user": pr.user,
                            "merged": pr.merged,
                            "created_at": pr.created_at,
                            "html_url": pr.html_url,
                        }
                        for pr in prs_list
                    ],
                }
                with open(dest, "w") as f:
                    json.dump(prs_data, f, indent=2)
                console.print(f"   [green]✓ Pull requests exported: {owner}/{repo_name} ({len(prs_list)} PRs)[/green]")

            # Export workflows
            if include_workflows:
                dest = get_default_workflows_dest(owner, repo_name)
                dest.mkdir(parents=True, exist_ok=True)

                workflows_list, workflow_files = client.get_workflows(owner, repo_name)
                if workflows_list:
                    for wf_file in workflow_files:
                        file_path = dest / Path(wf_file["path"]).name
                        with open(file_path, "w") as f:
                            f.write(wf_file["content"])

                    metadata = {
                        "repository": f"{owner}/{repo_name}",
                        "total_workflows": len(workflows_list),
                        "exported_at": datetime.now().isoformat(),
                        "workflows": [{"name": wf.name, "path": wf.path} for wf in workflows_list],
                    }
                    with open(dest / "metadata.json", "w") as f:
                        json.dump(metadata, f, indent=2)
                    console.print(f"   [green]✓ Workflows exported: {owner}/{repo_name} ({len(workflows_list)} workflows)[/green]")

            # Export releases
            if include_releases:
                dest = get_default_releases_dest(owner, repo_name)
                dest.mkdir(parents=True, exist_ok=True)

                releases_list = client.get_releases(owner, repo_name)
                if releases_list:
                    metadata = {
                        "repository": f"{owner}/{repo_name}",
                        "total_releases": len(releases_list),
                        "exported_at": datetime.now().isoformat(),
                        "releases": [
                            {
                                "tag_name": release.tag_name,
                                "name": release.name,
                                "created_at": release.created_at,
                                "html_url": release.html_url,
                            }
                            for release in releases_list
                        ],
                    }
                    with open(dest / "metadata.json", "w") as f:
                        json.dump(metadata, f, indent=2)
                    console.print(f"   [green]✓ Releases exported: {owner}/{repo_name} ({len(releases_list)} releases)[/green]")

            # Backup wikis
            if include_wikis:
                has_wiki = client.check_wiki_exists(owner, repo_name)
                if has_wiki:
                    dest = get_default_wiki_dest(owner, repo_name)
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    wiki_url = f"https://github.com/{owner}/{repo_name}.wiki.git"

                    if not dest.exists():
                        try:
                            subprocess.run(
                                ["git", "clone", wiki_url, str(dest)],
                                capture_output=True,
                                text=True,
                                check=True,
                                timeout=300,
                            )
                            console.print(f"   [green]✓ Wiki cloned: {owner}/{repo_name}[/green]")
                        except subprocess.CalledProcessError:
                            pass  # Silently skip if clone fails
                    else:
                        try:
                            subprocess.run(
                                ["git", "pull"],
                                cwd=dest,
                                capture_output=True,
                                text=True,
                                check=True,
                                timeout=120,
                            )
                            console.print(f"   [green]✓ Wiki updated: {owner}/{repo_name}[/green]")
                        except subprocess.CalledProcessError:
                            pass  # Silently skip if pull fails

        except Exception as e:
            console.print(f"   ⚠️  Error exporting data for {owner}/{repo_name}: {e}")
            continue


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from . import __version__
        console.print(f"Farmore version {__version__}")
        console.print("Repository: https://github.com/miztizm/farmore")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """
    🥔 Farmore - Mirror every repo you own — in one command.

    "Control is an illusion. But backups? Those are real." — schema.cx
    """
    pass


@app.command()
def user(
    username: str = typer.Argument(..., help="GitHub username"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for backups (default: backups/<username>/)",
    ),
    visibility: Visibility = typer.Option(
        Visibility.ALL,
        "--visibility",
        help="Filter repositories by visibility",
    ),
    include_forks: bool = typer.Option(
        False,
        "--include-forks",
        help="Include forked repositories",
    ),
    include_archived: bool = typer.Option(
        False,
        "--include-archived",
        help="Include archived repositories",
    ),
    exclude_org_repos: bool = typer.Option(
        False,
        "--exclude-orgs",
        help="Exclude organization repositories (only download personal repos)",
    ),
    exclude: list[str] = typer.Option(
        [],
        "--exclude",
        "-e",
        help="Repository names to exclude (can be used multiple times)",
    ),
    name_regex: str | None = typer.Option(
        None,
        "--name-regex",
        "-N",
        help="Only backup repos matching this regex pattern (e.g., '^my-prefix-.*')",
    ),
    incremental: bool = typer.Option(
        False,
        "--incremental",
        "-i",
        help="Only backup repos that have changed since last backup",
    ),
    include_issues: bool = typer.Option(
        False,
        "--include-issues",
        help="Export issues for all repositories",
    ),
    include_pulls: bool = typer.Option(
        False,
        "--include-pulls",
        help="Export pull requests for all repositories",
    ),
    include_workflows: bool = typer.Option(
        False,
        "--include-workflows",
        help="Backup GitHub Actions workflows for all repositories",
    ),
    include_releases: bool = typer.Option(
        False,
        "--include-releases",
        help="Download releases for all repositories",
    ),
    include_wikis: bool = typer.Option(
        False,
        "--include-wikis",
        help="Backup wikis for all repositories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview actions without executing",
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        help="Skip repositories that already exist locally (don't update them)",
    ),
    bare: bool = typer.Option(
        False,
        "--bare",
        help="Create bare/mirror clones (preserves all refs, branches, tags)",
    ),
    lfs: bool = typer.Option(
        False,
        "--lfs",
        help="Use Git LFS for cloning (for repos with large files)",
    ),
    max_workers: int = typer.Option(
        4,
        "--max-workers",
        "-w",
        help="Maximum number of parallel workers",
        min=1,
        max=20,
    ),
    github_host: str | None = typer.Option(
        None,
        "--github-host",
        "-H",
        help="GitHub Enterprise hostname (e.g., github.mycompany.com)",
        envvar="GITHUB_HOST",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Backup all repositories for a GitHub user.

    "Every user has secrets. Make sure their repos aren't lost." — schema.cx

    Example:
        farmore user miztizm
        farmore user miztizm --dest ./custom_backups
        farmore user miztizm --include-issues --include-pulls --include-wikis
        farmore user miztizm --bare --lfs  # Mirror clone with LFS support
        farmore user miztizm --exclude repo1 --exclude repo2  # Exclude specific repos
        farmore user miztizm --name-regex '^my-prefix-.*'  # Only repos matching pattern
        farmore user miztizm --incremental  # Only repos changed since last backup
    """
    # Use default destination if not provided
    if dest is None:
        dest = get_default_user_dest(username)

    if token and token == typer.get_app_dir("farmore"):
        # Token was passed via CLI flag
        console.print(
            "[yellow]⚠ Warning: Passing tokens via CLI flags exposes them in shell history. "
            "Use GITHUB_TOKEN environment variable instead.[/yellow]\n"
        )

    config = Config(
        target_type=TargetType.USER,
        target_name=username,
        dest=dest,
        token=token,
        visibility=visibility,
        include_forks=include_forks,
        include_archived=include_archived,
        exclude_org_repos=exclude_org_repos,
        exclude_repos=list(exclude) if exclude else None,
        name_regex=name_regex,
        incremental=incremental,
        dry_run=dry_run,
        skip_existing=skip_existing,
        bare=bare,
        lfs=lfs,
        max_workers=max_workers,
        github_host=github_host,
    )

    orchestrator = MirrorOrchestrator(config)
    summary = orchestrator.run()

    # Export additional data if requested
    if any([include_issues, include_pulls, include_workflows, include_releases, include_wikis]):
        client = GitHubAPIClient(config)
        repos = client.get_repositories()

        export_repository_data(
            client=client,
            repos=repos,
            username=username,
            include_issues=include_issues,
            include_pulls=include_pulls,
            include_workflows=include_workflows,
            include_releases=include_releases,
            include_wikis=include_wikis,
            token=token,
        )

    # Exit with appropriate code
    if summary.has_failures and summary.success_count == 0:
        # All operations failed
        sys.exit(1)
    # Exit 0 even if some repos failed but were reported
    sys.exit(0)


@app.command()
def org(
    orgname: str = typer.Argument(..., help="GitHub organization name"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for backups (default: backups/<orgname>/)",
    ),
    visibility: Visibility = typer.Option(
        Visibility.ALL,
        "--visibility",
        help="Filter repositories by visibility",
    ),
    include_forks: bool = typer.Option(
        False,
        "--include-forks",
        help="Include forked repositories",
    ),
    include_archived: bool = typer.Option(
        False,
        "--include-archived",
        help="Include archived repositories",
    ),
    exclude: list[str] = typer.Option(
        [],
        "--exclude",
        "-e",
        help="Repository names to exclude (can be used multiple times)",
    ),
    name_regex: str | None = typer.Option(
        None,
        "--name-regex",
        "-N",
        help="Only backup repos matching this regex pattern (e.g., '^my-prefix-.*')",
    ),
    incremental: bool = typer.Option(
        False,
        "--incremental",
        "-i",
        help="Only backup repos that have changed since last backup",
    ),
    include_issues: bool = typer.Option(
        False,
        "--include-issues",
        help="Export issues for all repositories",
    ),
    include_pulls: bool = typer.Option(
        False,
        "--include-pulls",
        help="Export pull requests for all repositories",
    ),
    include_workflows: bool = typer.Option(
        False,
        "--include-workflows",
        help="Backup GitHub Actions workflows for all repositories",
    ),
    include_releases: bool = typer.Option(
        False,
        "--include-releases",
        help="Download releases for all repositories",
    ),
    include_wikis: bool = typer.Option(
        False,
        "--include-wikis",
        help="Backup wikis for all repositories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview actions without executing",
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        help="Skip repositories that already exist locally (don't update them)",
    ),
    bare: bool = typer.Option(
        False,
        "--bare",
        help="Create bare/mirror clones (preserves all refs, branches, tags)",
    ),
    lfs: bool = typer.Option(
        False,
        "--lfs",
        help="Use Git LFS for cloning (for repos with large files)",
    ),
    max_workers: int = typer.Option(
        4,
        "--max-workers",
        "-w",
        help="Maximum number of parallel workers",
        min=1,
        max=20,
    ),
    github_host: str | None = typer.Option(
        None,
        "--github-host",
        "-H",
        help="GitHub Enterprise hostname (e.g., github.mycompany.com)",
        envvar="GITHUB_HOST",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Backup all repositories for a GitHub organization.

    "Organizations are just users with trust issues. And more repos." — schema.cx

    Example:
        farmore org github
        farmore org github --dest ./custom_backups
        farmore org myorg --include-issues --include-pulls --include-wikis
        farmore org myorg --bare --lfs  # Mirror clone with LFS support
        farmore org myorg --name-regex '^project-.*'  # Only repos matching pattern
        farmore org myorg --incremental  # Only repos changed since last backup
    """
    # Use default destination if not provided
    if dest is None:
        dest = get_default_user_dest(orgname)

    if token and token == typer.get_app_dir("farmore"):
        console.print(
            "[yellow]⚠ Warning: Passing tokens via CLI flags exposes them in shell history. "
            "Use GITHUB_TOKEN environment variable instead.[/yellow]\n"
        )

    config = Config(
        target_type=TargetType.ORG,
        target_name=orgname,
        dest=dest,
        token=token,
        visibility=visibility,
        include_forks=include_forks,
        include_archived=include_archived,
        exclude_repos=list(exclude) if exclude else None,
        name_regex=name_regex,
        incremental=incremental,
        dry_run=dry_run,
        skip_existing=skip_existing,
        bare=bare,
        lfs=lfs,
        max_workers=max_workers,
        github_host=github_host,
    )

    orchestrator = MirrorOrchestrator(config)
    summary = orchestrator.run()

    # Export additional data if requested
    if any([include_issues, include_pulls, include_workflows, include_releases, include_wikis]):
        client = GitHubAPIClient(config)
        repos = client.get_repositories()

        export_repository_data(
            client=client,
            repos=repos,
            username=orgname,
            include_issues=include_issues,
            include_pulls=include_pulls,
            include_workflows=include_workflows,
            include_releases=include_releases,
            include_wikis=include_wikis,
            token=token,
        )

    # Exit with appropriate code
    if summary.has_failures and summary.success_count == 0:
        # All operations failed
        sys.exit(1)
    # Exit 0 even if some repos failed but were reported
    sys.exit(0)


@app.command()
def profile(
    username: str | None = typer.Argument(None, help="GitHub username (omit for authenticated user)"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for profile export (default: backups/<username>/profile.{json|yaml})",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format: json or yaml",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export GitHub user profile information.

    "Identity is just metadata. But it's YOUR metadata." — schema.cx

    Example:
        farmore profile
        farmore profile miztizm
        farmore profile miztizm --dest ./custom_profile.yaml --format yaml
    """
    if format.lower() not in ["json", "yaml"]:
        console.print("[red]❌ Error: Format must be 'json' or 'yaml'[/red]")
        sys.exit(1)

    # Create a minimal config just for API client
    config = Config(
        target_type=TargetType.USER,
        target_name=username or "me",
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        user_profile = client.get_user_profile(username)

        # Use default destination if not provided
        if dest is None:
            dest = get_default_profile_dest(user_profile.login, format.lower())

        # Convert to dict
        profile_dict = {
            "login": user_profile.login,
            "name": user_profile.name,
            "email": user_profile.email,
            "bio": user_profile.bio,
            "company": user_profile.company,
            "location": user_profile.location,
            "blog": user_profile.blog,
            "twitter_username": user_profile.twitter_username,
            "public_repos": user_profile.public_repos,
            "public_gists": user_profile.public_gists,
            "followers": user_profile.followers,
            "following": user_profile.following,
            "created_at": user_profile.created_at,
            "updated_at": user_profile.updated_at,
            "hireable": user_profile.hireable,
            "avatar_url": user_profile.avatar_url,
            "html_url": user_profile.html_url,
        }

        # Save to file
        dest.parent.mkdir(parents=True, exist_ok=True)
        if format.lower() == "json":
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(profile_dict, f, indent=2, ensure_ascii=False)
        else:
            with open(dest, "w", encoding="utf-8") as f:
                yaml.dump(profile_dict, f, default_flow_style=False, allow_unicode=True)

        # Create profile summary table
        table = Table(title=f"👤 GitHub Profile: {user_profile.login}", border_style="cyan", show_header=False)
        table.add_column("Field", style="bold cyan", no_wrap=True)
        table.add_column("Value", style="white")

        table.add_row("Name", user_profile.name or "[dim]Not set[/dim]")
        table.add_row("Email", user_profile.email or "[dim]Not set[/dim]")
        table.add_row("Bio", user_profile.bio or "[dim]Not set[/dim]")
        table.add_row("Company", user_profile.company or "[dim]Not set[/dim]")
        table.add_row("Location", user_profile.location or "[dim]Not set[/dim]")
        table.add_row("Blog", user_profile.blog or "[dim]Not set[/dim]")
        table.add_row("Public Repos", f"[cyan]{user_profile.public_repos}[/cyan]")
        table.add_row("Followers", f"[cyan]{user_profile.followers}[/cyan]")
        table.add_row("Following", f"[cyan]{user_profile.following}[/cyan]")

        console.print()
        console.print(table)
        print_success(f"Profile exported to: {dest}")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def starred(
    username: str | None = typer.Argument(None, help="GitHub username (omit for authenticated user)"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for starred repositories (default: backups/<username>/)",
    ),
    include_forks: bool = typer.Option(
        False,
        "--include-forks",
        help="Include forked repositories",
    ),
    include_archived: bool = typer.Option(
        False,
        "--include-archived",
        help="Include archived repositories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview actions without executing",
    ),
    max_workers: int = typer.Option(
        4,
        "--max-workers",
        "-w",
        help="Maximum number of parallel workers",
        min=1,
        max=20,
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Mirror all repositories starred by a user.

    "Stars are just bookmarks. But they tell a story." — schema.cx

    Example:
        farmore starred
        farmore starred miztizm
        farmore starred miztizm --dest ./custom_starred
    """
    # Need to get the actual username first to determine default dest
    # Create a temporary config to fetch the username
    temp_config = Config(
        target_type=TargetType.USER,
        target_name=username or "me",
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(temp_config)
        # Get starred repositories (this also gives us the authenticated username if needed)
        repos = client.get_starred_repositories(username)

        # Determine the actual username for default destination
        if username is None:
            # Get authenticated user's profile to get the username
            user_profile = client.get_user_profile(None)
            actual_username = user_profile.login
        else:
            actual_username = username

        # Use default destination if not provided
        if dest is None:
            dest = get_default_user_dest(actual_username)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

    config = Config(
        target_type=TargetType.USER,
        target_name=actual_username,
        dest=dest,
        token=token,
        include_forks=include_forks,
        include_archived=include_archived,
        dry_run=dry_run,
        max_workers=max_workers,
        repository_category=RepositoryCategory.STARRED,
    )

    try:
        # Apply filters (repos already fetched above)
        client = GitHubAPIClient(config)
        repos = client._filter_repositories(repos)

        if not repos:
            console.print("\n[yellow]⚠️  No starred repositories found after filtering[/yellow]")
            sys.exit(0)

        # Use the mirror orchestrator to clone/update repos
        from .mirror import MirrorOrchestrator
        orchestrator = MirrorOrchestrator(config)

        # Run with the custom repos list
        summary = orchestrator.run(repos=repos)

        # Exit with appropriate code
        if summary.has_failures and summary.success_count == 0:
            sys.exit(1)
        sys.exit(0)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def watched(
    username: str | None = typer.Argument(None, help="GitHub username (omit for authenticated user)"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for watched repositories (default: backups/<username>/)",
    ),
    include_forks: bool = typer.Option(
        False,
        "--include-forks",
        help="Include forked repositories",
    ),
    include_archived: bool = typer.Option(
        False,
        "--include-archived",
        help="Include archived repositories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview actions without executing",
    ),
    max_workers: int = typer.Option(
        4,
        "--max-workers",
        "-w",
        help="Maximum number of parallel workers",
        min=1,
        max=20,
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Mirror all repositories watched by a user.

    "Watching is caring. Or stalking. Depends on perspective." — schema.cx

    Example:
        farmore watched
        farmore watched miztizm
        farmore watched miztizm --dest ./custom_watched
    """
    # Need to get the actual username first to determine default dest
    temp_config = Config(
        target_type=TargetType.USER,
        target_name=username or "me",
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(temp_config)
        # Get watched repositories
        repos = client.get_watched_repositories(username)

        # Determine the actual username for default destination
        if username is None:
            user_profile = client.get_user_profile(None)
            actual_username = user_profile.login
        else:
            actual_username = username

        # Use default destination if not provided
        if dest is None:
            dest = get_default_user_dest(actual_username)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

    config = Config(
        target_type=TargetType.USER,
        target_name=actual_username,
        dest=dest,
        token=token,
        include_forks=include_forks,
        include_archived=include_archived,
        dry_run=dry_run,
        max_workers=max_workers,
        repository_category=RepositoryCategory.WATCHED,
    )

    try:
        # Apply filters (repos already fetched above)
        client = GitHubAPIClient(config)
        repos = client._filter_repositories(repos)

        if not repos:
            console.print("\n[yellow]⚠️  No watched repositories found after filtering[/yellow]")
            sys.exit(0)

        # Use the mirror orchestrator to clone/update repos
        from .mirror import MirrorOrchestrator
        orchestrator = MirrorOrchestrator(config)

        # Run with the custom repos list
        summary = orchestrator.run(repos=repos)

        # Exit with appropriate code
        if summary.has_failures and summary.success_count == 0:
            sys.exit(1)
        sys.exit(0)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def secrets(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for secrets export (default: backups/<owner>/secrets/<owner>_<repo>_secrets.{json|yaml})",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format: json or yaml",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export repository secrets (names only, not values).

    "Secrets are meant to be kept. But their names? Those we can share." — schema.cx

    ⚠️  Note: GitHub API does NOT expose secret values, only names and metadata.

    Example:
        farmore secrets miztizm/farmore
        farmore secrets miztizm/hello-world --format yaml
        farmore secrets miztizm/farmore --dest ./custom_secrets.json
    """
    if format.lower() not in ["json", "yaml"]:
        console.print("[red]❌ Error: Format must be 'json' or 'yaml'[/red]")
        sys.exit(1)

    # Parse owner/repo
    parts = repository.split("/")
    if len(parts) != 2:
        console.print("[red]❌ Error: Repository must be in format 'owner/repo'[/red]")
        sys.exit(1)

    owner, repo = parts

    # Use default destination if not provided
    if dest is None:
        dest = get_default_secrets_dest(owner, repo, format.lower())

    # Create a minimal config just for API client
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        repo_secrets = client.get_repository_secrets(owner, repo)

        # Convert to dict
        secrets_dict = {
            "repository": repository,
            "total_secrets": len(repo_secrets),
            "secrets": [
                {
                    "name": s.name,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                }
                for s in repo_secrets
            ],
        }

        # Save to file
        dest.parent.mkdir(parents=True, exist_ok=True)
        if format.lower() == "json":
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(secrets_dict, f, indent=2, ensure_ascii=False)
        else:
            with open(dest, "w", encoding="utf-8") as f:
                yaml.dump(secrets_dict, f, default_flow_style=False, allow_unicode=True)

        # Create secrets table
        if repo_secrets:
            table = Table(title=f"🔐 Repository Secrets: {repository}", border_style="cyan")
            table.add_column("Secret Name", style="bold yellow", no_wrap=True)
            table.add_column("Created", style="dim")
            table.add_column("Updated", style="dim")

            for secret in repo_secrets:
                table.add_row(secret.name, secret.created_at[:10], secret.updated_at[:10])

            console.print()
            console.print(table)
        else:
            print_info(f"No secrets found for {repository}")

        print_success(f"Secrets exported to: {dest}")
        console.print(f"   [dim]Total secrets: {len(repo_secrets)}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def delete(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Delete a GitHub repository.

    "Deletion is permanent. There's no undo button in the cloud." — schema.cx

    ⚠️  WARNING: This action is IRREVERSIBLE! Deleted repositories cannot be recovered.

    Example:
        farmore delete miztizm/testdelete
        farmore delete miztizm/testdelete --force
    """
    # Parse owner/repo
    parts = repository.split("/")
    if len(parts) != 2:
        console.print("[red]❌ Error: Repository must be in format 'owner/repo'[/red]")
        sys.exit(1)

    owner, repo = parts

    # Safety check: Confirm deletion unless --force is used
    if not force:
        console.print(f"\n[red]⚠️  WARNING: You are about to DELETE the repository '{repository}'[/red]")
        console.print("[red]   This action is IRREVERSIBLE and cannot be undone![/red]")
        console.print(f"\n   Repository: {repository}")
        console.print(f"   Owner: {owner}")
        console.print(f"   Name: {repo}\n")

        confirm = typer.confirm("Are you absolutely sure you want to delete this repository?")
        if not confirm:
            console.print("\n[yellow]❌ Deletion cancelled[/yellow]")
            sys.exit(0)

        # Double confirmation
        confirm2 = typer.confirm(f"Type the repository name '{repo}' to confirm deletion", default=False)
        if not confirm2:
            console.print("\n[yellow]❌ Deletion cancelled[/yellow]")
            sys.exit(0)

    # Create a minimal config just for API client
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        success = client.delete_repository(owner, repo)

        if success:
            console.print(f"\n[green]✅ Repository '{repository}' has been deleted[/green]")
            sys.exit(0)
        else:
            console.print(f"\n[red]❌ Failed to delete repository '{repository}'[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def repo(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory (default: backups/<owner>/repos/public/<owner>/<repo>)",
    ),
    include_issues: bool = typer.Option(
        False,
        "--include-issues",
        help="Export issues for this repository",
    ),
    include_pulls: bool = typer.Option(
        False,
        "--include-pulls",
        help="Export pull requests for this repository",
    ),
    include_workflows: bool = typer.Option(
        False,
        "--include-workflows",
        help="Backup GitHub Actions workflows for this repository",
    ),
    include_releases: bool = typer.Option(
        False,
        "--include-releases",
        help="Download releases for this repository",
    ),
    include_wikis: bool = typer.Option(
        False,
        "--include-wikis",
        help="Backup wiki for this repository",
    ),
    all: bool = typer.Option(
        False,
        "--all",
        help="Include all data types (issues, PRs, workflows, releases, wikis)",
    ),
    use_ssh: bool = typer.Option(
        True,
        "--use-ssh/--no-use-ssh",
        help="Use SSH for cloning (default: True)",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Backup a single GitHub repository with optional data exports.

    "One repo at a time. Like eating chips — you can't stop at just one." — schema.cx

    Example:
        farmore repo microsoft/vscode
        farmore repo miztizm/hello-world --include-issues --include-pulls
        farmore repo myorg/myrepo --all
        farmore repo python/cpython --dest ./my-backups --include-wikis
    """
    # Parse owner/repo
    parts = repository.split("/")
    if len(parts) != 2:
        console.print("[red]❌ Error: Repository must be in format 'owner/repo'[/red]")
        sys.exit(1)

    owner, repo_name = parts

    # If --all flag is set, enable all data exports
    if all:
        include_issues = True
        include_pulls = True
        include_workflows = True
        include_releases = True
        include_wikis = True

    # Determine destination for repository clone
    if dest is None:
        # Use default structure: backups/<owner>/repos/public/<owner>/<repo>
        dest = Path("backups") / owner / "repos" / "public" / owner / repo_name

    console.print(f"\n📦 Backing up repository: {repository}")

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)

        # Get repository info
        console.print(f"   Fetching repository information...")
        repo_info = client.get_repository(owner, repo_name)

        if not repo_info:
            console.print(f"[red]❌ Repository not found: {repository}[/red]")
            sys.exit(1)

        # Clone or update the repository
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists() and GitOperations.is_git_repository(dest):
            console.print(f"   Repository already exists, updating...")
            result = GitOperations.pull(dest)
            if result[0]:
                console.print(f"[green]✅ Repository updated: {dest}[/green]")
            else:
                console.print(f"[yellow]⚠️  Update failed: {result[1]}[/yellow]")
        else:
            console.print(f"   Cloning repository...")
            result = GitOperations.clone(repo_info, dest, use_ssh=use_ssh)
            if result[0]:
                console.print(f"[green]✅ Repository cloned: {dest}[/green]")
            else:
                console.print(f"[red]❌ Clone failed: {result[1]}[/red]")
                sys.exit(1)

        # Export additional data if requested
        if any([include_issues, include_pulls, include_workflows, include_releases, include_wikis]):
            console.print(f"\n📊 Exporting additional data...")

            export_repository_data(
                client=client,
                repos=[repo_info],
                username=owner,
                include_issues=include_issues,
                include_pulls=include_pulls,
                include_workflows=include_workflows,
                include_releases=include_releases,
                include_wikis=include_wikis,
                token=token,
            )

        console.print(f"\n[green]✅ Backup complete for: {repository}[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


@app.command()
def issues(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for issues export (default: backups/<owner>/data/issues/<owner>_<repo>_issues.json)",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or yaml",
    ),
    state: str = typer.Option(
        "all",
        "--state",
        "-s",
        help="Filter by state: open, closed, or all",
    ),
    include_comments: bool = typer.Option(
        False,
        "--include-comments",
        help="Include issue comments in export",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export all issues from a GitHub repository.

    "Issues are just TODOs that escaped into the wild." — schema.cx

    Example:
        farmore issues miztizm/hello-world
        farmore issues miztizm/farmore --state open --include-comments
        farmore issues miztizm/farmore --dest ./my-issues.json --format yaml
    """
    # Parse owner/repo
    parts = repository.split("/")
    if len(parts) != 2:
        console.print("[red]❌ Error: Repository must be in format 'owner/repo'[/red]")
        sys.exit(1)

    owner, repo = parts

    # Determine destination
    if dest is None:
        dest = get_default_issues_dest(owner, repo, format)

    # Create parent directory
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        issues_list = client.get_issues(owner, repo, state=state, include_comments=include_comments)

        # Convert to dict for export
        issues_data = {
            "repository": repository,
            "total_issues": len(issues_list),
            "state_filter": state,
            "exported_at": datetime.now().isoformat(),
            "issues": [
                {
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "user": issue.user,
                    "body": issue.body,
                    "labels": issue.labels,
                    "assignees": issue.assignees,
                    "created_at": issue.created_at,
                    "updated_at": issue.updated_at,
                    "closed_at": issue.closed_at,
                    "comments_count": issue.comments_count,
                    "html_url": issue.html_url,
                    "comments": issue.comments if include_comments else [],
                }
                for issue in issues_list
            ],
        }

        # Export to file
        if format == "yaml":
            with open(dest, "w") as f:
                yaml.dump(issues_data, f, default_flow_style=False, sort_keys=False)
        else:
            with open(dest, "w") as f:
                json.dump(issues_data, f, indent=2)

        # Create summary table
        table = Table(title=f"📋 Issues Export Summary: {repository}", border_style="cyan")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")

        table.add_row("Total Issues", f"[cyan]{len(issues_list)}[/cyan]")
        table.add_row("State Filter", state)
        table.add_row("Format", format)
        table.add_row("Exported To", str(dest))

        console.print()
        console.print(table)
        print_success("Issues exported successfully")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


@app.command()
def pulls(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for pull requests export (default: backups/<owner>/data/pulls/<owner>_<repo>_pulls.json)",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or yaml",
    ),
    state: str = typer.Option(
        "all",
        "--state",
        "-s",
        help="Filter by state: open, closed, or all",
    ),
    include_comments: bool = typer.Option(
        False,
        "--include-comments",
        help="Include PR comments in export",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export all pull requests from a GitHub repository.

    "Pull requests: where code goes to be judged by its peers." — schema.cx

    Example:
        farmore pulls miztizm/hello-world
        farmore pulls miztizm/farmore --state open --include-comments
        farmore pulls miztizm/farmore --dest ./my-prs.json --format yaml
    """
    # Parse owner/repo
    parts = repository.split("/")
    if len(parts) != 2:
        console.print("[red]❌ Error: Repository must be in format 'owner/repo'[/red]")
        sys.exit(1)

    owner, repo = parts

    # Determine destination
    if dest is None:
        dest = get_default_pulls_dest(owner, repo, format)

    # Create parent directory
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        prs_list = client.get_pull_requests(owner, repo, state=state, include_comments=include_comments)

        # Convert to dict for export
        prs_data = {
            "repository": repository,
            "total_pull_requests": len(prs_list),
            "state_filter": state,
            "exported_at": datetime.now().isoformat(),
            "pull_requests": [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "user": pr.user,
                    "body": pr.body,
                    "labels": pr.labels,
                    "assignees": pr.assignees,
                    "created_at": pr.created_at,
                    "updated_at": pr.updated_at,
                    "closed_at": pr.closed_at,
                    "merged_at": pr.merged_at,
                    "merged": pr.merged,
                    "draft": pr.draft,
                    "head_ref": pr.head_ref,
                    "base_ref": pr.base_ref,
                    "commits_count": pr.commits_count,
                    "comments_count": pr.comments_count,
                    "review_comments_count": pr.review_comments_count,
                    "html_url": pr.html_url,
                    "diff_url": pr.diff_url,
                    "patch_url": pr.patch_url,
                    "comments": pr.comments if include_comments else [],
                }
                for pr in prs_list
            ],
        }

        # Export to file
        if format == "yaml":
            with open(dest, "w") as f:
                yaml.dump(prs_data, f, default_flow_style=False, sort_keys=False)
        else:
            with open(dest, "w") as f:
                json.dump(prs_data, f, indent=2)

        # Create summary table
        table = Table(title=f"🔀 Pull Requests Export Summary: {repository}", border_style="cyan")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")

        table.add_row("Total PRs", f"[cyan]{len(prs_list)}[/cyan]")
        table.add_row("State Filter", state)
        table.add_row("Format", format)
        table.add_row("Exported To", str(dest))

        console.print()
        console.print(table)
        print_success("Pull requests exported successfully")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def workflows(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for workflows backup (default: backups/<owner>/data/workflows/<owner>_<repo>/)",
    ),
    include_runs: bool = typer.Option(
        False,
        "--include-runs",
        help="Include workflow runs history",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Backup GitHub Actions workflows from a repository.

    "Automation is just laziness with a good PR." — schema.cx

    Example:
        farmore workflows miztizm/hello-world
        farmore workflows miztizm/farmore --include-runs
        farmore workflows miztizm/farmore --dest ./my-workflows/
    """
    # Parse owner/repo
    parts = repository.split("/")
    if len(parts) != 2:
        console.print("[red]❌ Error: Repository must be in format 'owner/repo'[/red]")
        sys.exit(1)

    owner, repo = parts

    # Determine destination
    if dest is None:
        dest = get_default_workflows_dest(owner, repo)

    # Create directory
    dest.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        workflows_list, workflow_files = client.get_workflows(owner, repo)

        if not workflows_list:
            console.print(f"\n[yellow]⚠️  No workflows found for {repository}[/yellow]")
            sys.exit(0)

        # Save workflow files
        for wf_file in workflow_files:
            file_path = dest / Path(wf_file["path"]).name
            with open(file_path, "w") as f:
                f.write(wf_file["content"])

        # Save metadata
        metadata = {
            "repository": repository,
            "total_workflows": len(workflows_list),
            "exported_at": datetime.now().isoformat(),
            "workflows": [
                {
                    "name": wf.name,
                    "path": wf.path,
                    "state": wf.state,
                    "created_at": wf.created_at,
                    "updated_at": wf.updated_at,
                    "html_url": wf.html_url,
                    "badge_url": wf.badge_url,
                }
                for wf in workflows_list
            ],
        }

        # Include workflow runs if requested
        if include_runs:
            runs = client.get_workflow_runs(owner, repo, limit=100)
            metadata["workflow_runs"] = [
                {
                    "id": run.id,
                    "name": run.name,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "event": run.event,
                    "created_at": run.created_at,
                    "run_number": run.run_number,
                    "html_url": run.html_url,
                }
                for run in runs
            ]

        # Save metadata
        metadata_path = dest / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        console.print(f"\n[green]✅ Workflows backed up to: {dest}[/green]")
        console.print(f"   Repository: {repository}")
        console.print(f"   Total workflows: {len(workflows_list)}")
        console.print(f"   Workflow files saved: {len(workflow_files)}")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def releases(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for releases backup (default: backups/<owner>/data/releases/<owner>_<repo>/)",
    ),
    download_assets: bool = typer.Option(
        False,
        "--download-assets",
        help="Download release assets (binaries, archives, etc.)",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Download all releases and assets from a GitHub repository.

    "Releases are just commits with marketing." — schema.cx

    Example:
        farmore releases miztizm/hello-world
        farmore releases miztizm/farmore --download-assets
        farmore releases miztizm/farmore --dest ./my-releases/
    """
    # Parse owner/repo
    parts = repository.split("/")
    if len(parts) != 2:
        console.print("[red]❌ Error: Repository must be in format 'owner/repo'[/red]")
        sys.exit(1)

    owner, repo = parts

    # Determine destination
    if dest is None:
        dest = get_default_releases_dest(owner, repo)

    # Create directory
    dest.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        releases_list = client.get_releases(owner, repo)

        if not releases_list:
            console.print(f"\n[yellow]⚠️  No releases found for {repository}[/yellow]")
            sys.exit(0)

        # Save metadata for all releases
        metadata = {
            "repository": repository,
            "total_releases": len(releases_list),
            "exported_at": datetime.now().isoformat(),
            "releases": [
                {
                    "id": release.id,
                    "tag_name": release.tag_name,
                    "name": release.name,
                    "body": release.body,
                    "draft": release.draft,
                    "prerelease": release.prerelease,
                    "created_at": release.created_at,
                    "published_at": release.published_at,
                    "author": release.author,
                    "html_url": release.html_url,
                    "assets": release.assets,
                }
                for release in releases_list
            ],
        }

        metadata_path = dest / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Download assets if requested
        if download_assets:
            console.print(f"\n📦 Downloading release assets...")

            for release in releases_list:
                if not release.assets:
                    continue

                # Create directory for this release
                release_dir = dest / release.tag_name
                release_dir.mkdir(parents=True, exist_ok=True)

                # Save release metadata
                release_metadata = {
                    "tag_name": release.tag_name,
                    "name": release.name,
                    "body": release.body,
                    "created_at": release.created_at,
                    "published_at": release.published_at,
                    "author": release.author,
                    "html_url": release.html_url,
                }
                with open(release_dir / "release.json", "w") as f:
                    json.dump(release_metadata, f, indent=2)

                # Download each asset
                for asset in release.assets:
                    asset_path = release_dir / asset["name"]
                    console.print(f"   Downloading: {asset['name']} ({asset['size']} bytes)")

                    # Download with progress
                    response = requests.get(asset["browser_download_url"], stream=True)
                    response.raise_for_status()

                    with open(asset_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

        console.print(f"\n[green]✅ Releases backed up to: {dest}[/green]")
        console.print(f"   Repository: {repository}")
        console.print(f"   Total releases: {len(releases_list)}")
        if download_assets:
            total_assets = sum(len(r.assets) for r in releases_list)
            console.print(f"   Assets downloaded: {total_assets}")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def wiki(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for wiki backup (default: backups/<owner>/data/wikis/<owner>_<repo>.wiki/)",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Backup a repository's wiki (if it exists).

    "Wikis are where documentation goes to die. But at least it's organized." — schema.cx

    Example:
        farmore wiki miztizm/hello-world
        farmore wiki miztizm/farmore --dest ./my-wiki/
    """
    # Parse owner/repo
    parts = repository.split("/")
    if len(parts) != 2:
        console.print("[red]❌ Error: Repository must be in format 'owner/repo'[/red]")
        sys.exit(1)

    owner, repo = parts

    # Determine destination
    if dest is None:
        dest = get_default_wiki_dest(owner, repo)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)

        # Check if wiki exists
        has_wiki = client.check_wiki_exists(owner, repo)

        if not has_wiki:
            console.print(f"\n[yellow]⚠️  Repository {repository} does not have a wiki enabled[/yellow]")
            sys.exit(0)

        console.print(f"\n📚 Cloning wiki for repository: {repository}")

        # Wiki URL
        wiki_url = f"https://github.com/{owner}/{repo}.wiki.git"

        # Create parent directory
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Clone or update wiki using git directly
        if dest.exists():
            console.print(f"   Wiki already exists, updating...")
            try:
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=dest,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                )
                console.print(f"[green]✅ Wiki updated: {dest}[/green]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]❌ Failed to update wiki: {e.stderr}[/red]")
                sys.exit(1)
        else:
            console.print(f"   Cloning wiki...")
            try:
                result = subprocess.run(
                    ["git", "clone", wiki_url, str(dest)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=300,
                )
                console.print(f"[green]✅ Wiki cloned to: {dest}[/green]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]❌ Failed to clone wiki: {e.stderr}[/red]")
                sys.exit(1)

        console.print(f"   Repository: {repository}")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search keyword or phrase (e.g., 'smsbomber', 'machine learning')"),
    limit: int = typer.Option(10, "--limit", "-l", min=1, max=100, help="Maximum number of repositories to clone (1-100)"),
    language: str | None = typer.Option(None, "--language", help="Filter by programming language (e.g., 'python', 'javascript')"),
    min_stars: int | None = typer.Option(None, "--min-stars", help="Minimum number of stars required"),
    sort: str = typer.Option(
        "best-match",
        "--sort",
        help="Sort order: 'stars', 'forks', 'updated', or 'best-match'",
        case_sensitive=False,
    ),
    order: str = typer.Option("desc", "--order", help="Sort direction: 'asc' or 'desc'", case_sensitive=False),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt and proceed automatically"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Custom output directory for cloned repositories"),
    flat_structure: bool = typer.Option(False, "--flat-structure", help="Clone repos directly without owner subdirectories"),
    token: str | None = typer.Option(None, "--token", "-t", envvar="GITHUB_TOKEN", help="GitHub personal access token"),
    max_workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel workers for cloning"),
) -> None:
    """
    🔍 Search for GitHub repositories and clone/mirror the results.

    Search GitHub repositories by keyword and clone the matching results to a local directory.
    Supports filtering by language, stars, and sorting options.

    Examples:

        # Search for "smsbomber" and clone top 10 results
        farmore search "smsbomber" --limit 10

        # Search with multiple filters
        farmore search "machine learning" --language python --min-stars 1000 --limit 20

        # Search and auto-confirm (skip prompt)
        farmore search "react components" --limit 5 --yes

        # Search with custom output directory
        farmore search "awesome-python" --output-dir ./my-collections --limit 15

        # Search with flat structure (no owner subdirectories)
        farmore search "cli tools" --flat-structure --limit 10
    """
    # Validate sort option
    valid_sorts = ["best-match", "stars", "forks", "updated"]
    if sort.lower() not in valid_sorts:
        print_error(f"Invalid sort option: {sort}. Must be one of: {', '.join(valid_sorts)}")
        sys.exit(1)

    # Validate order option
    valid_orders = ["asc", "desc"]
    if order.lower() not in valid_orders:
        print_error(f"Invalid order option: {order}. Must be one of: {', '.join(valid_orders)}")
        sys.exit(1)

    # Determine output directory
    if output_dir is None:
        sanitized_query = sanitize_query_for_dirname(query)
        output_dir = Path("search-results") / sanitized_query
    else:
        output_dir = Path(output_dir)

    # Create a temporary config for API client
    temp_config = Config(
        target_type=TargetType.USER,
        target_name="search",  # Placeholder, not used for search
        dest=output_dir,
        token=token,
        max_workers=max_workers,
    )

    try:
        # Initialize GitHub API client
        client = GitHubAPIClient(temp_config)

        # Perform search
        repos = client.search_repositories(
            query=query,
            language=language,
            min_stars=min_stars,
            sort=sort.lower(),
            order=order.lower(),
            limit=limit,
        )

        # Check if we got any results
        if not repos:
            console.print("\n[yellow]No repositories to clone.[/yellow]")
            sys.exit(0)

        # Display results in a Rich table
        from .rich_utils import create_data_table

        table = create_data_table(title=f"🔍 Search Results: '{query}'", show_lines=False)
        table.add_column("Repository", style="bold blue", no_wrap=True)
        table.add_column("Owner", style="cyan")
        table.add_column("⭐ Stars", justify="right", style="yellow")
        table.add_column("🍴 Forks", justify="right", style="green")
        table.add_column("Language", style="magenta")
        table.add_column("Description", style="dim", max_width=50)

        # We need to fetch additional metadata for stars/forks/description
        # For now, we'll make individual API calls (could be optimized)
        console.print("\n[cyan]📊 Fetching repository details...[/cyan]")

        for repo in repos:
            # Get full repository details
            try:
                full_repo_data = client.session.get(
                    f"{client.BASE_URL}/repos/{repo.full_name}",
                    timeout=10,
                ).json()

                stars = full_repo_data.get("stargazers_count", 0)
                forks = full_repo_data.get("forks_count", 0)
                lang = full_repo_data.get("language") or "N/A"
                desc = full_repo_data.get("description") or ""

                # Truncate description
                if len(desc) > 50:
                    desc = desc[:47] + "..."

                table.add_row(
                    repo.name,
                    repo.owner,
                    f"{stars:,}",
                    f"{forks:,}",
                    lang,
                    desc,
                )
            except Exception:
                # If we can't fetch details, show basic info
                table.add_row(repo.name, repo.owner, "?", "?", "?", "")

        console.print(table)

        # Show summary
        console.print(f"\n[cyan]📦 Found {len(repos)} repositories to clone[/cyan]")
        console.print(f"[dim]Output directory: {output_dir.absolute()}[/dim]")

        # Confirmation prompt (unless --yes flag is provided)
        if not yes:
            proceed = typer.confirm(f"\nClone {len(repos)} repositories to {output_dir}?", default=False)
            if not proceed:
                console.print("\n[yellow]Operation cancelled.[/yellow]")
                sys.exit(0)

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Handle flat structure by modifying repository local_path
        if flat_structure:
            # Check for naming conflicts
            repo_names = [repo.name for repo in repos]
            duplicates = [name for name in repo_names if repo_names.count(name) > 1]

            if duplicates:
                console.print(
                    f"\n[yellow]⚠️  Warning: Found {len(set(duplicates))} repository name(s) "
                    f"with conflicts in flat structure mode:[/yellow]"
                )
                for dup_name in set(duplicates):
                    owners = [repo.owner for repo in repos if repo.name == dup_name]
                    console.print(f"  [dim]• {dup_name}: {', '.join(owners)}[/dim]")

                console.print(
                    "\n[yellow]Repositories with duplicate names will have their owner "
                    "appended (e.g., 'repo-owner')[/yellow]"
                )

            # Create modified repositories with flat paths
            from dataclasses import replace
            modified_repos = []
            name_counts: dict[str, int] = {}

            for repo in repos:
                # Track how many times we've seen this repo name
                if repo.name in name_counts:
                    name_counts[repo.name] += 1
                    # Append owner to make it unique
                    modified_name = f"{repo.name}-{repo.owner}"
                else:
                    name_counts[repo.name] = 1
                    # Check if this name will have duplicates
                    if repo.name in duplicates:
                        modified_name = f"{repo.name}-{repo.owner}"
                    else:
                        modified_name = repo.name

                # Create a modified repository with updated name for flat structure
                modified_repo = replace(repo, name=modified_name, owner="")
                modified_repos.append(modified_repo)

            repos = modified_repos

        # Create a proper config for mirroring
        mirror_config = Config(
            target_type=TargetType.USER,
            target_name="search",  # Placeholder
            dest=output_dir,
            token=token,
            max_workers=max_workers,
            include_forks=True,  # Include all search results
            include_archived=True,  # Include all search results
            disable_categorization=True,  # Disable category subdirectories for search results
        )

        # Use MirrorOrchestrator to clone the repositories
        console.print(f"\n[cyan]🚀 Starting clone operation...[/cyan]")

        orchestrator = MirrorOrchestrator(mirror_config)
        summary = orchestrator.run(repos=repos)

        # Display final summary (already handled by MirrorOrchestrator)
        if summary.has_failures:
            console.print(f"\n[yellow]⚠️  Completed with {summary.failed} failures[/yellow]")
            sys.exit(1)
        else:
            console.print(f"\n[green]✅ All repositories cloned successfully![/green]")

    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Search failed: {e}")
        if "--debug" in sys.argv:
            traceback.print_exc()
        sys.exit(1)


@app.command()
def gists(
    username: str | None = typer.Argument(None, help="GitHub username (omit for authenticated user)"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for gists backup (default: backups/<username>/gists/)",
    ),
    include_starred: bool = typer.Option(
        False,
        "--starred",
        help="Also backup starred gists",
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        help="Skip gists that already exist locally",
    ),
    github_host: str | None = typer.Option(
        None,
        "--github-host",
        "-H",
        help="GitHub Enterprise hostname (e.g., github.mycompany.com)",
        envvar="GITHUB_HOST",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Backup all gists for a user.

    "Gists are just repos that didn't make the cut. But they still deserve a backup." — schema.cx

    Gists are cloned as git repositories, preserving their full history.

    Example:
        farmore gists
        farmore gists miztizm
        farmore gists miztizm --starred  # Include starred gists
        farmore gists --dest ./my-gists --skip-existing
    """
    from .gists import GistsBackup

    # Determine destination
    if dest is None:
        dest = Path("backups") / (username or "me") / "gists"

    console.print(f"\n[cyan]📝 Backing up gists...[/cyan]")
    if github_host:
        console.print(f"   [dim]GitHub Enterprise: {github_host}[/dim]")

    try:
        with GistsBackup(token=token, github_host=github_host, dest=dest.parent) as backup:
            summary = backup.backup_user_gists(
                username=username,
                include_starred=include_starred,
                skip_existing=skip_existing,
            )

        # Display summary
        table = Table(title="📝 Gists Backup Summary", border_style="cyan")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")

        table.add_row("Total Gists", f"[cyan]{summary['total']}[/cyan]")
        table.add_row("Cloned", f"[green]{summary['cloned']}[/green]")
        table.add_row("Updated", f"[blue]{summary['updated']}[/blue]")
        table.add_row("Skipped", f"[dim]{summary['skipped']}[/dim]")
        table.add_row("Failed", f"[red]{summary['failed']}[/red]" if summary['failed'] else "[green]0[/green]")
        table.add_row("Destination", str(dest))

        console.print()
        console.print(table)

        if summary['errors']:
            console.print("\n[red]Errors:[/red]")
            for error in summary['errors'][:5]:  # Show first 5 errors
                console.print(f"   [red]• {error}[/red]")
            if len(summary['errors']) > 5:
                console.print(f"   [dim]... and {len(summary['errors']) - 5} more errors[/dim]")

        if summary['failed'] > 0 and summary['cloned'] == 0 and summary['updated'] == 0:
            sys.exit(1)

        print_success("Gists backup complete!")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


@app.command()
def attachments(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination directory for attachments (default: backups/<owner>/<repo>/attachments/)",
    ),
    source: str = typer.Option(
        "all",
        "--source",
        "-s",
        help="Source to extract from: 'issues', 'pulls', or 'all'",
    ),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--no-skip-existing",
        help="Skip attachments that already exist locally",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Download attachments (images, files) from issues and pull requests.

    "Every picture tells a story. Make sure you back it up." — schema.cx

    This command extracts and downloads all user-uploaded files from GitHub
    issues and pull requests, including images, documents, and other attachments.

    Example:
        farmore attachments miztizm/farmore
        farmore attachments myorg/myrepo --source issues
        farmore attachments myorg/myrepo --source pulls --dest ./my-attachments
    """
    from .attachments import AttachmentDownloader

    # Parse owner/repo
    try:
        owner, repo = validate_repository_format(repository)
    except ValueError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

    # Validate source option
    if source.lower() not in ["issues", "pulls", "all"]:
        console.print("[red]❌ Error: Source must be 'issues', 'pulls', or 'all'[/red]")
        sys.exit(1)

    # Determine destination
    if dest is None:
        dest = Path("backups") / owner / repo

    console.print(f"\n[cyan]📎 Downloading attachments for: {repository}[/cyan]")
    console.print(f"   [dim]Source: {source}[/dim]")
    console.print(f"   [dim]Destination: {dest}[/dim]")

    # Create config for API client
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=dest,
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        total_downloaded = 0
        total_failed = 0
        total_skipped = 0

        with AttachmentDownloader(token=token, dest=dest) as downloader:
            # Download from issues
            if source.lower() in ["issues", "all"]:
                issues_list = client.get_issues(owner, repo, state="all", include_comments=True)
                issues_data = [
                    {
                        "number": issue.number,
                        "body": issue.body,
                        "comments": issue.comments,
                    }
                    for issue in issues_list
                ]

                manifest = downloader.download_from_issues(
                    owner=owner,
                    repo=repo,
                    issues=issues_data,
                    skip_existing=skip_existing,
                )

                total_downloaded += manifest.total_downloaded
                total_failed += manifest.total_failed
                total_skipped += manifest.total_skipped

                console.print(f"\n   [green]✓ Issues: {manifest.total_downloaded} downloaded, "
                              f"{manifest.total_skipped} skipped, {manifest.total_failed} failed[/green]")

            # Download from pull requests
            if source.lower() in ["pulls", "all"]:
                prs_list = client.get_pull_requests(owner, repo, state="all", include_comments=True)
                prs_data = [
                    {
                        "number": pr.number,
                        "body": pr.body,
                        "comments": pr.comments,
                    }
                    for pr in prs_list
                ]

                manifest = downloader.download_from_pull_requests(
                    owner=owner,
                    repo=repo,
                    pull_requests=prs_data,
                    skip_existing=skip_existing,
                )

                total_downloaded += manifest.total_downloaded
                total_failed += manifest.total_failed
                total_skipped += manifest.total_skipped

                console.print(f"\n   [green]✓ Pull Requests: {manifest.total_downloaded} downloaded, "
                              f"{manifest.total_skipped} skipped, {manifest.total_failed} failed[/green]")

        # Display summary
        table = Table(title="📎 Attachments Download Summary", border_style="cyan")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")

        table.add_row("Repository", repository)
        table.add_row("Downloaded", f"[green]{total_downloaded}[/green]")
        table.add_row("Skipped", f"[dim]{total_skipped}[/dim]")
        table.add_row("Failed", f"[red]{total_failed}[/red]" if total_failed else "[green]0[/green]")
        table.add_row("Destination", str(dest))

        console.print()
        console.print(table)

        if total_failed > 0 and total_downloaded == 0:
            sys.exit(1)

        print_success("Attachments download complete!")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


@app.command()
def labels(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for labels export (default: backups/<owner>/data/labels/<owner>_<repo>_labels.json)",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or yaml",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export all labels from a GitHub repository.

    "Labels are just tags with prettier colors." — schema.cx

    Example:
        farmore labels miztizm/farmore
        farmore labels myorg/myrepo --format yaml
        farmore labels myorg/myrepo --dest ./my-labels.json
    """
    if format.lower() not in ["json", "yaml"]:
        console.print("[red]❌ Error: Format must be 'json' or 'yaml'[/red]")
        sys.exit(1)

    # Parse owner/repo
    try:
        owner, repo = validate_repository_format(repository)
    except ValueError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

    # Determine destination
    if dest is None:
        dest = Path("backups") / owner / "data" / "labels" / f"{owner}_{repo}_labels.{format.lower()}"

    # Create parent directory
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        labels_list = client.get_labels(owner, repo)

        # Convert to dict for export
        labels_data = {
            "repository": repository,
            "total_labels": len(labels_list),
            "exported_at": datetime.now().isoformat(),
            "labels": [
                {
                    "id": label.id,
                    "name": label.name,
                    "description": label.description,
                    "color": label.color,
                }
                for label in labels_list
            ],
        }

        # Export to file
        if format.lower() == "yaml":
            with open(dest, "w") as f:
                yaml.dump(labels_data, f, default_flow_style=False, sort_keys=False)
        else:
            with open(dest, "w") as f:
                json.dump(labels_data, f, indent=2)

        # Create summary table
        if labels_list:
            table = Table(title=f"🏷️  Labels: {repository}", border_style="cyan")
            table.add_column("Name", style="bold")
            table.add_column("Color", style="cyan")
            table.add_column("Description", style="dim", max_width=50)

            for label in labels_list:
                table.add_row(
                    label.name,
                    f"#{label.color}",
                    label.description or "[dim]No description[/dim]",
                )

            console.print()
            console.print(table)

        print_success(f"Labels exported to: {dest}")
        console.print(f"   [dim]Total labels: {len(labels_list)}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


@app.command()
def milestones(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for milestones export (default: backups/<owner>/data/milestones/<owner>_<repo>_milestones.json)",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or yaml",
    ),
    state: str = typer.Option(
        "all",
        "--state",
        "-s",
        help="Filter by state: open, closed, or all",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export all milestones from a GitHub repository.

    "Milestones are just deadlines you can see coming." — schema.cx

    Example:
        farmore milestones miztizm/farmore
        farmore milestones myorg/myrepo --state open
        farmore milestones myorg/myrepo --format yaml
    """
    if format.lower() not in ["json", "yaml"]:
        console.print("[red]❌ Error: Format must be 'json' or 'yaml'[/red]")
        sys.exit(1)

    # Parse owner/repo
    try:
        owner, repo = validate_repository_format(repository)
    except ValueError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

    # Determine destination
    if dest is None:
        dest = Path("backups") / owner / "data" / "milestones" / f"{owner}_{repo}_milestones.{format.lower()}"

    # Create parent directory
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        milestones_list = client.get_milestones(owner, repo, state=state)

        # Convert to dict for export
        milestones_data = {
            "repository": repository,
            "total_milestones": len(milestones_list),
            "state_filter": state,
            "exported_at": datetime.now().isoformat(),
            "milestones": [
                {
                    "id": m.id,
                    "number": m.number,
                    "title": m.title,
                    "description": m.description,
                    "state": m.state,
                    "open_issues": m.open_issues,
                    "closed_issues": m.closed_issues,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                    "due_on": m.due_on,
                    "closed_at": m.closed_at,
                    "html_url": m.html_url,
                }
                for m in milestones_list
            ],
        }

        # Export to file
        if format.lower() == "yaml":
            with open(dest, "w") as f:
                yaml.dump(milestones_data, f, default_flow_style=False, sort_keys=False)
        else:
            with open(dest, "w") as f:
                json.dump(milestones_data, f, indent=2)

        # Create summary table
        if milestones_list:
            table = Table(title=f"🎯 Milestones: {repository}", border_style="cyan")
            table.add_column("Title", style="bold")
            table.add_column("State", style="cyan")
            table.add_column("Progress", style="green")
            table.add_column("Due Date", style="dim")

            for m in milestones_list:
                total = m.open_issues + m.closed_issues
                progress = f"{m.closed_issues}/{total}" if total > 0 else "0/0"
                due = m.due_on[:10] if m.due_on else "No due date"
                state_color = "green" if m.state == "open" else "dim"

                table.add_row(
                    m.title,
                    f"[{state_color}]{m.state}[/{state_color}]",
                    progress,
                    due,
                )

            console.print()
            console.print(table)

        print_success(f"Milestones exported to: {dest}")
        console.print(f"   [dim]Total milestones: {len(milestones_list)}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


@app.command()
def webhooks(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for webhooks export (default: backups/<owner>/data/webhooks/<owner>_<repo>_webhooks.json)",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or yaml",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export webhooks configuration from a GitHub repository.

    "Webhooks are just callbacks with trust issues." — schema.cx

    ⚠️  Note: Requires admin access to the repository. Secret values are redacted.

    Example:
        farmore webhooks miztizm/farmore
        farmore webhooks myorg/myrepo --format yaml
    """
    if format.lower() not in ["json", "yaml"]:
        console.print("[red]❌ Error: Format must be 'json' or 'yaml'[/red]")
        sys.exit(1)

    # Parse owner/repo
    try:
        owner, repo = validate_repository_format(repository)
    except ValueError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

    # Determine destination
    if dest is None:
        dest = Path("backups") / owner / "data" / "webhooks" / f"{owner}_{repo}_webhooks.{format.lower()}"

    # Create parent directory
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        webhooks_list = client.get_webhooks(owner, repo)

        # Convert to dict for export
        webhooks_data = {
            "repository": repository,
            "total_webhooks": len(webhooks_list),
            "exported_at": datetime.now().isoformat(),
            "note": "Webhook secrets are not exported for security reasons",
            "webhooks": [
                {
                    "id": wh.id,
                    "name": wh.name,
                    "active": wh.active,
                    "events": wh.events,
                    "config": wh.config,
                    "created_at": wh.created_at,
                    "updated_at": wh.updated_at,
                }
                for wh in webhooks_list
            ],
        }

        # Export to file
        if format.lower() == "yaml":
            with open(dest, "w") as f:
                yaml.dump(webhooks_data, f, default_flow_style=False, sort_keys=False)
        else:
            with open(dest, "w") as f:
                json.dump(webhooks_data, f, indent=2)

        # Create summary table
        if webhooks_list:
            table = Table(title=f"🔗 Webhooks: {repository}", border_style="cyan")
            table.add_column("ID", style="dim")
            table.add_column("URL", style="bold", max_width=50)
            table.add_column("Active", style="cyan")
            table.add_column("Events", style="dim")

            for wh in webhooks_list:
                url = wh.config.get("url", "N/A")
                if len(url) > 50:
                    url = url[:47] + "..."
                active = "[green]Yes[/green]" if wh.active else "[red]No[/red]"
                events = ", ".join(wh.events[:3])
                if len(wh.events) > 3:
                    events += f" (+{len(wh.events) - 3})"

                table.add_row(str(wh.id), url, active, events)

            console.print()
            console.print(table)
        else:
            print_info(f"No webhooks found for {repository}")

        print_success(f"Webhooks exported to: {dest}")
        console.print(f"   [dim]Total webhooks: {len(webhooks_list)}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


@app.command()
def followers(
    username: str | None = typer.Argument(None, help="GitHub username (omit for authenticated user)"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for followers export (default: backups/<username>/followers.json)",
    ),
    include_following: bool = typer.Option(
        False,
        "--include-following",
        help="Also export users that the account is following",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or yaml",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export followers (and optionally following) for a GitHub user.

    "Followers are just watchers for humans." — schema.cx

    Example:
        farmore followers
        farmore followers miztizm
        farmore followers miztizm --include-following
        farmore followers --format yaml
    """
    if format.lower() not in ["json", "yaml"]:
        console.print("[red]❌ Error: Format must be 'json' or 'yaml'[/red]")
        sys.exit(1)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=username or "me",
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)

        # Get the actual username if not provided
        if username is None:
            profile = client.get_user_profile(None)
            actual_username = profile.login
        else:
            actual_username = username

        # Determine destination
        if dest is None:
            dest = Path("backups") / actual_username / f"followers.{format.lower()}"

        # Create parent directory
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Fetch followers
        followers_list = client.get_followers(username)

        # Fetch following if requested
        following_list = []
        if include_following:
            following_list = client.get_following(username)

        # Convert to dict for export
        export_data = {
            "username": actual_username,
            "exported_at": datetime.now().isoformat(),
            "followers_count": len(followers_list),
            "followers": [
                {
                    "login": f.login,
                    "id": f.id,
                    "avatar_url": f.avatar_url,
                    "html_url": f.html_url,
                    "type": f.type,
                }
                for f in followers_list
            ],
        }

        if include_following:
            export_data["following_count"] = len(following_list)
            export_data["following"] = [
                {
                    "login": f.login,
                    "id": f.id,
                    "avatar_url": f.avatar_url,
                    "html_url": f.html_url,
                    "type": f.type,
                }
                for f in following_list
            ]

        # Export to file
        if format.lower() == "yaml":
            with open(dest, "w") as f:
                yaml.dump(export_data, f, default_flow_style=False, sort_keys=False)
        else:
            with open(dest, "w") as f:
                json.dump(export_data, f, indent=2)

        # Create summary table
        table = Table(title=f"👥 Social Graph: {actual_username}", border_style="cyan")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")

        table.add_row("Followers", f"[cyan]{len(followers_list)}[/cyan]")
        if include_following:
            table.add_row("Following", f"[cyan]{len(following_list)}[/cyan]")
        table.add_row("Exported To", str(dest))

        console.print()
        console.print(table)
        print_success("Followers exported successfully!")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


@app.command()
def discussions(
    repository: str = typer.Argument(..., help="Repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for discussions export (default: backups/<owner>/data/discussions/<owner>_<repo>_discussions.json)",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or yaml",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export all discussions from a GitHub repository.

    "Discussions are just issues that went to therapy." — schema.cx

    Uses the GitHub GraphQL API to fetch discussions data.

    Example:
        farmore discussions miztizm/farmore
        farmore discussions myorg/myrepo --format yaml
    """
    if format.lower() not in ["json", "yaml"]:
        console.print("[red]❌ Error: Format must be 'json' or 'yaml'[/red]")
        sys.exit(1)

    # Parse owner/repo
    try:
        owner, repo = validate_repository_format(repository)
    except ValueError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

    # Determine destination
    if dest is None:
        dest = Path("backups") / owner / "data" / "discussions" / f"{owner}_{repo}_discussions.{format.lower()}"

    # Create parent directory
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        discussions_list = client.get_discussions(owner, repo)

        # Convert to dict for export
        discussions_data = {
            "repository": repository,
            "total_discussions": len(discussions_list),
            "exported_at": datetime.now().isoformat(),
            "discussions": [
                {
                    "id": d.id,
                    "number": d.number,
                    "title": d.title,
                    "body": d.body,
                    "author": d.author,
                    "category": d.category,
                    "answer_chosen": d.answer_chosen,
                    "locked": d.locked,
                    "created_at": d.created_at,
                    "updated_at": d.updated_at,
                    "html_url": d.html_url,
                    "comments_count": d.comments_count,
                    "upvote_count": d.upvote_count,
                }
                for d in discussions_list
            ],
        }

        # Export to file
        if format.lower() == "yaml":
            with open(dest, "w") as f:
                yaml.dump(discussions_data, f, default_flow_style=False, sort_keys=False)
        else:
            with open(dest, "w") as f:
                json.dump(discussions_data, f, indent=2)

        # Create summary table
        if discussions_list:
            table = Table(title=f"💬 Discussions: {repository}", border_style="cyan")
            table.add_column("#", style="dim")
            table.add_column("Title", style="bold", max_width=50)
            table.add_column("Category", style="cyan")
            table.add_column("Author", style="green")
            table.add_column("💬", justify="right")
            table.add_column("👍", justify="right")

            for d in discussions_list[:20]:  # Show first 20
                title = d.title[:47] + "..." if len(d.title) > 50 else d.title
                table.add_row(
                    str(d.number),
                    title,
                    d.category,
                    d.author,
                    str(d.comments_count),
                    str(d.upvote_count),
                )

            if len(discussions_list) > 20:
                table.add_row("...", f"[dim]and {len(discussions_list) - 20} more[/dim]", "", "", "", "")

            console.print()
            console.print(table)
        else:
            print_info(f"No discussions found for {repository}")

        print_success(f"Discussions exported to: {dest}")
        console.print(f"   [dim]Total discussions: {len(discussions_list)}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


# ==============================================================================
# Configuration Profile Commands
# ==============================================================================


@app.command("config-save")
def config_save(
    name: str = typer.Argument(..., help="Profile name"),
    target_type: str = typer.Option(..., "--type", "-t", help="Target type: 'user' or 'org'"),
    target_name: str = typer.Option(..., "--name", "-n", help="GitHub username or organization"),
    dest: str | None = typer.Option(None, "--dest", "-d", help="Destination directory"),
    visibility: str = typer.Option("all", "--visibility", help="Repository visibility filter"),
    include_forks: bool = typer.Option(False, "--include-forks", help="Include forked repositories"),
    include_archived: bool = typer.Option(False, "--include-archived", help="Include archived repositories"),
    include_issues: bool = typer.Option(False, "--include-issues", help="Include issues in backup"),
    include_pulls: bool = typer.Option(False, "--include-pulls", help="Include pull requests in backup"),
    include_releases: bool = typer.Option(False, "--include-releases", help="Include releases in backup"),
    include_wikis: bool = typer.Option(False, "--include-wikis", help="Include wikis in backup"),
    parallel_workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel workers"),
    description: str = typer.Option("", "--description", help="Profile description"),
) -> None:
    """
    Save a backup configuration profile.

    "Save your settings once, use them forever." — schema.cx

    Example:
        farmore config-save my-backup --type user --name miztizm --include-issues
        farmore config-save daily-org --type org --name myorg --workers 8
    """
    from .config import ConfigManager, create_profile_from_args

    profile = create_profile_from_args(
        name=name,
        target_type=target_type,
        target_name=target_name,
        dest=dest,
        visibility=visibility,
        include_forks=include_forks,
        include_archived=include_archived,
        include_issues=include_issues,
        include_pulls=include_pulls,
        include_releases=include_releases,
        include_wikis=include_wikis,
        parallel_workers=parallel_workers,
        description=description,
    )

    manager = ConfigManager()
    manager.save_profile(profile)

    print_success(f"Profile '{name}' saved successfully!")
    console.print(f"   [dim]Config path: {manager.get_profile_path()}[/dim]")


@app.command("config-load")
def config_load(
    name: str = typer.Argument(..., help="Profile name to load"),
) -> None:
    """
    Load and display a saved backup profile.

    "Configuration recall is just organized memory." — schema.cx

    Example:
        farmore config-load my-backup
    """
    from .config import ConfigManager

    manager = ConfigManager()
    profile = manager.load_profile(name)

    if profile is None:
        print_error(f"Profile '{name}' not found")
        sys.exit(1)

    # Display profile as a table
    table = Table(title=f"⚙️  Profile: {name}", border_style="cyan")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Target Type", profile.target_type)
    table.add_row("Target Name", profile.target_name)
    table.add_row("Destination", profile.dest or "[dim]Default[/dim]")
    table.add_row("Visibility", profile.visibility)
    table.add_row("Include Forks", "Yes" if profile.include_forks else "No")
    table.add_row("Include Archived", "Yes" if profile.include_archived else "No")
    table.add_row("Include Issues", "Yes" if profile.include_issues else "No")
    table.add_row("Include Pulls", "Yes" if profile.include_pulls else "No")
    table.add_row("Include Releases", "Yes" if profile.include_releases else "No")
    table.add_row("Include Wikis", "Yes" if profile.include_wikis else "No")
    table.add_row("Parallel Workers", str(profile.parallel_workers))
    table.add_row("Description", profile.description or "[dim]No description[/dim]")
    table.add_row("Created", profile.created_at[:19])
    table.add_row("Updated", profile.updated_at[:19])

    console.print()
    console.print(table)


@app.command("config-list")
def config_list() -> None:
    """
    List all saved backup profiles.

    "Know your options before you choose." — schema.cx

    Example:
        farmore config-list
    """
    from .config import ConfigManager

    manager = ConfigManager()
    profiles = manager.list_profiles()

    if not profiles:
        print_info("No profiles saved yet")
        console.print("   [dim]Use 'farmore config-save' to create a profile[/dim]")
        return

    table = Table(title="⚙️  Saved Profiles", border_style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("Target", style="green")
    table.add_column("Description", style="dim", max_width=40)
    table.add_column("Updated", style="dim")

    for profile in profiles:
        desc = profile.description[:37] + "..." if len(profile.description) > 40 else profile.description
        table.add_row(
            profile.name,
            profile.target_type,
            profile.target_name,
            desc or "[dim]—[/dim]",
            profile.updated_at[:10],
        )

    console.print()
    console.print(table)
    console.print(f"\n   [dim]Total profiles: {len(profiles)}[/dim]")


@app.command("config-delete")
def config_delete(
    name: str = typer.Argument(..., help="Profile name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """
    Delete a saved backup profile.

    "Sometimes the best configuration is no configuration." — schema.cx

    Example:
        farmore config-delete my-backup
        farmore config-delete old-profile --force
    """
    from .config import ConfigManager

    manager = ConfigManager()

    if not force:
        confirm = typer.confirm(f"Delete profile '{name}'?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    if manager.delete_profile(name):
        print_success(f"Profile '{name}' deleted")
    else:
        print_error(f"Profile '{name}' not found")
        sys.exit(1)


@app.command("config-export")
def config_export(
    name: str = typer.Argument(..., help="Profile name to export"),
    output: Path = typer.Option(..., "--output", "-o", help="Output file path"),
) -> None:
    """
    Export a profile to a file for sharing.

    "Sharing is caring. Even for configurations." — schema.cx

    Example:
        farmore config-export my-backup --output ./my-backup.yaml
    """
    from .config import ConfigManager

    manager = ConfigManager()
    if manager.export_profile(name, output):
        print_success(f"Profile exported to: {output}")
    else:
        print_error(f"Profile '{name}' not found")
        sys.exit(1)


@app.command("config-import")
def config_import(
    input_file: Path = typer.Argument(..., help="Profile file to import"),
    name: str | None = typer.Option(None, "--name", "-n", help="Override profile name"),
) -> None:
    """
    Import a profile from a file.

    "Good configurations deserve to be shared." — schema.cx

    Example:
        farmore config-import ./shared-backup.yaml
        farmore config-import ./backup.yaml --name my-new-profile
    """
    from .config import ConfigManager

    manager = ConfigManager()
    profile = manager.import_profile(input_file, name)

    if profile:
        print_success(f"Profile '{profile.name}' imported successfully!")
    else:
        print_error(f"Failed to import profile from: {input_file}")
        sys.exit(1)


# ==============================================================================
# Backup Verification Commands
# ==============================================================================


@app.command("verify")
def verify_backup(
    path: Path = typer.Argument(..., help="Path to backup directory or repository"),
    deep: bool = typer.Option(False, "--deep", help="Perform deep verification (git fsck)"),
    checksums: bool = typer.Option(False, "--checksums", help="Verify file checksums"),
) -> None:
    """
    Verify backup integrity.

    "Trust, but verify. Especially your backups." — schema.cx

    Checks git repository integrity and optionally verifies checksums.

    Example:
        farmore verify ./backups/miztizm
        farmore verify ./backups/miztizm/repos/public/miztizm/farmore --deep
        farmore verify ./my-backup --deep --checksums
    """
    from .verify import BackupVerifier

    console.print(f"\n[cyan]🔍 Verifying backup: {path}[/cyan]")
    if deep:
        console.print("   [dim]Deep verification enabled (git fsck)[/dim]")
    if checksums:
        console.print("   [dim]Checksum verification enabled[/dim]")

    verifier = BackupVerifier()
    results = verifier.verify_backup_directory(path, deep=deep, verify_checksums=checksums)

    if not results:
        # Check if it's a single repository
        if (path / ".git").exists() or (path / "HEAD").exists():
            result = verifier.verify_repository(path, deep=deep, verify_checksums=checksums)
            results = [result]
        else:
            print_warning("No repositories found to verify")
            return

    # Display results
    valid_count = sum(1 for r in results if r.is_valid)
    invalid_count = len(results) - valid_count

    table = Table(title="🔍 Verification Results", border_style="cyan")
    table.add_column("Repository", style="bold")
    table.add_column("Status", style="cyan")
    table.add_column("Git", style="green")
    table.add_column("Issues", style="dim")
    table.add_column("Duration", justify="right", style="dim")

    for result in results:
        status = "[green]✓ Valid[/green]" if result.is_valid else "[red]✗ Invalid[/red]"
        git_status = "[green]OK[/green]" if result.git_valid else "[red]FAIL[/red]"

        issues = []
        if result.git_errors:
            issues.extend(result.git_errors[:2])
        if result.checksum_errors:
            issues.extend(result.checksum_errors[:2])
        issues_str = "; ".join(issues[:2]) if issues else "[dim]None[/dim]"
        if len(issues_str) > 50:
            issues_str = issues_str[:47] + "..."

        table.add_row(
            result.repository_name or str(result.path.name),
            status,
            git_status,
            issues_str,
            f"{result.duration_seconds:.2f}s",
        )

    console.print()
    console.print(table)

    # Summary
    console.print(f"\n   [green]Valid: {valid_count}[/green]  [red]Invalid: {invalid_count}[/red]")

    if invalid_count > 0:
        sys.exit(1)

    print_success("All backups verified successfully!")


# ==============================================================================
# Backup Scheduling Commands
# ==============================================================================


@app.command("schedule-add")
def schedule_add(
    name: str = typer.Argument(..., help="Schedule name"),
    profile: str = typer.Option(..., "--profile", "-p", help="Profile name to use"),
    interval: str = typer.Option("daily", "--interval", "-i", help="Backup interval: hourly, daily, weekly, or 'every X hours/days'"),
    at_time: str | None = typer.Option(None, "--at", help="Time to run (HH:MM format, for daily/weekly)"),
    on_day: str | None = typer.Option(None, "--on", help="Day to run (for weekly, e.g., 'monday')"),
) -> None:
    """
    Add a scheduled backup.

    "Automation is the art of making the future happen on time." — schema.cx

    Example:
        farmore schedule-add daily-backup --profile my-backup --interval daily --at 02:00
        farmore schedule-add weekly-full --profile full-backup --interval weekly --on monday --at 03:00
        farmore schedule-add frequent --profile quick --interval "every 6 hours"
    """
    from .scheduler import BackupScheduler, create_scheduled_backup

    scheduler = BackupScheduler()
    backup = create_scheduled_backup(
        name=name,
        profile_name=profile,
        interval=interval,
        at_time=at_time,
        on_day=on_day,
    )

    scheduler.add_backup(backup)
    print_success(f"Scheduled backup '{name}' added!")
    console.print(f"   [dim]Interval: {interval}[/dim]")
    if at_time:
        console.print(f"   [dim]At: {at_time}[/dim]")
    if on_day:
        console.print(f"   [dim]On: {on_day}[/dim]")


@app.command("schedule-list")
def schedule_list() -> None:
    """
    List all scheduled backups.

    "Know your schedule before time knows you." — schema.cx

    Example:
        farmore schedule-list
    """
    from .scheduler import BackupScheduler

    scheduler = BackupScheduler()
    backups = scheduler.list_backups()

    if not backups:
        print_info("No scheduled backups")
        console.print("   [dim]Use 'farmore schedule-add' to create a schedule[/dim]")
        return

    table = Table(title="📅 Scheduled Backups", border_style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Profile", style="cyan")
    table.add_column("Interval", style="green")
    table.add_column("Enabled", style="yellow")
    table.add_column("Last Run", style="dim")
    table.add_column("Status", style="dim")

    for backup in backups:
        enabled = "[green]Yes[/green]" if backup.enabled else "[dim]No[/dim]"
        last_run = backup.last_run[:16] if backup.last_run else "[dim]Never[/dim]"
        status = backup.last_status

        table.add_row(
            backup.name,
            backup.profile_name,
            backup.interval,
            enabled,
            last_run,
            status,
        )

    console.print()
    console.print(table)


@app.command("schedule-remove")
def schedule_remove(
    name: str = typer.Argument(..., help="Schedule name to remove"),
) -> None:
    """
    Remove a scheduled backup.

    "Not all schedules are forever." — schema.cx

    Example:
        farmore schedule-remove daily-backup
    """
    from .scheduler import BackupScheduler

    scheduler = BackupScheduler()
    if scheduler.remove_backup(name):
        print_success(f"Schedule '{name}' removed")
    else:
        print_error(f"Schedule '{name}' not found")
        sys.exit(1)


@app.command("schedule-run")
def schedule_run(
    run_once: bool = typer.Option(False, "--once", help="Run all pending jobs once and exit"),
) -> None:
    """
    Run the backup scheduler daemon.

    "The scheduler never sleeps. So you can." — schema.cx

    This starts a long-running process that executes scheduled backups.
    Use Ctrl+C to stop the scheduler.

    Example:
        farmore schedule-run
        farmore schedule-run --once  # Run pending jobs and exit
    """
    from .config import ConfigManager
    from .scheduler import BackupScheduler

    config_manager = ConfigManager()

    def run_profile_backup(profile_name: str) -> bool:
        """Execute a backup using a saved profile."""
        profile = config_manager.load_profile(profile_name)
        if profile is None:
            console.print(f"[red]Profile '{profile_name}' not found[/red]")
            return False

        console.print(f"\n[cyan]🚀 Running backup: {profile_name}[/cyan]")

        # Build config from profile
        dest = Path(profile.dest) if profile.dest else get_default_user_dest(profile.target_name)

        config = Config(
            target_type=TargetType.USER if profile.target_type == "user" else TargetType.ORG,
            target_name=profile.target_name,
            dest=dest,
            visibility=Visibility(profile.visibility),
            include_forks=profile.include_forks,
            include_archived=profile.include_archived,
            max_workers=profile.parallel_workers,
            skip_existing=profile.skip_existing,
            bare=profile.bare,
            lfs=profile.lfs,
        )

        try:
            orchestrator = MirrorOrchestrator(config)
            summary = orchestrator.run()
            return not summary.has_failures
        except Exception as e:
            console.print(f"[red]Backup failed: {e}[/red]")
            return False

    scheduler = BackupScheduler(backup_callback=run_profile_backup)

    console.print("\n[cyan]📅 Starting backup scheduler...[/cyan]")
    console.print("   [dim]Press Ctrl+C to stop[/dim]")

    try:
        scheduler.run(run_once=run_once)
    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduler stopped[/yellow]")
    except RuntimeError as e:
        print_error(str(e))
        console.print("   [dim]Install with: pip install schedule[/dim]")
        sys.exit(1)


# ==============================================================================
# Restore Commands
# ==============================================================================


@app.command("restore-issues")
def restore_issues(
    backup_path: Path = typer.Argument(..., help="Path to issues backup file (JSON)"),
    target_repo: str = typer.Option(..., "--to", "-t", help="Target repository (owner/repo)"),
    skip_existing: bool = typer.Option(True, "--skip-existing/--no-skip-existing", help="Skip issues with matching titles"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without creating issues"),
    token: str | None = typer.Option(None, "--token", envvar="GITHUB_TOKEN", help="GitHub token"),
) -> None:
    """
    Restore issues from a backup to a GitHub repository.

    "Backups are insurance. Restores are the payout." — schema.cx

    Example:
        farmore restore-issues ./backup/issues.json --to miztizm/new-repo
        farmore restore-issues ./issues.json --to myorg/myrepo --dry-run
    """
    from .restore import RestoreManager

    if not token:
        print_error("GitHub token required for restore operations")
        console.print("   [dim]Set GITHUB_TOKEN environment variable or use --token[/dim]")
        sys.exit(1)

    try:
        owner, repo = validate_repository_format(target_repo)
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)

    console.print(f"\n[cyan]📥 Restoring issues to: {target_repo}[/cyan]")
    if dry_run:
        console.print("   [yellow]DRY RUN - No issues will be created[/yellow]")

    manager = RestoreManager(token)
    result = manager.restore_issues(
        backup_path=backup_path,
        target_repo=target_repo,
        skip_existing=skip_existing,
        dry_run=dry_run,
    )

    # Display results
    table = Table(title="📥 Restore Results", border_style="cyan")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Restored", f"[green]{result.items_restored}[/green]")
    table.add_row("Skipped", f"[dim]{result.items_skipped}[/dim]")
    table.add_row("Failed", f"[red]{result.items_failed}[/red]" if result.items_failed else "[green]0[/green]")
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")

    console.print()
    console.print(table)

    if result.failed_items:
        console.print("\n[red]Failed items:[/red]")
        for item in result.failed_items[:5]:
            console.print(f"   [red]• {item.get('title', 'Unknown')}: {item.get('error', '')}[/red]")

    if result.success:
        print_success("Issues restored successfully!")
    else:
        print_error(result.error_message or "Some issues failed to restore")
        sys.exit(1)


@app.command("restore-releases")
def restore_releases(
    backup_path: Path = typer.Argument(..., help="Path to releases backup file or directory"),
    target_repo: str = typer.Option(..., "--to", "-t", help="Target repository (owner/repo)"),
    skip_existing: bool = typer.Option(True, "--skip-existing/--no-skip-existing", help="Skip releases with matching tags"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without creating releases"),
    token: str | None = typer.Option(None, "--token", envvar="GITHUB_TOKEN", help="GitHub token"),
) -> None:
    """
    Restore releases from a backup to a GitHub repository.

    "Releases are milestones. Restore them carefully." — schema.cx

    Example:
        farmore restore-releases ./backup/releases/ --to miztizm/new-repo
        farmore restore-releases ./metadata.json --to myorg/myrepo --dry-run
    """
    from .restore import RestoreManager

    if not token:
        print_error("GitHub token required for restore operations")
        console.print("   [dim]Set GITHUB_TOKEN environment variable or use --token[/dim]")
        sys.exit(1)

    try:
        owner, repo = validate_repository_format(target_repo)
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)

    console.print(f"\n[cyan]📥 Restoring releases to: {target_repo}[/cyan]")
    if dry_run:
        console.print("   [yellow]DRY RUN - No releases will be created[/yellow]")

    manager = RestoreManager(token)
    result = manager.restore_releases(
        backup_path=backup_path,
        target_repo=target_repo,
        skip_existing=skip_existing,
        dry_run=dry_run,
    )

    # Display results
    table = Table(title="📥 Restore Results", border_style="cyan")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Restored", f"[green]{result.items_restored}[/green]")
    table.add_row("Skipped", f"[dim]{result.items_skipped}[/dim]")
    table.add_row("Failed", f"[red]{result.items_failed}[/red]" if result.items_failed else "[green]0[/green]")
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")

    console.print()
    console.print(table)

    if result.failed_items:
        console.print("\n[red]Failed items:[/red]")
        for item in result.failed_items[:5]:
            console.print(f"   [red]• {item.get('tag', 'Unknown')}: {item.get('error', '')}[/red]")

    if result.success:
        print_success("Releases restored successfully!")
    else:
        print_error(result.error_message or "Some releases failed to restore")
        sys.exit(1)


@app.command("restore-labels")
def restore_labels(
    backup_path: Path = typer.Argument(..., help="Path to labels backup file (JSON)"),
    target_repo: str = typer.Option(..., "--to", "-t", help="Target repository (owner/repo)"),
    skip_existing: bool = typer.Option(True, "--skip-existing/--no-skip-existing", help="Skip labels with matching names"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without creating labels"),
    token: str | None = typer.Option(None, "--token", envvar="GITHUB_TOKEN", help="GitHub token"),
) -> None:
    """
    Restore labels from a backup to a GitHub repository.

    "Labels bring order to chaos. Restore them wisely." — schema.cx

    Example:
        farmore restore-labels ./backup/labels.json --to miztizm/new-repo
        farmore restore-labels ./labels.json --to myorg/myrepo --dry-run
    """
    from .restore import RestoreManager

    if not token:
        print_error("GitHub token required for restore operations")
        console.print("   [dim]Set GITHUB_TOKEN environment variable or use --token[/dim]")
        sys.exit(1)

    try:
        owner, repo = validate_repository_format(target_repo)
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)

    console.print(f"\n[cyan]📥 Restoring labels to: {target_repo}[/cyan]")
    if dry_run:
        console.print("   [yellow]DRY RUN - No labels will be created[/yellow]")

    manager = RestoreManager(token)
    result = manager.restore_labels(
        backup_path=backup_path,
        target_repo=target_repo,
        skip_existing=skip_existing,
        dry_run=dry_run,
    )

    # Display results
    table = Table(title="📥 Restore Results", border_style="cyan")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Restored", f"[green]{result.items_restored}[/green]")
    table.add_row("Skipped", f"[dim]{result.items_skipped}[/dim]")
    table.add_row("Failed", f"[red]{result.items_failed}[/red]" if result.items_failed else "[green]0[/green]")
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")

    console.print()
    console.print(table)

    if result.success:
        print_success("Labels restored successfully!")
    else:
        print_error(result.error_message or "Some labels failed to restore")
        sys.exit(1)


@app.command("restore-milestones")
def restore_milestones(
    backup_path: Path = typer.Argument(..., help="Path to milestones backup file (JSON)"),
    target_repo: str = typer.Option(..., "--to", "-t", help="Target repository (owner/repo)"),
    skip_existing: bool = typer.Option(True, "--skip-existing/--no-skip-existing", help="Skip milestones with matching titles"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without creating milestones"),
    token: str | None = typer.Option(None, "--token", envvar="GITHUB_TOKEN", help="GitHub token"),
) -> None:
    """
    Restore milestones from a backup to a GitHub repository.

    "Milestones mark progress. Restore them to continue the journey." — schema.cx

    Example:
        farmore restore-milestones ./backup/milestones.json --to miztizm/new-repo
        farmore restore-milestones ./milestones.json --to myorg/myrepo --dry-run
    """
    from .restore import RestoreManager

    if not token:
        print_error("GitHub token required for restore operations")
        console.print("   [dim]Set GITHUB_TOKEN environment variable or use --token[/dim]")
        sys.exit(1)

    try:
        owner, repo = validate_repository_format(target_repo)
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)

    console.print(f"\n[cyan]📥 Restoring milestones to: {target_repo}[/cyan]")
    if dry_run:
        console.print("   [yellow]DRY RUN - No milestones will be created[/yellow]")

    manager = RestoreManager(token)
    result = manager.restore_milestones(
        backup_path=backup_path,
        target_repo=target_repo,
        skip_existing=skip_existing,
        dry_run=dry_run,
    )

    # Display results
    table = Table(title="📥 Restore Results", border_style="cyan")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Restored", f"[green]{result.items_restored}[/green]")
    table.add_row("Skipped", f"[dim]{result.items_skipped}[/dim]")
    table.add_row("Failed", f"[red]{result.items_failed}[/red]" if result.items_failed else "[green]0[/green]")
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")

    console.print()
    console.print(table)

    if result.success:
        print_success("Milestones restored successfully!")
    else:
        print_error(result.error_message or "Some milestones failed to restore")
        sys.exit(1)


# ==============================================================================
# Projects Command (existing)
# ==============================================================================


@app.command()
def projects(
    target: str = typer.Argument(..., help="User/org name or repository in format 'owner/repo'"),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        "-d",
        help="Destination file for projects export",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or yaml",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Export GitHub Projects (v2) for a user/org or repository.

    "Projects are just spreadsheets with delusions of grandeur." — schema.cx

    Uses the GitHub GraphQL API to fetch project data.

    Example:
        farmore projects miztizm  # User/org projects
        farmore projects miztizm/farmore  # Repository projects
        farmore projects myorg/myrepo --format yaml
    """
    if format.lower() not in ["json", "yaml"]:
        console.print("[red]❌ Error: Format must be 'json' or 'yaml'[/red]")
        sys.exit(1)

    # Determine if target is user/org or repo
    if "/" in target:
        owner, repo = target.split("/", 1)
        is_repo = True
    else:
        owner = target
        repo = None
        is_repo = False

    # Determine destination
    if dest is None:
        if is_repo:
            dest = Path("backups") / owner / "data" / "projects" / f"{owner}_{repo}_projects.{format.lower()}"
        else:
            dest = Path("backups") / owner / f"projects.{format.lower()}"

    # Create parent directory
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Create config
    config = Config(
        target_type=TargetType.USER,
        target_name=owner,
        dest=Path("."),
        token=token,
    )

    try:
        client = GitHubAPIClient(config)
        projects_list = client.get_projects(owner, repo)

        # Convert to dict for export
        projects_data = {
            "target": target,
            "is_repository": is_repo,
            "total_projects": len(projects_list),
            "exported_at": datetime.now().isoformat(),
            "projects": [
                {
                    "id": p.id,
                    "number": p.number,
                    "title": p.title,
                    "description": p.description,
                    "public": p.public,
                    "closed": p.closed,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "html_url": p.html_url,
                    "items_count": p.items_count,
                    "fields": p.fields,
                }
                for p in projects_list
            ],
        }

        # Export to file
        if format.lower() == "yaml":
            with open(dest, "w") as f:
                yaml.dump(projects_data, f, default_flow_style=False, sort_keys=False)
        else:
            with open(dest, "w") as f:
                json.dump(projects_data, f, indent=2)

        # Create summary table
        if projects_list:
            table = Table(title=f"📋 Projects: {target}", border_style="cyan")
            table.add_column("#", style="dim")
            table.add_column("Title", style="bold", max_width=40)
            table.add_column("Status", style="cyan")
            table.add_column("Items", justify="right")
            table.add_column("Visibility", style="green")

            for p in projects_list:
                status = "[green]Open[/green]" if not p.closed else "[dim]Closed[/dim]"
                visibility = "Public" if p.public else "Private"

                table.add_row(
                    str(p.number),
                    p.title,
                    status,
                    str(p.items_count),
                    visibility,
                )

            console.print()
            console.print(table)
        else:
            print_info(f"No projects found for {target}")

        print_success(f"Projects exported to: {dest}")
        console.print(f"   [dim]Total projects: {len(projects_list)}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)


# ==============================================================================
# Analytics Commands
# ==============================================================================


@app.command("analytics")
def analytics_report(
    path: Path = typer.Argument(None, help="Path to backup directory (default: backups/)"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, json, or yaml"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Save report to file"),
) -> None:
    """
    Analyze backup directory and generate statistics report.

    "Data is only as good as the insights you extract." — schema.cx

    Example:
        farmore analytics
        farmore analytics ./backups/miztizm
        farmore analytics --format json --output report.json
    """
    from .analytics import BackupAnalytics

    backup_path = path or Path("backups")

    if not backup_path.exists():
        print_error(f"Backup directory not found: {backup_path}")
        sys.exit(1)

    console.print(f"\n[cyan]📊 Analyzing backup directory: {backup_path}[/cyan]")

    analytics = BackupAnalytics(backup_path)
    report = analytics.generate_report(format=format.lower())

    if output:
        output.write_text(report)
        print_success(f"Report saved to: {output}")
    else:
        console.print(report)


@app.command("analytics-history")
def analytics_history(
    path: Path = typer.Argument(None, help="Path to backup directory"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of history entries to show"),
) -> None:
    """
    Show backup history and statistics.

    "History doesn't repeat, but it does rhyme. Track it." — schema.cx

    Example:
        farmore analytics-history
        farmore analytics-history ./backups/miztizm --limit 50
    """
    from .analytics import BackupAnalytics

    backup_path = path or Path("backups")
    analytics = BackupAnalytics(backup_path)

    history = analytics.get_history(limit=limit)

    if not history:
        print_info("No backup history found")
        console.print("   [dim]History is recorded after backup operations[/dim]")
        return

    table = Table(title="📜 Backup History", border_style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Date", style="cyan")
    table.add_column("Cloned", justify="right", style="green")
    table.add_column("Updated", justify="right", style="blue")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Duration", justify="right", style="dim")
    table.add_column("Status")

    for h in reversed(history):
        status = "[green]✓[/green]" if h.success else "[red]✗[/red]"
        duration = f"{h.duration_seconds:.1f}s"
        date = h.started_at[:16] if h.started_at else "?"

        table.add_row(
            h.backup_id,
            date,
            str(h.repos_cloned),
            str(h.repos_updated),
            str(h.repos_failed),
            duration,
            status,
        )

    console.print()
    console.print(table)

    # Show growth stats
    growth = analytics.get_growth_stats()
    if growth.get("has_data"):
        console.print(f"\n   [cyan]📈 Total backups: {growth['backup_count']}[/cyan]")
        console.print(f"   [dim]Success rate: {growth['success_rate']:.1f}%[/dim]")
        console.print(f"   [dim]Avg duration: {growth['avg_duration_seconds']:.1f}s[/dim]")


# ==============================================================================
# Diff/Compare Commands
# ==============================================================================


@app.command("diff")
def diff_backups(
    old_path: Path = typer.Argument(..., help="Path to old/baseline backup"),
    new_path: Path = typer.Argument(None, help="Path to new backup (omit to compare with snapshot)"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, json, or yaml"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Save diff to file"),
) -> None:
    """
    Compare two backup directories and show differences.

    "Change is the only constant. Track it." — schema.cx

    Example:
        farmore diff ./backups-old ./backups-new
        farmore diff ./backups  # Compare with last snapshot
        farmore diff ./backup1 ./backup2 --format json
    """
    from .diff import BackupCompare

    compare = BackupCompare()

    if new_path:
        # Compare two directories
        if not old_path.exists():
            print_error(f"Directory not found: {old_path}")
            sys.exit(1)
        if not new_path.exists():
            print_error(f"Directory not found: {new_path}")
            sys.exit(1)

        console.print(f"\n[cyan]🔍 Comparing backups...[/cyan]")
        console.print(f"   [dim]Old: {old_path}[/dim]")
        console.print(f"   [dim]New: {new_path}[/dim]")

        diff = compare.compare_directories(old_path, new_path)
    else:
        # Compare with snapshot
        if not old_path.exists():
            print_error(f"Directory not found: {old_path}")
            sys.exit(1)

        console.print(f"\n[cyan]🔍 Comparing with last snapshot...[/cyan]")

        diff = compare.compare_with_snapshot(old_path)

        if diff is None:
            print_warning("No snapshot found. Create one first with 'farmore snapshot'")
            sys.exit(1)

    report = compare.generate_diff_report(diff, format=format.lower())

    if output:
        output.write_text(report)
        print_success(f"Diff report saved to: {output}")
    else:
        console.print(report)


@app.command("snapshot")
def create_snapshot(
    path: Path = typer.Argument(..., help="Path to backup directory"),
) -> None:
    """
    Create a snapshot of the current backup state for later comparison.

    "Capture the moment. Compare later." — schema.cx

    Example:
        farmore snapshot ./backups/miztizm
    """
    from .diff import BackupCompare

    if not path.exists():
        print_error(f"Directory not found: {path}")
        sys.exit(1)

    console.print(f"\n[cyan]📸 Creating snapshot of: {path}[/cyan]")

    compare = BackupCompare()
    snapshot_path = compare.save_snapshot(path)

    print_success(f"Snapshot saved: {snapshot_path}")
    console.print("   [dim]Use 'farmore diff' to compare future changes[/dim]")


# ==============================================================================
# Template Commands
# ==============================================================================


@app.command("templates")
def list_templates(
    category: str | None = typer.Option(None, "--category", "-c", help="Filter by category"),
    tag: str | None = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    builtin_only: bool = typer.Option(False, "--builtin", help="Show only built-in templates"),
    custom_only: bool = typer.Option(False, "--custom", help="Show only custom templates"),
) -> None:
    """
    List available backup templates.

    "Good templates save time. Great templates save careers." — schema.cx

    Example:
        farmore templates
        farmore templates --category org
        farmore templates --tag scheduled
    """
    from .templates import TemplateManager

    manager = TemplateManager()

    if builtin_only:
        templates = manager.list_builtin()
    elif custom_only:
        templates = manager.list_custom()
    elif category:
        templates = manager.get_by_category(category)
    elif tag:
        templates = manager.get_by_tag(tag)
    else:
        templates = manager.list_all()

    if not templates:
        print_info("No templates found")
        return

    table = Table(title="📋 Backup Templates", border_style="cyan")
    table.add_column("ID", style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Description", style="dim", max_width=40)
    table.add_column("Tags", style="dim")

    for t in templates:
        desc = t.description[:37] + "..." if len(t.description) > 40 else t.description
        tags = ", ".join(t.tags[:3])
        if len(t.tags) > 3:
            tags += f" (+{len(t.tags) - 3})"

        table.add_row(t.id, t.name, t.category, desc, tags)

    console.print()
    console.print(table)
    console.print(f"\n   [dim]Total templates: {len(templates)}[/dim]")
    console.print("   [dim]Use 'farmore template-show <id>' for details[/dim]")


@app.command("template-show")
def show_template(
    template_id: str = typer.Argument(..., help="Template ID"),
) -> None:
    """
    Show details of a backup template.

    Example:
        farmore template-show user-complete
        farmore template-show org-compliance
    """
    from .templates import TemplateManager

    manager = TemplateManager()
    template = manager.get(template_id)

    if template is None:
        print_error(f"Template not found: {template_id}")
        sys.exit(1)

    table = Table(title=f"📋 Template: {template.name}", border_style="cyan", show_header=False)
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("ID", template.id)
    table.add_row("Name", template.name)
    table.add_row("Description", template.description)
    table.add_row("Category", template.category)
    table.add_row("Author", template.author)
    table.add_row("", "")
    table.add_row("[bold]Target Settings[/bold]", "")
    table.add_row("Target Type", template.target_type)
    table.add_row("Visibility", template.visibility)
    table.add_row("Include Forks", "Yes" if template.include_forks else "No")
    table.add_row("Include Archived", "Yes" if template.include_archived else "No")
    if template.name_regex:
        table.add_row("Name Regex", template.name_regex)
    table.add_row("", "")
    table.add_row("[bold]Data Exports[/bold]", "")
    table.add_row("Issues", "Yes" if template.include_issues else "No")
    table.add_row("Pull Requests", "Yes" if template.include_pulls else "No")
    table.add_row("Releases", "Yes" if template.include_releases else "No")
    table.add_row("Wikis", "Yes" if template.include_wikis else "No")
    table.add_row("Workflows", "Yes" if template.include_workflows else "No")
    table.add_row("", "")
    table.add_row("[bold]Git Options[/bold]", "")
    table.add_row("Bare/Mirror", "Yes" if template.bare else "No")
    table.add_row("LFS Support", "Yes" if template.lfs else "No")
    table.add_row("Skip Existing", "Yes" if template.skip_existing else "No")
    table.add_row("Parallel Workers", str(template.parallel_workers))
    table.add_row("", "")
    table.add_row("Tags", ", ".join(template.tags) if template.tags else "[dim]None[/dim]")

    console.print()
    console.print(table)

    if template.schedule_interval:
        console.print(f"\n   [cyan]📅 Schedule: {template.schedule_interval}")
        if template.schedule_time:
            console.print(f"      At: {template.schedule_time}[/cyan]")


@app.command("template-use")
def use_template(
    template_id: str = typer.Argument(..., help="Template ID to use"),
    target: str = typer.Argument(..., help="GitHub username or organization"),
    dest: Path | None = typer.Option(None, "--dest", "-d", help="Destination directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without executing"),
    token: str | None = typer.Option(None, "--token", "-t", envvar="GITHUB_TOKEN", help="GitHub token"),
) -> None:
    """
    Run a backup using a template.

    "Templates turn complex operations into one-liners." — schema.cx

    Example:
        farmore template-use user-complete miztizm
        farmore template-use org-compliance myorg --dest ./org-backup
    """
    from .templates import TemplateManager

    manager = TemplateManager()
    template = manager.get(template_id)

    if template is None:
        print_error(f"Template not found: {template_id}")
        sys.exit(1)

    console.print(f"\n[cyan]🚀 Using template: {template.name}[/cyan]")
    console.print(f"   [dim]Target: {target}[/dim]")

    # Build config from template
    args = manager.apply_template(template_id, target, dest)

    if args is None:
        print_error("Failed to apply template")
        sys.exit(1)

    if dry_run:
        console.print("\n[yellow]DRY RUN - Would execute with:[/yellow]")
        for key, value in args.items():
            if value:
                console.print(f"   {key}: {value}")
        return

    # Build and run the backup
    if dest is None:
        dest = Path("backups") / target

    target_type = TargetType.USER if args["target_type"] == "user" else TargetType.ORG

    config = Config(
        target_type=target_type,
        target_name=target,
        dest=dest,
        token=token,
        visibility=Visibility(args["visibility"]),
        include_forks=args["include_forks"],
        include_archived=args["include_archived"],
        exclude_repos=args.get("exclude_repos"),
        name_regex=args.get("name_regex"),
        bare=args["bare"],
        lfs=args["lfs"],
        skip_existing=args["skip_existing"],
        max_workers=args["parallel_workers"],
    )

    orchestrator = MirrorOrchestrator(config)
    summary = orchestrator.run()

    # Export additional data if requested
    if any([args.get("include_issues"), args.get("include_pulls"),
            args.get("include_workflows"), args.get("include_releases"),
            args.get("include_wikis")]):
        client = GitHubAPIClient(config)
        repos = client.get_repositories()

        export_repository_data(
            client=client,
            repos=repos,
            username=target,
            include_issues=args.get("include_issues", False),
            include_pulls=args.get("include_pulls", False),
            include_workflows=args.get("include_workflows", False),
            include_releases=args.get("include_releases", False),
            include_wikis=args.get("include_wikis", False),
            token=token,
        )

    if summary.has_failures and summary.success_count == 0:
        sys.exit(1)


@app.command("template-create")
def create_template(
    template_id: str = typer.Argument(..., help="Unique template ID"),
    name: str = typer.Option(..., "--name", "-n", help="Template name"),
    description: str = typer.Option("", "--description", "-d", help="Template description"),
    from_profile: str | None = typer.Option(None, "--from-profile", help="Create from existing profile"),
) -> None:
    """
    Create a custom backup template.

    Example:
        farmore template-create my-template --name "My Template" --from-profile daily-backup
    """
    from .templates import TemplateManager, BackupTemplate

    manager = TemplateManager()

    if from_profile:
        template = manager.create_from_profile(
            profile_name=from_profile,
            template_id=template_id,
            template_name=name,
            description=description,
        )

        if template is None:
            print_error(f"Profile not found: {from_profile}")
            sys.exit(1)
    else:
        template = BackupTemplate(
            id=template_id,
            name=name,
            description=description,
            category="custom",
        )
        manager.add_custom(template)

    print_success(f"Template '{template_id}' created!")
    console.print("   [dim]Use 'farmore template-show' to view details[/dim]")


@app.command("template-delete")
def delete_template(
    template_id: str = typer.Argument(..., help="Template ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """
    Delete a custom template (built-in templates cannot be deleted).

    Example:
        farmore template-delete my-template
    """
    from .templates import TemplateManager

    manager = TemplateManager()

    # Check if it's a built-in template
    for t in manager.list_builtin():
        if t.id == template_id:
            print_error("Cannot delete built-in templates")
            sys.exit(1)

    if not force:
        confirm = typer.confirm(f"Delete template '{template_id}'?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    if manager.remove_custom(template_id):
        print_success(f"Template '{template_id}' deleted")
    else:
        print_error(f"Template not found: {template_id}")
        sys.exit(1)


# ==============================================================================
# Notification Commands
# ==============================================================================


@app.command("notify-test")
def test_notifications() -> None:
    """
    Test all configured notification providers.

    "Test your notifications before disaster strikes." — schema.cx

    Example:
        farmore notify-test
    """
    from .notifications import NotificationManager

    manager = NotificationManager()

    if not manager.providers:
        print_warning("No notification providers configured")
        console.print("   [dim]Configure notifications in ~/.config/farmore/.farmore_notifications.json[/dim]")
        return

    console.print("\n[cyan]🔔 Testing notification providers...[/cyan]")

    results = manager.test_all_providers()

    table = Table(title="🔔 Notification Tests", border_style="cyan")
    table.add_column("Provider", style="bold")
    table.add_column("Status")
    table.add_column("Message", style="dim")

    for provider, (success, message) in results.items():
        status = "[green]✓ Success[/green]" if success else "[red]✗ Failed[/red]"
        table.add_row(provider, status, message)

    console.print()
    console.print(table)


@app.command("notify-status")
def notification_status() -> None:
    """
    Show notification configuration status.

    Example:
        farmore notify-status
    """
    from .notifications import NotificationManager

    manager = NotificationManager()
    config = manager.config

    table = Table(title="🔔 Notification Configuration", border_style="cyan", show_header=False)
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("[bold]Email[/bold]", "")
    table.add_row("Enabled", "[green]Yes[/green]" if config.email_enabled else "[dim]No[/dim]")
    if config.email_enabled:
        table.add_row("SMTP Host", config.email_smtp_host or "[dim]Not set[/dim]")
        table.add_row("Recipients", ", ".join(config.email_to) if config.email_to else "[dim]None[/dim]")

    table.add_row("", "")
    table.add_row("[bold]Slack[/bold]", "")
    table.add_row("Enabled", "[green]Yes[/green]" if config.slack_enabled else "[dim]No[/dim]")
    if config.slack_enabled:
        table.add_row("Channel", config.slack_channel or "[dim]Default[/dim]")

    table.add_row("", "")
    table.add_row("[bold]Discord[/bold]", "")
    table.add_row("Enabled", "[green]Yes[/green]" if config.discord_enabled else "[dim]No[/dim]")

    table.add_row("", "")
    table.add_row("[bold]Webhook[/bold]", "")
    table.add_row("Enabled", "[green]Yes[/green]" if config.webhook_enabled else "[dim]No[/dim]")
    if config.webhook_enabled:
        table.add_row("URL", config.webhook_url[:40] + "..." if len(config.webhook_url) > 40 else config.webhook_url)

    table.add_row("", "")
    table.add_row("[bold]Preferences[/bold]", "")
    table.add_row("Notify on Success", "Yes" if config.notify_on_success else "No")
    table.add_row("Notify on Failure", "Yes" if config.notify_on_failure else "No")
    table.add_row("Notify on Warning", "Yes" if config.notify_on_warning else "No")

    console.print()
    console.print(table)
    console.print(f"\n   [dim]Config path: {manager.config_dir / manager.CONFIG_FILE}[/dim]")


@app.command()
def transfer(
    repos: str = typer.Argument(
        ...,
        help="Repository name(s): single name, comma-separated, or @file.txt",
    ),
    org: str = typer.Option(
        ...,
        "--org",
        "-o",
        help="Target organization name (required)",
    ),
    source_owner: str | None = typer.Option(
        None,
        "--source-owner",
        "--owner",
        help="Source owner username (default: authenticated user)",
    ),
    new_name: str | None = typer.Option(
        None,
        "--new-name",
        "-n",
        help="New repository name (only valid for single repo transfer)",
    ),
    team_ids: str | None = typer.Option(
        None,
        "--team-ids",
        help="Comma-separated team IDs to grant access",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate only, do not execute transfer",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="GitHub Personal Access Token (prefer GITHUB_TOKEN env var)",
        envvar="GITHUB_TOKEN",
    ),
) -> None:
    """
    Transfer repository(ies) to a GitHub organization.

    "Moving repos is like moving houses. Don't forget the keys." — schema.cx

    ⚠️  WARNING: Repository transfers are significant operations. Use --dry-run first!

    Example:
        farmore transfer my-repo --org my-org
        farmore transfer repo1,repo2,repo3 --org my-org
        farmore transfer @repos.txt --org my-org
        farmore transfer my-repo --org my-org --new-name new-repo-name
        farmore transfer my-repo --org my-org --dry-run
    """
    from .transfer import (
        TransferClient,
        TransferError,
        TransferSummary,
        parse_repo_list,
        parse_team_ids,
        validate_org_name,
        validate_repo_name,
    )
    from rich.panel import Panel

    # Validate token
    if not token:
        print_error("GitHub token is required. Set GITHUB_TOKEN environment variable or use --token")
        sys.exit(1)

    # Validate organization name
    org_valid, org_msg = validate_org_name(org)
    if not org_valid:
        print_error(f"Invalid organization name: {org_msg}")
        sys.exit(1)

    # Parse repository list
    try:
        repo_list = parse_repo_list(repos)
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)

    if not repo_list:
        print_error("No repositories specified")
        sys.exit(1)

    # Validate new_name is only used with single repo
    if new_name and len(repo_list) > 1:
        print_error("--new-name can only be used when transferring a single repository")
        sys.exit(1)

    # Validate repository names
    for repo_name in repo_list:
        valid, msg = validate_repo_name(repo_name)
        if not valid:
            print_error(f"Invalid repository name '{repo_name}': {msg}")
            sys.exit(1)

    # Parse team IDs
    try:
        team_id_list = parse_team_ids(team_ids)
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)

    # Display transfer plan
    mode_text = "[yellow]DRY RUN[/yellow]" if dry_run else "[red]LIVE[/red]"
    console.print(Panel(
        f"[bold]Repository Transfer[/bold]\n\n"
        f"Mode: {mode_text}\n"
        f"Repositories: {len(repo_list)}\n"
        f"Target Organization: [cyan]{org}[/cyan]\n"
        f"{'New Name: ' + new_name if new_name else ''}",
        title="🚀 Transfer Plan",
        border_style="cyan",
    ))

    try:
        with TransferClient(token) as client:
            # Get source owner (default to authenticated user)
            if source_owner is None:
                source_owner = client.get_authenticated_user()
                console.print(f"[dim]Using authenticated user as source: {source_owner}[/dim]")

            summary = TransferSummary()

            for repo_name in repo_list:
                result = client.transfer_repository(
                    source_owner=source_owner,
                    repo_name=repo_name,
                    target_org=org,
                    new_name=new_name if len(repo_list) == 1 else None,
                    team_ids=team_id_list,
                    dry_run=dry_run,
                )
                summary.add_result(result)

            # Print summary
            console.print("\n" + "=" * 60)
            console.print("[bold]Transfer Summary[/bold]")
            console.print("=" * 60)

            if dry_run:
                console.print(f"[yellow]DRY RUN - No transfers were executed[/yellow]")

            console.print(f"Total: {summary.total}")
            console.print(f"[green]Successful: {summary.successful}[/green]")
            console.print(f"[red]Failed: {summary.failed}[/red]")

            if summary.failed_repos:
                console.print("\n[red]Failed Transfers:[/red]")
                for result in summary.failed_repos:
                    console.print(f"  • {result.repo_name}: {result.error}")

            # Exit code
            if summary.failed > 0:
                sys.exit(1)
            sys.exit(0)

    except TransferError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    app()
