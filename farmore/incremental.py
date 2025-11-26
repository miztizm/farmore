"""
Incremental backup state management for Farmore.

"The difference between a backup and a disaster is timestamps." — schema.cx

This module provides state tracking for incremental backups, allowing farmore
to only fetch data that has changed since the last successful backup run.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class BackupState:
    """
    Stores state for incremental backups.

    "State is just organized memory. Don't forget it." — schema.cx
    """

    # When this backup state was created/updated
    last_backup: str  # ISO timestamp
    version: str = "0.6.0"

    # What was backed up
    target_type: str = ""  # "user" or "org"
    target_name: str = ""

    # Repository tracking
    repos_backed_up: list[str] = field(default_factory=list)
    repos_updated: dict[str, str] = field(default_factory=dict)  # repo -> last_updated_at

    # Data tracking (for issues, PRs, etc.)
    issues_since: dict[str, str] = field(default_factory=dict)  # repo -> last issue updated_at
    pulls_since: dict[str, str] = field(default_factory=dict)  # repo -> last PR updated_at

    # Gists tracking
    gists_backed_up: list[str] = field(default_factory=list)

    # Statistics
    total_repos: int = 0
    total_issues: int = 0
    total_pulls: int = 0
    total_gists: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupState":
        """Create from dictionary."""
        return cls(
            last_backup=data.get("last_backup", ""),
            version=data.get("version", "0.6.0"),
            target_type=data.get("target_type", ""),
            target_name=data.get("target_name", ""),
            repos_backed_up=data.get("repos_backed_up", []),
            repos_updated=data.get("repos_updated", {}),
            issues_since=data.get("issues_since", {}),
            pulls_since=data.get("pulls_since", {}),
            gists_backed_up=data.get("gists_backed_up", []),
            total_repos=data.get("total_repos", 0),
            total_issues=data.get("total_issues", 0),
            total_pulls=data.get("total_pulls", 0),
            total_gists=data.get("total_gists", 0),
        )


class IncrementalBackupManager:
    """
    Manages incremental backup state files.

    "Persistence is key. Even when the API says no." — schema.cx

    State is stored in a `.farmore_state.json` file in the backup directory.
    This file tracks:
    - When the last backup was performed
    - Which repositories were backed up
    - When each repository was last updated
    - Timestamps for issues/PRs to enable incremental fetching
    """

    STATE_FILE = ".farmore_state.json"

    def __init__(self, backup_dir: Path) -> None:
        """
        Initialize the incremental backup manager.

        Args:
            backup_dir: Base directory for backups
        """
        self.backup_dir = Path(backup_dir)
        self.state_file = self.backup_dir / self.STATE_FILE
        self._state: BackupState | None = None

    def load_state(self) -> BackupState | None:
        """
        Load existing backup state from disk.

        Returns:
            BackupState if exists, None otherwise
        """
        if not self.state_file.exists():
            return None

        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self._state = BackupState.from_dict(data)
            return self._state
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Corrupted state file - log warning and return None
            from .rich_utils import print_warning
            print_warning(f"Corrupted state file, starting fresh: {e}")
            return None

    def save_state(self, state: BackupState) -> None:
        """
        Save backup state to disk.

        Args:
            state: BackupState to save
        """
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(state.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._state = state

    def get_last_backup_time(self) -> datetime | None:
        """
        Get timestamp of last successful backup.

        Returns:
            datetime if previous backup exists, None otherwise
        """
        state = self.load_state()
        if not state or not state.last_backup:
            return None

        try:
            # Parse ISO timestamp
            return datetime.fromisoformat(state.last_backup.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def get_repo_last_update(self, repo_full_name: str) -> datetime | None:
        """
        Get when a repository was last updated in backup.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            datetime if repo was previously backed up, None otherwise
        """
        state = self.load_state()
        if not state:
            return None

        timestamp = state.repos_updated.get(repo_full_name)
        if not timestamp:
            return None

        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def get_issues_since(self, repo_full_name: str) -> datetime | None:
        """
        Get timestamp for incremental issue fetching.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            datetime to use as 'since' parameter, None for full fetch
        """
        state = self.load_state()
        if not state:
            return None

        timestamp = state.issues_since.get(repo_full_name)
        if not timestamp:
            return None

        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def get_pulls_since(self, repo_full_name: str) -> datetime | None:
        """
        Get timestamp for incremental PR fetching.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            datetime to use as 'since' parameter, None for full fetch
        """
        state = self.load_state()
        if not state:
            return None

        timestamp = state.pulls_since.get(repo_full_name)
        if not timestamp:
            return None

        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def should_update_repo(self, repo_full_name: str, repo_updated_at: str) -> bool:
        """
        Check if a repository needs updating based on GitHub's updated_at.

        Args:
            repo_full_name: Full repository name (owner/repo)
            repo_updated_at: GitHub's updated_at timestamp for the repo

        Returns:
            True if repo should be updated, False if unchanged
        """
        last_backup = self.get_repo_last_update(repo_full_name)
        if not last_backup:
            return True  # Never backed up

        try:
            repo_update_time = datetime.fromisoformat(repo_updated_at.replace("Z", "+00:00"))
            return repo_update_time > last_backup
        except (ValueError, AttributeError):
            return True  # Can't parse, be safe and update

    def create_new_state(
        self,
        target_type: str,
        target_name: str,
    ) -> BackupState:
        """
        Create a new backup state for this run.

        Args:
            target_type: "user" or "org"
            target_name: Username or organization name

        Returns:
            New BackupState initialized for this run
        """
        return BackupState(
            last_backup=datetime.now(timezone.utc).isoformat(),
            target_type=target_type,
            target_name=target_name,
        )

    def update_repo_state(
        self,
        state: BackupState,
        repo_full_name: str,
        updated_at: str | None = None,
    ) -> None:
        """
        Update state after backing up a repository.

        Args:
            state: BackupState to update
            repo_full_name: Full repository name
            updated_at: Repository's updated_at timestamp from GitHub
        """
        if repo_full_name not in state.repos_backed_up:
            state.repos_backed_up.append(repo_full_name)
            state.total_repos += 1

        if updated_at:
            state.repos_updated[repo_full_name] = updated_at

    def update_issues_state(
        self,
        state: BackupState,
        repo_full_name: str,
        latest_updated_at: str | None = None,
        count: int = 0,
    ) -> None:
        """
        Update state after backing up issues.

        Args:
            state: BackupState to update
            repo_full_name: Full repository name
            latest_updated_at: Most recent issue updated_at timestamp
            count: Number of issues backed up
        """
        if latest_updated_at:
            state.issues_since[repo_full_name] = latest_updated_at
        state.total_issues += count

    def update_pulls_state(
        self,
        state: BackupState,
        repo_full_name: str,
        latest_updated_at: str | None = None,
        count: int = 0,
    ) -> None:
        """
        Update state after backing up pull requests.

        Args:
            state: BackupState to update
            repo_full_name: Full repository name
            latest_updated_at: Most recent PR updated_at timestamp
            count: Number of PRs backed up
        """
        if latest_updated_at:
            state.pulls_since[repo_full_name] = latest_updated_at
        state.total_pulls += count

    def update_gist_state(
        self,
        state: BackupState,
        gist_id: str,
    ) -> None:
        """
        Update state after backing up a gist.

        Args:
            state: BackupState to update
            gist_id: Gist ID
        """
        if gist_id not in state.gists_backed_up:
            state.gists_backed_up.append(gist_id)
            state.total_gists += 1

    def finalize_state(self, state: BackupState) -> None:
        """
        Finalize and save state after backup completes.

        Args:
            state: BackupState to finalize and save
        """
        state.last_backup = datetime.now(timezone.utc).isoformat()
        self.save_state(state)

    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of the current backup state.

        Returns:
            Dictionary with state summary
        """
        state = self.load_state()
        if not state:
            return {"exists": False}

        return {
            "exists": True,
            "last_backup": state.last_backup,
            "target": f"{state.target_type}/{state.target_name}",
            "repos_count": len(state.repos_backed_up),
            "total_repos": state.total_repos,
            "total_issues": state.total_issues,
            "total_pulls": state.total_pulls,
            "total_gists": state.total_gists,
        }
