"""
Restore functionality for Farmore.

"Backups are insurance. Restores are the payout." — schema.cx
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


@dataclass
class RestoreResult:
    """
    Result of a restore operation.

    "Every restore tells a story of recovery." — schema.cx
    """

    success: bool
    item_type: str  # "issue", "release", "label", etc.
    item_name: str
    source_path: Path | None = None
    target_repo: str = ""

    # Counts
    items_restored: int = 0
    items_skipped: int = 0
    items_failed: int = 0

    # Details
    restored_items: list[str] = field(default_factory=list)
    skipped_items: list[str] = field(default_factory=list)
    failed_items: list[dict[str, str]] = field(default_factory=list)

    # Metadata
    restored_at: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "item_type": self.item_type,
            "item_name": self.item_name,
            "source_path": str(self.source_path) if self.source_path else None,
            "target_repo": self.target_repo,
            "items_restored": self.items_restored,
            "items_skipped": self.items_skipped,
            "items_failed": self.items_failed,
            "restored_items": self.restored_items,
            "skipped_items": self.skipped_items,
            "failed_items": self.failed_items,
            "restored_at": self.restored_at,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }


class RestoreManager:
    """
    Manages restore operations from backups to GitHub.

    "Restoration is the art of bringing the past into the present." — schema.cx
    """

    def __init__(
        self,
        token: str,
        github_host: str = "https://api.github.com",
    ) -> None:
        """
        Initialize the restore manager.

        Args:
            token: GitHub API token
            github_host: GitHub API host URL
        """
        self.token = token
        self.github_host = github_host.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Farmore-Restore/0.7.0",
            }
        )

    def restore_issues(
        self,
        backup_path: Path,
        target_repo: str,
        skip_existing: bool = True,
        dry_run: bool = False,
    ) -> RestoreResult:
        """
        Restore issues from a backup to a GitHub repository.

        Args:
            backup_path: Path to the issues backup file (JSON)
            target_repo: Target repository (owner/repo format)
            skip_existing: Skip issues with matching titles
            dry_run: If True, don't actually create issues

        Returns:
            RestoreResult with restoration details
        """
        import time

        start_time = time.time()

        result = RestoreResult(
            success=True,
            item_type="issue",
            item_name="issues",
            source_path=backup_path,
            target_repo=target_repo,
        )

        # Load backup file
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                issues = json.load(f)
        except Exception as e:
            result.success = False
            result.error_message = f"Failed to load backup file: {str(e)}"
            result.duration_seconds = time.time() - start_time
            return result

        if not isinstance(issues, list):
            issues = [issues]

        # Get existing issues if skip_existing
        existing_titles: set[str] = set()
        if skip_existing:
            existing_titles = self._get_existing_issue_titles(target_repo)

        # Restore each issue
        for issue in issues:
            title = issue.get("title", "")

            if title in existing_titles:
                result.items_skipped += 1
                result.skipped_items.append(title)
                continue

            if dry_run:
                result.items_restored += 1
                result.restored_items.append(f"[DRY RUN] {title}")
                continue

            success, error = self._create_issue(target_repo, issue)
            if success:
                result.items_restored += 1
                result.restored_items.append(title)
            else:
                result.items_failed += 1
                result.failed_items.append({"title": title, "error": error})

        result.success = result.items_failed == 0
        result.duration_seconds = time.time() - start_time
        return result

    def restore_releases(
        self,
        backup_path: Path,
        target_repo: str,
        skip_existing: bool = True,
        dry_run: bool = False,
    ) -> RestoreResult:
        """
        Restore releases from a backup to a GitHub repository.

        Args:
            backup_path: Path to the releases backup directory or file
            target_repo: Target repository (owner/repo format)
            skip_existing: Skip releases with matching tags
            dry_run: If True, don't actually create releases

        Returns:
            RestoreResult with restoration details
        """
        import time

        start_time = time.time()

        result = RestoreResult(
            success=True,
            item_type="release",
            item_name="releases",
            source_path=backup_path,
            target_repo=target_repo,
        )

        # Load releases from backup
        releases = []
        try:
            if backup_path.is_file():
                with open(backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    releases = data if isinstance(data, list) else [data]
            elif backup_path.is_dir():
                # Look for release metadata files
                for file in backup_path.glob("*.json"):
                    if file.name == "release.json":
                        with open(file, "r", encoding="utf-8") as f:
                            releases.append(json.load(f))
                    elif file.name != "assets.json":
                        with open(file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                releases.extend(data)
                            else:
                                releases.append(data)
        except Exception as e:
            result.success = False
            result.error_message = f"Failed to load backup: {str(e)}"
            result.duration_seconds = time.time() - start_time
            return result

        # Get existing releases if skip_existing
        existing_tags: set[str] = set()
        if skip_existing:
            existing_tags = self._get_existing_release_tags(target_repo)

        # Restore each release
        for release in releases:
            tag = release.get("tag_name", "")

            if tag in existing_tags:
                result.items_skipped += 1
                result.skipped_items.append(tag)
                continue

            if dry_run:
                result.items_restored += 1
                result.restored_items.append(f"[DRY RUN] {tag}")
                continue

            success, error = self._create_release(target_repo, release)
            if success:
                result.items_restored += 1
                result.restored_items.append(tag)
            else:
                result.items_failed += 1
                result.failed_items.append({"tag": tag, "error": error})

        result.success = result.items_failed == 0
        result.duration_seconds = time.time() - start_time
        return result

    def restore_labels(
        self,
        backup_path: Path,
        target_repo: str,
        skip_existing: bool = True,
        dry_run: bool = False,
    ) -> RestoreResult:
        """
        Restore labels from a backup to a GitHub repository.

        Args:
            backup_path: Path to the labels backup file (JSON)
            target_repo: Target repository (owner/repo format)
            skip_existing: Skip labels with matching names
            dry_run: If True, don't actually create labels

        Returns:
            RestoreResult with restoration details
        """
        import time

        start_time = time.time()

        result = RestoreResult(
            success=True,
            item_type="label",
            item_name="labels",
            source_path=backup_path,
            target_repo=target_repo,
        )

        # Load backup file
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                labels = json.load(f)
        except Exception as e:
            result.success = False
            result.error_message = f"Failed to load backup file: {str(e)}"
            result.duration_seconds = time.time() - start_time
            return result

        if not isinstance(labels, list):
            labels = [labels]

        # Get existing labels if skip_existing
        existing_names: set[str] = set()
        if skip_existing:
            existing_names = self._get_existing_label_names(target_repo)

        # Restore each label
        for label in labels:
            name = label.get("name", "")

            if name.lower() in {n.lower() for n in existing_names}:
                result.items_skipped += 1
                result.skipped_items.append(name)
                continue

            if dry_run:
                result.items_restored += 1
                result.restored_items.append(f"[DRY RUN] {name}")
                continue

            success, error = self._create_label(target_repo, label)
            if success:
                result.items_restored += 1
                result.restored_items.append(name)
            else:
                result.items_failed += 1
                result.failed_items.append({"name": name, "error": error})

        result.success = result.items_failed == 0
        result.duration_seconds = time.time() - start_time
        return result

    def restore_milestones(
        self,
        backup_path: Path,
        target_repo: str,
        skip_existing: bool = True,
        dry_run: bool = False,
    ) -> RestoreResult:
        """
        Restore milestones from a backup to a GitHub repository.

        Args:
            backup_path: Path to the milestones backup file (JSON)
            target_repo: Target repository (owner/repo format)
            skip_existing: Skip milestones with matching titles
            dry_run: If True, don't actually create milestones

        Returns:
            RestoreResult with restoration details
        """
        import time

        start_time = time.time()

        result = RestoreResult(
            success=True,
            item_type="milestone",
            item_name="milestones",
            source_path=backup_path,
            target_repo=target_repo,
        )

        # Load backup file
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                milestones = json.load(f)
        except Exception as e:
            result.success = False
            result.error_message = f"Failed to load backup file: {str(e)}"
            result.duration_seconds = time.time() - start_time
            return result

        if not isinstance(milestones, list):
            milestones = [milestones]

        # Get existing milestones if skip_existing
        existing_titles: set[str] = set()
        if skip_existing:
            existing_titles = self._get_existing_milestone_titles(target_repo)

        # Restore each milestone
        for milestone in milestones:
            title = milestone.get("title", "")

            if title in existing_titles:
                result.items_skipped += 1
                result.skipped_items.append(title)
                continue

            if dry_run:
                result.items_restored += 1
                result.restored_items.append(f"[DRY RUN] {title}")
                continue

            success, error = self._create_milestone(target_repo, milestone)
            if success:
                result.items_restored += 1
                result.restored_items.append(title)
            else:
                result.items_failed += 1
                result.failed_items.append({"title": title, "error": error})

        result.success = result.items_failed == 0
        result.duration_seconds = time.time() - start_time
        return result

    def _get_existing_issue_titles(self, repo: str) -> set[str]:
        """Get existing issue titles in a repository."""
        titles: set[str] = set()
        url = f"{self.github_host}/repos/{repo}/issues"
        params = {"state": "all", "per_page": 100}

        try:
            while url:
                response = self.session.get(url, params=params)
                if response.status_code != 200:
                    break

                for issue in response.json():
                    titles.add(issue.get("title", ""))

                # Handle pagination
                url = response.links.get("next", {}).get("url")
                params = {}  # URL includes params
        except Exception:
            pass

        return titles

    def _get_existing_release_tags(self, repo: str) -> set[str]:
        """Get existing release tags in a repository."""
        tags: set[str] = set()
        url = f"{self.github_host}/repos/{repo}/releases"

        try:
            response = self.session.get(url, params={"per_page": 100})
            if response.status_code == 200:
                for release in response.json():
                    tags.add(release.get("tag_name", ""))
        except Exception:
            pass

        return tags

    def _get_existing_label_names(self, repo: str) -> set[str]:
        """Get existing label names in a repository."""
        names: set[str] = set()
        url = f"{self.github_host}/repos/{repo}/labels"

        try:
            response = self.session.get(url, params={"per_page": 100})
            if response.status_code == 200:
                for label in response.json():
                    names.add(label.get("name", ""))
        except Exception:
            pass

        return names

    def _get_existing_milestone_titles(self, repo: str) -> set[str]:
        """Get existing milestone titles in a repository."""
        titles: set[str] = set()
        url = f"{self.github_host}/repos/{repo}/milestones"

        try:
            response = self.session.get(url, params={"state": "all", "per_page": 100})
            if response.status_code == 200:
                for milestone in response.json():
                    titles.add(milestone.get("title", ""))
        except Exception:
            pass

        return titles

    def _create_issue(self, repo: str, issue: dict[str, Any]) -> tuple[bool, str]:
        """Create an issue in a repository."""
        url = f"{self.github_host}/repos/{repo}/issues"

        payload = {
            "title": issue.get("title", "Untitled"),
            "body": issue.get("body", ""),
        }

        # Add labels if present
        if "labels" in issue:
            payload["labels"] = [
                label.get("name", label) if isinstance(label, dict) else label
                for label in issue["labels"]
            ]

        try:
            response = self.session.post(url, json=payload)
            if response.status_code == 201:
                return True, ""
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            return False, str(e)

    def _create_release(self, repo: str, release: dict[str, Any]) -> tuple[bool, str]:
        """Create a release in a repository."""
        url = f"{self.github_host}/repos/{repo}/releases"

        payload = {
            "tag_name": release.get("tag_name", ""),
            "name": release.get("name", release.get("tag_name", "")),
            "body": release.get("body", ""),
            "draft": release.get("draft", False),
            "prerelease": release.get("prerelease", False),
        }

        if release.get("target_commitish"):
            payload["target_commitish"] = release["target_commitish"]

        try:
            response = self.session.post(url, json=payload)
            if response.status_code == 201:
                return True, ""
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            return False, str(e)

    def _create_label(self, repo: str, label: dict[str, Any]) -> tuple[bool, str]:
        """Create a label in a repository."""
        url = f"{self.github_host}/repos/{repo}/labels"

        payload = {
            "name": label.get("name", ""),
            "color": label.get("color", "ededed").lstrip("#"),
            "description": label.get("description", ""),
        }

        try:
            response = self.session.post(url, json=payload)
            if response.status_code == 201:
                return True, ""
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            return False, str(e)

    def _create_milestone(self, repo: str, milestone: dict[str, Any]) -> tuple[bool, str]:
        """Create a milestone in a repository."""
        url = f"{self.github_host}/repos/{repo}/milestones"

        payload = {
            "title": milestone.get("title", ""),
            "description": milestone.get("description", ""),
            "state": milestone.get("state", "open"),
        }

        if milestone.get("due_on"):
            payload["due_on"] = milestone["due_on"]

        try:
            response = self.session.post(url, json=payload)
            if response.status_code == 201:
                return True, ""
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            return False, str(e)


def restore_from_backup(
    backup_path: Path,
    target_repo: str,
    token: str,
    item_type: str = "issues",
    skip_existing: bool = True,
    dry_run: bool = False,
    github_host: str = "https://api.github.com",
) -> RestoreResult:
    """
    Convenience function to restore from a backup.

    "Convenience is the bridge between capability and adoption." — schema.cx
    """
    manager = RestoreManager(token, github_host)

    if item_type == "issues":
        return manager.restore_issues(backup_path, target_repo, skip_existing, dry_run)
    elif item_type == "releases":
        return manager.restore_releases(backup_path, target_repo, skip_existing, dry_run)
    elif item_type == "labels":
        return manager.restore_labels(backup_path, target_repo, skip_existing, dry_run)
    elif item_type == "milestones":
        return manager.restore_milestones(backup_path, target_repo, skip_existing, dry_run)
    else:
        return RestoreResult(
            success=False,
            item_type=item_type,
            item_name=item_type,
            error_message=f"Unknown item type: {item_type}",
        )
