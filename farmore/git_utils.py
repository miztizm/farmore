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
        # Also check for bare repositories (no .git folder, but has HEAD)
        bare_head = path / "HEAD"
        return (git_dir.exists() and git_dir.is_dir()) or (bare_head.exists() and (path / "objects").exists())

    @staticmethod
    def is_lfs_available() -> bool:
        """
        Check if git-lfs is installed and available.
        
        "LFS: Large File Storage. Or 'Let's Find Solutions' for big repos." — schema.cx
        """
        try:
            result = subprocess.run(
                ["git", "lfs", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

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
    def clone(
        repo: Repository,
        dest_path: Path,
        use_ssh: bool = True,
        bare: bool = False,
        lfs: bool = False,
    ) -> tuple[bool, str]:
        """
        Clone a repository.

        "Cloning is just copying with extra steps and version control." — schema.cx

        Args:
            repo: Repository to clone
            dest_path: Destination path for the clone
            use_ssh: Whether to use SSH (True) or HTTPS (False)
            bare: Whether to create a bare/mirror clone (preserves all refs)
            lfs: Whether to use Git LFS for cloning (for repos with large files)

        Returns:
            Tuple of (success, message)
        """
        # Choose URL based on protocol preference
        url = repo.ssh_url if use_ssh else repo.clone_url

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Check LFS availability if requested
        if lfs and not GitOperations.is_lfs_available():
            return False, "Git LFS not installed. Install with: git lfs install"

        try:
            # Build the clone command based on options
            if lfs:
                # Use git lfs clone for LFS-enabled repos
                cmd = ["git", "lfs", "clone", url, str(dest_path)]
            elif bare:
                # Use --mirror for true 1:1 backup (all refs, branches, tags)
                cmd = ["git", "clone", "--mirror", url, str(dest_path)]
            else:
                # Standard clone
                cmd = ["git", "clone", url, str(dest_path)]

            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=600 if lfs else 300,  # 10 min for LFS, 5 min otherwise
            )
            
            # Build success message
            mode_suffix = ""
            if bare:
                mode_suffix = " (mirror)"
            elif lfs:
                mode_suffix = " (with LFS)"
            
            return True, f"Cloned successfully{mode_suffix}"
        except subprocess.TimeoutExpired:
            return False, "Clone operation timed out"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)

            # If SSH failed, suggest HTTPS fallback
            if use_ssh and ("Permission denied" in error_msg or "publickey" in error_msg):
                return False, "SSH authentication failed (try HTTPS with token)"

            return False, f"Clone failed: {error_msg}"

    @staticmethod
    def fetch(path: Path, prune: bool = True) -> tuple[bool, str]:
        """
        Fetch updates from remote.

        Args:
            path: Path to the git repository
            prune: Whether to prune deleted remote branches (default: True)

        Returns:
            Tuple of (success, message)
        """
        if not GitOperations.is_git_repository(path):
            return False, "Not a git repository"

        try:
            cmd = ["git", "fetch", "--all"]
            if prune:
                cmd.append("--prune")
            
            subprocess.run(
                cmd,
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
    def fetch_lfs(path: Path) -> tuple[bool, str]:
        """
        Fetch LFS objects from remote.

        Args:
            path: Path to the git repository

        Returns:
            Tuple of (success, message)
        """
        if not GitOperations.is_git_repository(path):
            return False, "Not a git repository"

        if not GitOperations.is_lfs_available():
            return False, "Git LFS not installed"

        try:
            subprocess.run(
                ["git", "lfs", "fetch", "--all"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
                timeout=600,  # LFS can take longer
            )
            return True, "LFS objects fetched successfully"
        except subprocess.TimeoutExpired:
            return False, "LFS fetch operation timed out"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            return False, f"LFS fetch failed: {error_msg}"

    @staticmethod
    def update_mirror(path: Path) -> tuple[bool, str]:
        """
        Update a bare/mirror repository by fetching all refs.

        Args:
            path: Path to the bare git repository

        Returns:
            Tuple of (success, message)
        """
        if not GitOperations.is_git_repository(path):
            return False, "Not a git repository"

        try:
            subprocess.run(
                ["git", "remote", "update", "--prune"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            return True, "Mirror updated successfully"
        except subprocess.TimeoutExpired:
            return False, "Mirror update operation timed out"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            return False, f"Mirror update failed: {error_msg}"

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
    def update(repo: Repository, path: Path, lfs: bool = False, bare: bool = False) -> tuple[bool, str]:
        """
        Update an existing repository (fetch + pull, or mirror update for bare repos).

        Args:
            repo: Repository information
            path: Path to the git repository
            lfs: Whether to also fetch LFS objects
            bare: Whether this is a bare/mirror repository

        Returns:
            Tuple of (success, message)
        """
        if bare:
            # For mirror/bare repos, use remote update
            return GitOperations.update_mirror(path)
        
        # Fetch first
        success, message = GitOperations.fetch(path)
        if not success:
            return False, message

        # Optionally fetch LFS objects
        if lfs and GitOperations.is_lfs_available():
            lfs_success, lfs_message = GitOperations.fetch_lfs(path)
            if not lfs_success:
                # Log warning but continue
                pass

        # Then pull
        success, message = GitOperations.pull(path, repo.default_branch)
        return success, message
