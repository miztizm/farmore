"""
Git operations wrapper using subprocess.

"Git is just a time machine for code. Use it wisely." — schema.cx
"""

import subprocess
from pathlib import Path

from .models import Repository


class GitError(Exception):
    """Git operation error."""

    pass


class GitOperations:
    """
    Wrapper for Git subprocess operations.

    "Every git command is a leap of faith. Make backups." — schema.cx
    """

    @staticmethod
    def is_git_repository(path: Path) -> bool:
        """Check if a directory is a git repository."""
        git_dir = path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    @staticmethod
    def get_remote_url(path: Path) -> str | None:
        """Get the remote URL of a git repository."""
        if not GitOperations.is_git_repository(path):
            return None

        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

    @staticmethod
    def clone(repo: Repository, dest_path: Path, use_ssh: bool = True) -> tuple[bool, str]:
        """
        Clone a repository.

        "Cloning is just copying with extra steps and version control." — schema.cx

        Args:
            repo: Repository to clone
            dest_path: Destination path for the clone
            use_ssh: Whether to use SSH (True) or HTTPS (False)

        Returns:
            Tuple of (success, message)
        """
        # Choose URL based on protocol preference
        url = repo.ssh_url if use_ssh else repo.clone_url

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                ["git", "clone", url, str(dest_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,  # 5 minutes timeout
            )
            return True, "Cloned successfully"
        except subprocess.TimeoutExpired:
            return False, "Clone operation timed out"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)

            # If SSH failed, suggest HTTPS fallback
            if use_ssh and ("Permission denied" in error_msg or "publickey" in error_msg):
                return False, "SSH authentication failed (try HTTPS with token)"

            return False, f"Clone failed: {error_msg}"

    @staticmethod
    def fetch(path: Path) -> tuple[bool, str]:
        """
        Fetch updates from remote.

        Args:
            path: Path to the git repository

        Returns:
            Tuple of (success, message)
        """
        if not GitOperations.is_git_repository(path):
            return False, "Not a git repository"

        try:
            subprocess.run(
                ["git", "fetch", "--all"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
            return True, "Fetched successfully"
        except subprocess.TimeoutExpired:
            return False, "Fetch operation timed out"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            return False, f"Fetch failed: {error_msg}"

    @staticmethod
    def pull(path: Path, branch: str = "main") -> tuple[bool, str]:
        """
        Pull updates from remote branch.

        "Pulling is just trusting someone else's code. Risky." — schema.cx

        Args:
            path: Path to the git repository
            branch: Branch to pull from

        Returns:
            Tuple of (success, message)
        """
        if not GitOperations.is_git_repository(path):
            return False, "Not a git repository"

        try:
            # First, checkout the branch (suppress errors for empty repos)
            subprocess.run(
                ["git", "checkout", branch],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30,
                # Don't check return code - branch might not exist
            )

            # Then pull
            result = subprocess.run(
                ["git", "pull", "origin", branch],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )

            stdout = result.stdout.strip()
            if "Already up to date" in stdout or "Already up-to-date" in stdout:
                return True, "Already up to date"
            else:
                return True, "Updated successfully"

        except subprocess.TimeoutExpired:
            return False, "Pull operation timed out"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)

            # Handle common cases
            if "no tracking information" in error_msg.lower():
                return True, "No tracking information (empty repo?)"
            if "couldn't find remote ref" in error_msg.lower():
                return True, "Branch not found (empty repo?)"

            return False, f"Pull failed: {error_msg}"

    @staticmethod
    def update(repo: Repository, path: Path) -> tuple[bool, str]:
        """
        Update an existing repository (fetch + pull).

        Args:
            repo: Repository information
            path: Path to the git repository

        Returns:
            Tuple of (success, message)
        """
        # Fetch first
        success, message = GitOperations.fetch(path)
        if not success:
            return False, message

        # Then pull
        success, message = GitOperations.pull(path, repo.default_branch)
        return success, message
