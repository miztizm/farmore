"""
Configuration profile management for Farmore.

"Configuration is just organized preferences. Save them wisely." — schema.cx
"""

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .models import TargetType, Visibility


@dataclass
class BackupProfile:
    """
    A saved backup configuration profile.

    "Profiles are just memories for your settings." — schema.cx
    """

    name: str
    target_type: str  # "user" or "org"
    target_name: str
    dest: str | None = None

    # Filtering options
    visibility: str = "all"
    include_forks: bool = False
    include_archived: bool = False
    exclude_org_repos: bool = False
    exclude_repos: list[str] = field(default_factory=list)
    name_regex: str | None = None

    # Data options
    include_issues: bool = False
    include_pulls: bool = False
    include_workflows: bool = False
    include_releases: bool = False
    include_wikis: bool = False

    # Execution options
    parallel_workers: int = 4
    skip_existing: bool = False
    bare: bool = False
    lfs: bool = False
    incremental: bool = False

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupProfile":
        """Create profile from dictionary."""
        # Handle missing fields with defaults
        return cls(
            name=data.get("name", "unnamed"),
            target_type=data.get("target_type", "user"),
            target_name=data.get("target_name", ""),
            dest=data.get("dest"),
            visibility=data.get("visibility", "all"),
            include_forks=data.get("include_forks", False),
            include_archived=data.get("include_archived", False),
            exclude_org_repos=data.get("exclude_org_repos", False),
            exclude_repos=data.get("exclude_repos", []),
            name_regex=data.get("name_regex"),
            include_issues=data.get("include_issues", False),
            include_pulls=data.get("include_pulls", False),
            include_workflows=data.get("include_workflows", False),
            include_releases=data.get("include_releases", False),
            include_wikis=data.get("include_wikis", False),
            parallel_workers=data.get("parallel_workers", 4),
            skip_existing=data.get("skip_existing", False),
            bare=data.get("bare", False),
            lfs=data.get("lfs", False),
            incremental=data.get("incremental", False),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            description=data.get("description", ""),
        )


class ConfigManager:
    """
    Manages backup configuration profiles.

    "A good manager knows where everything is. Even your configs." — schema.cx
    """

    DEFAULT_CONFIG_DIR = Path.home() / ".config" / "farmore"
    PROFILES_FILE = "profiles.yaml"

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the configuration manager."""
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.profiles_path = self.config_dir / self.PROFILES_FILE
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_profiles(self) -> dict[str, dict[str, Any]]:
        """Load all profiles from the profiles file."""
        if not self.profiles_path.exists():
            return {}

        try:
            with open(self.profiles_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get("profiles", {})
        except Exception:
            return {}

    def _save_profiles(self, profiles: dict[str, dict[str, Any]]) -> None:
        """Save all profiles to the profiles file."""
        with open(self.profiles_path, "w", encoding="utf-8") as f:
            yaml.dump({"profiles": profiles}, f, default_flow_style=False, sort_keys=False)

    def save_profile(self, profile: BackupProfile) -> None:
        """
        Save a backup profile.

        Args:
            profile: The profile to save
        """
        profiles = self._load_profiles()
        profile.updated_at = datetime.now().isoformat()
        profiles[profile.name] = profile.to_dict()
        self._save_profiles(profiles)

    def load_profile(self, name: str) -> BackupProfile | None:
        """
        Load a backup profile by name.

        Args:
            name: The profile name

        Returns:
            The profile if found, None otherwise
        """
        profiles = self._load_profiles()
        if name not in profiles:
            return None
        return BackupProfile.from_dict(profiles[name])

    def delete_profile(self, name: str) -> bool:
        """
        Delete a backup profile.

        Args:
            name: The profile name

        Returns:
            True if deleted, False if not found
        """
        profiles = self._load_profiles()
        if name not in profiles:
            return False
        del profiles[name]
        self._save_profiles(profiles)
        return True

    def list_profiles(self) -> list[BackupProfile]:
        """
        List all saved profiles.

        Returns:
            List of all profiles
        """
        profiles = self._load_profiles()
        return [BackupProfile.from_dict(data) for data in profiles.values()]

    def export_profile(self, name: str, output_path: Path) -> bool:
        """
        Export a profile to a file.

        Args:
            name: The profile name
            output_path: The output file path

        Returns:
            True if exported successfully
        """
        profile = self.load_profile(name)
        if profile is None:
            return False

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(profile.to_dict(), f, default_flow_style=False, sort_keys=False)
        return True

    def import_profile(self, input_path: Path, new_name: str | None = None) -> BackupProfile | None:
        """
        Import a profile from a file.

        Args:
            input_path: The input file path
            new_name: Optional new name for the profile

        Returns:
            The imported profile or None if failed
        """
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if new_name:
                data["name"] = new_name

            profile = BackupProfile.from_dict(data)
            self.save_profile(profile)
            return profile
        except Exception:
            return None

    def get_profile_path(self) -> Path:
        """Get the path to the profiles file."""
        return self.profiles_path


def create_profile_from_args(
    name: str,
    target_type: str,
    target_name: str,
    dest: str | None = None,
    visibility: str = "all",
    include_forks: bool = False,
    include_archived: bool = False,
    exclude_org_repos: bool = False,
    exclude_repos: list[str] | None = None,
    name_regex: str | None = None,
    include_issues: bool = False,
    include_pulls: bool = False,
    include_workflows: bool = False,
    include_releases: bool = False,
    include_wikis: bool = False,
    parallel_workers: int = 4,
    skip_existing: bool = False,
    bare: bool = False,
    lfs: bool = False,
    incremental: bool = False,
    description: str = "",
) -> BackupProfile:
    """
    Create a BackupProfile from CLI arguments.

    "From chaos of arguments, order of configuration emerges." — schema.cx
    """
    return BackupProfile(
        name=name,
        target_type=target_type,
        target_name=target_name,
        dest=dest,
        visibility=visibility,
        include_forks=include_forks,
        include_archived=include_archived,
        exclude_org_repos=exclude_org_repos,
        exclude_repos=exclude_repos or [],
        name_regex=name_regex,
        include_issues=include_issues,
        include_pulls=include_pulls,
        include_workflows=include_workflows,
        include_releases=include_releases,
        include_wikis=include_wikis,
        parallel_workers=parallel_workers,
        skip_existing=skip_existing,
        bare=bare,
        lfs=lfs,
        incremental=incremental,
        description=description,
    )
