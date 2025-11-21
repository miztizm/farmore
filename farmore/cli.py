"""
Farmore CLI interface.

"The command line is where the real work happens. Everything else is just theater." — schema.cx
"""

import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

import requests
import typer
import yaml
from dotenv import load_dotenv
from rich.progress import Progress
from rich.table import Table

from .git_utils import GitOperations
from .github_api import GitHubAPIClient
from .mirror import MirrorOrchestrator
from .models import Config, RepositoryCategory, TargetType, Visibility
from .rich_utils import (
    console,
    print_error,
    print_info,
    print_panel,
    print_success,
    print_warning,
)

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
    
    Args:
        repository: Repository string in format 'owner/repo'
    
    Returns:
        Tuple of (owner, repo) if valid
        
    Raises:
        ValueError: If format is invalid or contains disallowed characters
        
    Security:
        Prevents command injection by validating against GitHub's allowed characters.
        GitHub repository names allow: alphanumeric, hyphens, underscores, and periods.
    """
    import re
    
    parts = repository.split("/")
    if len(parts) != 2:
        raise ValueError("Repository must be in format 'owner/repo'")
    
    owner, repo = parts
    
    # Validate owner and repo names (GitHub's allowed characters)
    # Pattern: alphanumeric, hyphens, underscores, periods (no spaces or special chars)
    github_name_pattern = r'^[a-zA-Z0-9._-]+$'
    
    if not re.match(github_name_pattern, owner):
        raise ValueError(f"Invalid owner name '{owner}'. Only alphanumeric characters, '.', '-', and '_' allowed.")
    
    if not re.match(github_name_pattern, repo):
        raise ValueError(f"Invalid repository name '{repo}'. Only alphanumeric characters, '.', '-', and '_' allowed.")
    
    # Additional length validation (GitHub limits)
    if len(owner) > 39:  # GitHub username max length
        raise ValueError(f"Owner name too long (max 39 characters): '{owner}'")
    
    if len(repo) > 100:  # GitHub repo name max length
        raise ValueError(f"Repository name too long (max 100 characters): '{repo}'")
    
    return owner, repo


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
    Backup all repositories for a GitHub user.

    "Every user has secrets. Make sure their repos aren't lost." — schema.cx

    Example:
        farmore user miztizm
        farmore user miztizm --dest ./custom_backups
        farmore user miztizm --include-issues --include-pulls --include-wikis
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
        dry_run=dry_run,
        max_workers=max_workers,
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
    Backup all repositories for a GitHub organization.

    "Organizations are just users with trust issues. And more repos." — schema.cx

    Example:
        farmore org github
        farmore org github --dest ./custom_backups
        farmore org myorg --include-issues --include-pulls --include-wikis
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
        dry_run=dry_run,
        max_workers=max_workers,
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


if __name__ == "__main__":
    app()
