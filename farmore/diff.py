"""
Farmore Diff/Compare Module - Compare backups and detect changes.

"Change is the only constant. Track it." — schema.cx
"""

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ChangeType(str, Enum):
    """Type of change detected."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class FileChange:
    """Represents a change to a file."""
    path: str
    change_type: ChangeType
    old_hash: str | None = None
    new_hash: str | None = None
    old_size: int | None = None
    new_size: int | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "change_type": self.change_type.value,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "old_size": self.old_size,
            "new_size": self.new_size,
        }


@dataclass
class RepositoryDiff:
    """Difference between two versions of a repository."""
    name: str
    path: Path
    change_type: ChangeType
    commit_diff: int = 0  # Number of new commits
    old_head: str | None = None
    new_head: str | None = None
    commits: list[dict] = field(default_factory=list)
    file_changes: list[FileChange] = field(default_factory=list)
    
    @property
    def files_added(self) -> int:
        return sum(1 for f in self.file_changes if f.change_type == ChangeType.ADDED)
    
    @property
    def files_modified(self) -> int:
        return sum(1 for f in self.file_changes if f.change_type == ChangeType.MODIFIED)
    
    @property
    def files_removed(self) -> int:
        return sum(1 for f in self.file_changes if f.change_type == ChangeType.REMOVED)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": str(self.path),
            "change_type": self.change_type.value,
            "commit_diff": self.commit_diff,
            "old_head": self.old_head,
            "new_head": self.new_head,
            "commits": self.commits,
            "files_added": self.files_added,
            "files_modified": self.files_modified,
            "files_removed": self.files_removed,
            "file_changes": [f.to_dict() for f in self.file_changes],
        }


@dataclass
class BackupDiff:
    """Difference between two backup states."""
    old_path: Path
    new_path: Path
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    repos_added: list[str] = field(default_factory=list)
    repos_removed: list[str] = field(default_factory=list)
    repos_modified: list[RepositoryDiff] = field(default_factory=list)
    repos_unchanged: list[str] = field(default_factory=list)
    
    @property
    def total_changes(self) -> int:
        return len(self.repos_added) + len(self.repos_removed) + len(self.repos_modified)
    
    @property
    def has_changes(self) -> bool:
        return self.total_changes > 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "old_path": str(self.old_path),
            "new_path": str(self.new_path),
            "analyzed_at": self.analyzed_at,
            "repos_added": self.repos_added,
            "repos_removed": self.repos_removed,
            "repos_modified": [r.to_dict() for r in self.repos_modified],
            "repos_unchanged": self.repos_unchanged,
            "total_changes": self.total_changes,
            "summary": {
                "added": len(self.repos_added),
                "removed": len(self.repos_removed),
                "modified": len(self.repos_modified),
                "unchanged": len(self.repos_unchanged),
            },
        }


@dataclass
class SnapshotInfo:
    """Information about a backup snapshot."""
    path: Path
    created_at: str
    repo_count: int
    total_size_bytes: int
    repositories: dict[str, dict] = field(default_factory=dict)  # name -> {head, size, mtime}
    
    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "created_at": self.created_at,
            "repo_count": self.repo_count,
            "total_size_bytes": self.total_size_bytes,
            "repositories": self.repositories,
        }


class BackupCompare:
    """
    Compare backup directories and detect changes.
    
    "Know what changed, and you'll know what matters." — schema.cx
    """
    
    SNAPSHOT_FILE = ".farmore_snapshot.json"
    
    def __init__(self):
        """Initialize the compare engine."""
        pass
    
    def create_snapshot(self, path: Path) -> SnapshotInfo:
        """Create a snapshot of the current backup state."""
        repos = self._find_repositories(path)
        
        snapshot = SnapshotInfo(
            path=path,
            created_at=datetime.now().isoformat(),
            repo_count=len(repos),
            total_size_bytes=0,
            repositories={},
        )
        
        for repo_path in repos:
            repo_name = str(repo_path.relative_to(path))
            
            # Get HEAD commit
            head = self._get_head_commit(repo_path)
            
            # Get size
            size = self._get_directory_size(repo_path)
            snapshot.total_size_bytes += size
            
            # Get modification time
            mtime = repo_path.stat().st_mtime
            
            snapshot.repositories[repo_name] = {
                "head": head,
                "size": size,
                "mtime": mtime,
            }
        
        return snapshot
    
    def save_snapshot(self, path: Path, snapshot: SnapshotInfo | None = None) -> Path:
        """Save a snapshot to disk."""
        if snapshot is None:
            snapshot = self.create_snapshot(path)
        
        snapshot_path = path / self.SNAPSHOT_FILE
        snapshot_path.write_text(json.dumps(snapshot.to_dict(), indent=2))
        
        return snapshot_path
    
    def load_snapshot(self, path: Path) -> SnapshotInfo | None:
        """Load a snapshot from disk."""
        snapshot_path = path / self.SNAPSHOT_FILE
        
        if not snapshot_path.exists():
            return None
        
        try:
            data = json.loads(snapshot_path.read_text())
            return SnapshotInfo(
                path=Path(data["path"]),
                created_at=data["created_at"],
                repo_count=data["repo_count"],
                total_size_bytes=data["total_size_bytes"],
                repositories=data.get("repositories", {}),
            )
        except (json.JSONDecodeError, KeyError):
            return None
    
    def compare_directories(
        self,
        old_path: Path,
        new_path: Path,
        include_file_changes: bool = False,
    ) -> BackupDiff:
        """Compare two backup directories."""
        old_repos = self._find_repositories(old_path)
        new_repos = self._find_repositories(new_path)
        
        old_names = {str(r.relative_to(old_path)): r for r in old_repos}
        new_names = {str(r.relative_to(new_path)): r for r in new_repos}
        
        diff = BackupDiff(old_path=old_path, new_path=new_path)
        
        # Find added repositories
        for name in new_names:
            if name not in old_names:
                diff.repos_added.append(name)
        
        # Find removed repositories
        for name in old_names:
            if name not in new_names:
                diff.repos_removed.append(name)
        
        # Find modified repositories
        for name in old_names:
            if name in new_names:
                old_repo = old_names[name]
                new_repo = new_names[name]
                
                repo_diff = self.compare_repositories(
                    old_repo, new_repo, name,
                    include_file_changes=include_file_changes,
                )
                
                if repo_diff.change_type == ChangeType.MODIFIED:
                    diff.repos_modified.append(repo_diff)
                else:
                    diff.repos_unchanged.append(name)
        
        return diff
    
    def compare_with_snapshot(
        self,
        path: Path,
        include_file_changes: bool = False,
    ) -> BackupDiff | None:
        """Compare current state with saved snapshot."""
        old_snapshot = self.load_snapshot(path)
        
        if old_snapshot is None:
            return None
        
        new_snapshot = self.create_snapshot(path)
        
        diff = BackupDiff(old_path=path, new_path=path)
        
        old_repos = set(old_snapshot.repositories.keys())
        new_repos = set(new_snapshot.repositories.keys())
        
        # Find added
        diff.repos_added = list(new_repos - old_repos)
        
        # Find removed
        diff.repos_removed = list(old_repos - new_repos)
        
        # Find modified
        for name in old_repos & new_repos:
            old_info = old_snapshot.repositories[name]
            new_info = new_snapshot.repositories[name]
            
            if old_info["head"] != new_info["head"] or old_info["size"] != new_info["size"]:
                repo_path = path / name
                
                repo_diff = RepositoryDiff(
                    name=name,
                    path=repo_path,
                    change_type=ChangeType.MODIFIED,
                    old_head=old_info["head"],
                    new_head=new_info["head"],
                )
                
                # Get commit diff
                if old_info["head"] and new_info["head"]:
                    repo_diff.commits = self._get_commits_between(
                        repo_path, old_info["head"], new_info["head"]
                    )
                    repo_diff.commit_diff = len(repo_diff.commits)
                
                diff.repos_modified.append(repo_diff)
            else:
                diff.repos_unchanged.append(name)
        
        return diff
    
    def compare_repositories(
        self,
        old_path: Path,
        new_path: Path,
        name: str | None = None,
        include_file_changes: bool = False,
    ) -> RepositoryDiff:
        """Compare two versions of a repository."""
        repo_name = name or new_path.name
        
        old_head = self._get_head_commit(old_path)
        new_head = self._get_head_commit(new_path)
        
        diff = RepositoryDiff(
            name=repo_name,
            path=new_path,
            change_type=ChangeType.UNCHANGED if old_head == new_head else ChangeType.MODIFIED,
            old_head=old_head,
            new_head=new_head,
        )
        
        if old_head != new_head:
            # Get commits between versions
            if old_head and new_head:
                diff.commits = self._get_commits_between(new_path, old_head, new_head)
                diff.commit_diff = len(diff.commits)
        
        if include_file_changes:
            diff.file_changes = self._get_file_changes(old_path, new_path)
        
        return diff
    
    def get_repository_log(
        self,
        repo_path: Path,
        since: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get commit log for a repository."""
        cmd = ["git", "log", f"--max-count={limit}", "--format=%H|%s|%an|%ai"]
        
        if since:
            cmd.append(f"--since={since}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                return []
            
            commits = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|", 3)
                    if len(parts) >= 4:
                        commits.append({
                            "hash": parts[0],
                            "message": parts[1],
                            "author": parts[2],
                            "date": parts[3],
                        })
            
            return commits
        
        except subprocess.TimeoutExpired:
            return []
    
    def generate_diff_report(
        self,
        diff: BackupDiff,
        format: str = "text",
    ) -> str:
        """Generate a diff report."""
        if format == "json":
            return json.dumps(diff.to_dict(), indent=2)
        
        if format == "yaml":
            import yaml
            return yaml.dump(diff.to_dict(), default_flow_style=False)
        
        # Text format
        lines = [
            "=" * 60,
            "FARMORE BACKUP DIFF REPORT",
            "=" * 60,
            "",
            f"📅 Analyzed: {diff.analyzed_at}",
            "",
        ]
        
        if not diff.has_changes:
            lines.append("✅ No changes detected")
            lines.extend(["", "=" * 60])
            return "\n".join(lines)
        
        lines.extend([
            "SUMMARY",
            "-" * 40,
            f"  🆕 Added: {len(diff.repos_added)} repositories",
            f"  ❌ Removed: {len(diff.repos_removed)} repositories",
            f"  ✏️  Modified: {len(diff.repos_modified)} repositories",
            f"  ✅ Unchanged: {len(diff.repos_unchanged)} repositories",
            "",
        ])
        
        if diff.repos_added:
            lines.extend([
                "ADDED REPOSITORIES",
                "-" * 40,
            ])
            for name in diff.repos_added[:20]:
                lines.append(f"  + {name}")
            if len(diff.repos_added) > 20:
                lines.append(f"  ... and {len(diff.repos_added) - 20} more")
            lines.append("")
        
        if diff.repos_removed:
            lines.extend([
                "REMOVED REPOSITORIES",
                "-" * 40,
            ])
            for name in diff.repos_removed[:20]:
                lines.append(f"  - {name}")
            if len(diff.repos_removed) > 20:
                lines.append(f"  ... and {len(diff.repos_removed) - 20} more")
            lines.append("")
        
        if diff.repos_modified:
            lines.extend([
                "MODIFIED REPOSITORIES",
                "-" * 40,
            ])
            for repo in diff.repos_modified[:20]:
                lines.append(f"  ~ {repo.name} ({repo.commit_diff} new commits)")
                if repo.commits:
                    for commit in repo.commits[:3]:
                        msg = commit["message"][:50] + "..." if len(commit["message"]) > 50 else commit["message"]
                        lines.append(f"      • {msg}")
                    if len(repo.commits) > 3:
                        lines.append(f"      ... and {len(repo.commits) - 3} more commits")
            if len(diff.repos_modified) > 20:
                lines.append(f"  ... and {len(diff.repos_modified) - 20} more")
        
        lines.extend(["", "=" * 60])
        
        return "\n".join(lines)
    
    def _find_repositories(self, path: Path) -> list[Path]:
        """Find all git repositories in a directory."""
        repos = []
        
        import os
        for root, dirs, files in os.walk(path):
            root_path = Path(root)
            
            # Skip snapshot files
            if self.SNAPSHOT_FILE in files:
                pass  # Continue but don't stop
            
            # Check for regular git repo
            if ".git" in dirs:
                repos.append(root_path)
                dirs.remove(".git")
                dirs[:] = []
                continue
            
            # Check for bare repo
            if "HEAD" in files and "objects" in dirs and "refs" in dirs:
                repos.append(root_path)
                dirs[:] = []
                continue
        
        return repos
    
    def _get_head_commit(self, repo_path: Path) -> str | None:
        """Get the HEAD commit hash for a repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            pass
        
        return None
    
    def _get_commits_between(
        self,
        repo_path: Path,
        old_commit: str,
        new_commit: str,
    ) -> list[dict]:
        """Get commits between two commit hashes."""
        try:
            result = subprocess.run(
                ["git", "log", f"{old_commit}..{new_commit}", "--format=%H|%s|%an|%ai"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                return []
            
            commits = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|", 3)
                    if len(parts) >= 4:
                        commits.append({
                            "hash": parts[0],
                            "message": parts[1],
                            "author": parts[2],
                            "date": parts[3],
                        })
            
            return commits
        
        except subprocess.TimeoutExpired:
            return []
    
    def _get_file_changes(
        self,
        old_path: Path,
        new_path: Path,
    ) -> list[FileChange]:
        """Get file changes between two versions."""
        changes = []
        
        old_files = self._get_file_hashes(old_path)
        new_files = self._get_file_hashes(new_path)
        
        # Find added files
        for path, (hash_, size) in new_files.items():
            if path not in old_files:
                changes.append(FileChange(
                    path=path,
                    change_type=ChangeType.ADDED,
                    new_hash=hash_,
                    new_size=size,
                ))
        
        # Find removed files
        for path, (hash_, size) in old_files.items():
            if path not in new_files:
                changes.append(FileChange(
                    path=path,
                    change_type=ChangeType.REMOVED,
                    old_hash=hash_,
                    old_size=size,
                ))
        
        # Find modified files
        for path, (old_hash, old_size) in old_files.items():
            if path in new_files:
                new_hash, new_size = new_files[path]
                if old_hash != new_hash:
                    changes.append(FileChange(
                        path=path,
                        change_type=ChangeType.MODIFIED,
                        old_hash=old_hash,
                        new_hash=new_hash,
                        old_size=old_size,
                        new_size=new_size,
                    ))
        
        return changes
    
    def _get_file_hashes(self, path: Path) -> dict[str, tuple[str, int]]:
        """Get file hashes for all files in a directory."""
        files = {}
        
        for entry in path.rglob("*"):
            if entry.is_file() and ".git" not in entry.parts:
                rel_path = str(entry.relative_to(path))
                try:
                    size = entry.stat().st_size
                    # Only hash small files for performance
                    if size < 10 * 1024 * 1024:  # 10MB
                        hash_ = hashlib.md5(entry.read_bytes()).hexdigest()
                    else:
                        hash_ = f"size:{size}"
                    files[rel_path] = (hash_, size)
                except OSError:
                    pass
        
        return files
    
    def _get_directory_size(self, path: Path) -> int:
        """Calculate total size of a directory."""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total
