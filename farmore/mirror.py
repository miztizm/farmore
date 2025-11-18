"""
Repository mirroring orchestration with parallel execution.

"Parallelism is just organized chaos. But faster." — schema.cx
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .git_utils import GitOperations
from .github_api import GitHubAPIClient, GitHubAPIError
from .models import Config, MirrorResult, MirrorSummary, Repository

console = Console()


class MirrorOrchestrator:
    """
    Orchestrates repository mirroring operations.

    "Orchestration is just delegation with a fancy name." — schema.cx
    """

    def __init__(self, config: Config) -> None:
        """Initialize the mirror orchestrator."""
        self.config = config
        self.git_ops = GitOperations()

    def run(self, repos: list[Repository] | None = None) -> MirrorSummary:
        """
        Run the mirror operation.

        "Every journey begins with a single API call." — schema.cx

        Args:
            repos: Optional list of repositories to mirror. If None, fetches from GitHub API.
        """
        summary = MirrorSummary()

        try:
            # Fetch repositories from GitHub if not provided
            if repos is None:
                console.print(
                    f"\n[cyan]Discovering repositories for {self.config.target_type.value} "
                    f"'{self.config.target_name}'...[/cyan]"
                )

                if not self.config.token:
                    console.print(
                        "[yellow]⚠ No GITHUB_TOKEN found; only public repositories "
                        "will be mirrored.[/yellow]"
                    )

                api_client = GitHubAPIClient(self.config)
                repos = api_client.get_repositories()

            if not repos:
                console.print(
                    "[yellow]No repositories found matching the specified filters.[/yellow]"
                )
                return summary

            console.print(f"[green]✓ Found {len(repos)} repositories[/green]\n")

            # Process repositories
            if self.config.dry_run:
                console.print(
                    "[yellow]DRY RUN MODE - No actual operations will be performed[/yellow]\n"
                )
                self._dry_run_repos(repos, summary)
            else:
                self._mirror_repos(repos, summary)

            # Print summary
            self._print_summary(summary)

        except GitHubAPIError as e:
            console.print(f"[red]✗ GitHub API Error: {e}[/red]")
            summary.errors.append(str(e))
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
        except Exception as e:
            console.print(f"[red]✗ Unexpected error: {e}[/red]")
            summary.errors.append(str(e))

        return summary

    def _dry_run_repos(self, repos: list[Repository], summary: MirrorSummary) -> None:
        """Perform a dry run (just print what would be done)."""
        for repo in repos:
            # Use categorized path
            dest_path = self.config.dest / self.config.get_repo_category_path(repo)

            if dest_path.exists() and self.git_ops.is_git_repository(dest_path):
                action = "UPDATE"
                console.print(f"[blue]{action:8}[/blue] {repo.full_name}")
            else:
                action = "CLONE"
                console.print(f"[green]{action:8}[/green] {repo.full_name} -> {dest_path}")

            # Count as skipped in dry run
            result = MirrorResult(repo=repo, success=True, action="skipped", message="Dry run")
            summary.add_result(result)

    def _mirror_repos(self, repos: list[Repository], summary: MirrorSummary) -> None:
        """
        Mirror repositories with parallel execution.

        "Threading is just multitasking for computers. They're better at it." — schema.cx
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Mirroring repositories...", total=len(repos))

            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                # Submit all tasks
                future_to_repo = {
                    executor.submit(self._mirror_single_repo, repo): repo for repo in repos
                }

                # Process completed tasks
                for future in as_completed(future_to_repo):
                    result = future.result()
                    summary.add_result(result)
                    self._print_result(result)
                    progress.advance(task)

    def _mirror_single_repo(self, repo: Repository) -> MirrorResult:
        """
        Mirror a single repository.

        "One repo at a time. That's how you build an empire." — schema.cx
        """
        # Use categorized path
        dest_path = self.config.dest / self.config.get_repo_category_path(repo)

        try:
            # Check if repo already exists
            if dest_path.exists():
                if not self.git_ops.is_git_repository(dest_path):
                    return MirrorResult(
                        repo=repo,
                        success=False,
                        action="failed",
                        error=f"Path exists but is not a git repository: {dest_path}",
                    )

                # Verify remote URL matches
                remote_url = self.git_ops.get_remote_url(dest_path)
                expected_urls = [repo.ssh_url, repo.clone_url]

                if remote_url and not any(
                    remote_url.rstrip("/") == url.rstrip("/") for url in expected_urls
                ):
                    return MirrorResult(
                        repo=repo,
                        success=False,
                        action="skipped",
                        message=f"Remote URL mismatch (expected one of {expected_urls}, got {remote_url})",
                    )

                # Update existing repo
                success, message = self.git_ops.update(repo, dest_path)
                action = "updated" if success else "failed"
                return MirrorResult(
                    repo=repo,
                    success=success,
                    action=action,
                    message=message,
                    error=None if success else message,
                )
            else:
                # Clone new repo
                success, message = self._clone_with_fallback(repo, dest_path)
                action = "cloned" if success else "failed"
                return MirrorResult(
                    repo=repo,
                    success=success,
                    action=action,
                    message=message,
                    error=None if success else message,
                )

        except Exception as e:
            return MirrorResult(repo=repo, success=False, action="failed", error=str(e))

    def _clone_with_fallback(self, repo: Repository, dest_path: Path) -> tuple[bool, str]:
        """
        Clone with SSH, fallback to HTTPS if SSH fails.

        "Trust SSH. But verify with HTTPS." — schema.cx
        """
        # Try SSH first if configured
        if self.config.use_ssh:
            success, message = self.git_ops.clone(repo, dest_path, use_ssh=True)
            if success:
                return True, message

            # If SSH failed due to auth, try HTTPS
            if "SSH authentication failed" in message and self.config.token:
                success, message = self.git_ops.clone(repo, dest_path, use_ssh=False)
                if success:
                    return True, f"{message} (via HTTPS)"
                return False, message
            return False, message
        else:
            # Use HTTPS directly
            return self.git_ops.clone(repo, dest_path, use_ssh=False)

    def _print_result(self, result: MirrorResult) -> None:
        """Print the result of a mirror operation."""
        if result.success:
            if result.action == "cloned":
                console.print(
                    f"[green]CLONE   [/green] {result.repo.full_name} -> "
                    f"{self.config.dest / self.config.get_repo_category_path(result.repo)}"
                )
            elif result.action == "updated":
                console.print(f"[blue]UPDATE  [/blue] {result.repo.full_name}")
            elif result.action == "skipped":
                console.print(
                    f"[yellow]SKIP    [/yellow] {result.repo.full_name} ({result.message})"
                )
        else:
            console.print(f"[red]FAIL    [/red] {result.repo.full_name}: {result.error}")

    def _print_summary(self, summary: MirrorSummary) -> None:
        """
        Print operation summary.

        "Numbers tell the story. Make sure it's a good one." — schema.cx
        """
        console.print("\n" + "=" * 60)
        console.print("[bold]Summary[/bold]")
        console.print("=" * 60)
        console.print(f"Total repositories: {summary.total}")
        console.print(f"[green]✓ Cloned:  {summary.cloned}[/green]")
        console.print(f"[blue]✓ Updated: {summary.updated}[/blue]")
        console.print(f"[yellow]⊘ Skipped: {summary.skipped}[/yellow]")
        console.print(f"[red]✗ Failed:  {summary.failed}[/red]")

        if summary.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in summary.errors:
                console.print(f"  • {error}")

        console.print("=" * 60 + "\n")
