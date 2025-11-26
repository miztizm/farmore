"""
Farmore Analytics Module - Backup statistics, reporting, and insights.

"Data tells a story. Make sure you're listening." — schema.cx
"""

import json
import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RepositoryStats:
    """Statistics for a single repository."""
    
    name: str
    path: Path
    size_bytes: int = 0
    file_count: int = 0
    commit_count: int = 0
    branch_count: int = 0
    tag_count: int = 0
    last_commit_date: str | None = None
    last_backup_date: str | None = None
    is_bare: bool = False
    has_lfs: bool = False
    languages: dict[str, int] = field(default_factory=dict)
    
    @property
    def size_mb(self) -> float:
        """Size in megabytes."""
        return self.size_bytes / (1024 * 1024)
    
    @property
    def size_gb(self) -> float:
        """Size in gigabytes."""
        return self.size_bytes / (1024 * 1024 * 1024)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "size_mb": round(self.size_mb, 2),
            "file_count": self.file_count,
            "commit_count": self.commit_count,
            "branch_count": self.branch_count,
            "tag_count": self.tag_count,
            "last_commit_date": self.last_commit_date,
            "last_backup_date": self.last_backup_date,
            "is_bare": self.is_bare,
            "has_lfs": self.has_lfs,
            "languages": self.languages,
        }


@dataclass
class BackupStats:
    """Aggregate statistics for a backup directory."""
    
    path: Path
    total_repositories: int = 0
    total_size_bytes: int = 0
    total_files: int = 0
    total_commits: int = 0
    repositories: list[RepositoryStats] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    languages: dict[str, int] = field(default_factory=dict)
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def total_size_mb(self) -> float:
        """Total size in megabytes."""
        return self.total_size_bytes / (1024 * 1024)
    
    @property
    def total_size_gb(self) -> float:
        """Total size in gigabytes."""
        return self.total_size_bytes / (1024 * 1024 * 1024)
    
    @property
    def avg_repo_size_mb(self) -> float:
        """Average repository size in MB."""
        if self.total_repositories == 0:
            return 0
        return self.total_size_mb / self.total_repositories
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "path": str(self.path),
            "total_repositories": self.total_repositories,
            "total_size_bytes": self.total_size_bytes,
            "total_size_mb": round(self.total_size_mb, 2),
            "total_size_gb": round(self.total_size_gb, 3),
            "total_files": self.total_files,
            "total_commits": self.total_commits,
            "avg_repo_size_mb": round(self.avg_repo_size_mb, 2),
            "categories": self.categories,
            "languages": self.languages,
            "analyzed_at": self.analyzed_at,
            "repositories": [r.to_dict() for r in self.repositories],
        }


@dataclass
class BackupHistory:
    """Historical record of backups."""
    
    backup_id: str
    started_at: str
    completed_at: str | None = None
    duration_seconds: float = 0
    repos_cloned: int = 0
    repos_updated: int = 0
    repos_failed: int = 0
    total_size_bytes: int = 0
    success: bool = True
    error_message: str | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "backup_id": self.backup_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "repos_cloned": self.repos_cloned,
            "repos_updated": self.repos_updated,
            "repos_failed": self.repos_failed,
            "total_size_bytes": self.total_size_bytes,
            "success": self.success,
            "error_message": self.error_message,
        }


class BackupAnalytics:
    """
    Analyze backup directories and generate statistics.
    
    "Understanding your backups is the first step to protecting them." — schema.cx
    """
    
    HISTORY_FILE = ".farmore_history.json"
    
    def __init__(self, backup_dir: Path | None = None):
        """Initialize the analytics engine."""
        self.backup_dir = backup_dir or Path("backups")
        self._history: list[BackupHistory] = []
        self._load_history()
    
    def _load_history(self) -> None:
        """Load backup history from disk."""
        history_path = self.backup_dir / self.HISTORY_FILE
        if history_path.exists():
            try:
                data = json.loads(history_path.read_text())
                self._history = [
                    BackupHistory(**h) for h in data.get("history", [])
                ]
            except (json.JSONDecodeError, TypeError):
                self._history = []
    
    def _save_history(self) -> None:
        """Save backup history to disk."""
        history_path = self.backup_dir / self.HISTORY_FILE
        history_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "history": [h.to_dict() for h in self._history],
        }
        history_path.write_text(json.dumps(data, indent=2))
    
    def record_backup(
        self,
        repos_cloned: int,
        repos_updated: int,
        repos_failed: int,
        duration_seconds: float,
        total_size_bytes: int = 0,
        error_message: str | None = None,
    ) -> BackupHistory:
        """Record a backup operation in history."""
        import uuid
        
        now = datetime.now()
        history = BackupHistory(
            backup_id=str(uuid.uuid4())[:8],
            started_at=now.isoformat(),
            completed_at=now.isoformat(),
            duration_seconds=duration_seconds,
            repos_cloned=repos_cloned,
            repos_updated=repos_updated,
            repos_failed=repos_failed,
            total_size_bytes=total_size_bytes,
            success=repos_failed == 0,
            error_message=error_message,
        )
        
        self._history.append(history)
        
        # Keep last 100 entries
        if len(self._history) > 100:
            self._history = self._history[-100:]
        
        self._save_history()
        return history
    
    def get_history(self, limit: int = 20) -> list[BackupHistory]:
        """Get recent backup history."""
        return self._history[-limit:]
    
    def analyze_repository(self, repo_path: Path) -> RepositoryStats:
        """Analyze a single repository and return statistics."""
        stats = RepositoryStats(
            name=repo_path.name,
            path=repo_path,
        )
        
        # Check if it's a bare repository
        if (repo_path / "HEAD").exists() and not (repo_path / ".git").exists():
            stats.is_bare = True
            git_dir = repo_path
        elif (repo_path / ".git").exists():
            git_dir = repo_path / ".git"
        else:
            # Not a git repository
            return stats
        
        # Calculate size
        stats.size_bytes = self._get_directory_size(repo_path)
        
        # Count files (for non-bare repos)
        if not stats.is_bare:
            stats.file_count = self._count_files(repo_path)
        
        # Get git statistics
        try:
            # Commit count
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                stats.commit_count = int(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError):
            pass
        
        try:
            # Branch count
            result = subprocess.run(
                ["git", "branch", "-a"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                stats.branch_count = len([
                    b for b in result.stdout.strip().split("\n") 
                    if b.strip() and not b.strip().startswith("->")
                ])
        except subprocess.TimeoutExpired:
            pass
        
        try:
            # Tag count
            result = subprocess.run(
                ["git", "tag"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                stats.tag_count = len([t for t in result.stdout.strip().split("\n") if t.strip()])
        except subprocess.TimeoutExpired:
            pass
        
        try:
            # Last commit date
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ci"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                stats.last_commit_date = result.stdout.strip()
        except subprocess.TimeoutExpired:
            pass
        
        # Check for LFS
        lfs_config = repo_path / ".lfsconfig" if not stats.is_bare else git_dir / "lfs"
        if lfs_config.exists() or (repo_path / ".gitattributes").exists():
            gitattributes = repo_path / ".gitattributes"
            if gitattributes.exists():
                content = gitattributes.read_text()
                stats.has_lfs = "filter=lfs" in content
        
        # Get language statistics (for non-bare repos)
        if not stats.is_bare:
            stats.languages = self._analyze_languages(repo_path)
        
        # Last backup date (file modification time)
        try:
            mtime = repo_path.stat().st_mtime
            stats.last_backup_date = datetime.fromtimestamp(mtime).isoformat()
        except OSError:
            pass
        
        return stats
    
    def analyze_directory(self, path: Path | None = None) -> BackupStats:
        """Analyze an entire backup directory."""
        path = path or self.backup_dir
        
        stats = BackupStats(path=path)
        
        # Find all git repositories
        repos = self._find_repositories(path)
        
        for repo_path in repos:
            repo_stats = self.analyze_repository(repo_path)
            stats.repositories.append(repo_stats)
            stats.total_size_bytes += repo_stats.size_bytes
            stats.total_files += repo_stats.file_count
            stats.total_commits += repo_stats.commit_count
            
            # Aggregate languages
            for lang, count in repo_stats.languages.items():
                stats.languages[lang] = stats.languages.get(lang, 0) + count
        
        stats.total_repositories = len(repos)
        
        # Categorize repositories
        stats.categories = self._categorize_repositories(repos)
        
        return stats
    
    def _find_repositories(self, path: Path) -> list[Path]:
        """Find all git repositories in a directory."""
        repos = []
        
        for root, dirs, files in os.walk(path):
            root_path = Path(root)
            
            # Check for regular git repo
            if ".git" in dirs:
                repos.append(root_path)
                dirs.remove(".git")  # Don't recurse into .git
                dirs[:] = []  # Don't recurse into subdirectories of a repo
                continue
            
            # Check for bare repo
            if "HEAD" in files and "objects" in dirs and "refs" in dirs:
                repos.append(root_path)
                dirs[:] = []  # Don't recurse into subdirectories
                continue
        
        return repos
    
    def _get_directory_size(self, path: Path) -> int:
        """Calculate total size of a directory in bytes."""
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
    
    def _count_files(self, path: Path) -> int:
        """Count non-hidden files in a directory."""
        count = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file() and not any(p.startswith(".") for p in entry.parts):
                    count += 1
        except OSError:
            pass
        return count
    
    def _analyze_languages(self, path: Path) -> dict[str, int]:
        """Analyze language distribution in a repository."""
        extensions = defaultdict(int)
        
        language_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React JSX",
            ".tsx": "React TSX",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C/C++ Header",
            ".cs": "C#",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".scala": "Scala",
            ".r": "R",
            ".sql": "SQL",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".sass": "Sass",
            ".less": "Less",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".xml": "XML",
            ".md": "Markdown",
            ".sh": "Shell",
            ".bash": "Bash",
            ".zsh": "Zsh",
            ".ps1": "PowerShell",
            ".dockerfile": "Dockerfile",
        }
        
        try:
            for entry in path.rglob("*"):
                if entry.is_file() and not any(p.startswith(".") for p in entry.parts):
                    ext = entry.suffix.lower()
                    if ext in language_map:
                        extensions[language_map[ext]] += 1
        except OSError:
            pass
        
        return dict(extensions)
    
    def _categorize_repositories(self, repos: list[Path]) -> dict[str, int]:
        """Categorize repositories by directory structure."""
        categories: dict[str, int] = defaultdict(int)
        
        for repo_path in repos:
            # Look for category indicators in path
            parts = repo_path.parts
            
            if "private" in parts:
                categories["private"] += 1
            elif "public" in parts:
                categories["public"] += 1
            elif "starred" in parts:
                categories["starred"] += 1
            elif "watched" in parts:
                categories["watched"] += 1
            elif "forks" in parts:
                categories["forks"] += 1
            elif "organizations" in parts:
                categories["organizations"] += 1
            elif "gists" in parts:
                categories["gists"] += 1
            else:
                categories["other"] += 1
        
        return dict(categories)
    
    def generate_report(
        self,
        path: Path | None = None,
        format: str = "text",
    ) -> str:
        """Generate a backup report."""
        stats = self.analyze_directory(path)
        
        if format == "json":
            return json.dumps(stats.to_dict(), indent=2)
        
        if format == "yaml":
            import yaml
            return yaml.dump(stats.to_dict(), default_flow_style=False)
        
        # Text format
        lines = [
            "=" * 60,
            "FARMORE BACKUP REPORT",
            "=" * 60,
            "",
            f"📁 Backup Directory: {stats.path}",
            f"📊 Analyzed: {stats.analyzed_at}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Repositories: {stats.total_repositories}",
            f"Total Size: {stats.total_size_mb:.2f} MB ({stats.total_size_gb:.3f} GB)",
            f"Total Files: {stats.total_files:,}",
            f"Total Commits: {stats.total_commits:,}",
            f"Average Repo Size: {stats.avg_repo_size_mb:.2f} MB",
            "",
        ]
        
        if stats.categories:
            lines.extend([
                "CATEGORIES",
                "-" * 40,
            ])
            for category, count in sorted(stats.categories.items(), key=lambda x: -x[1]):
                lines.append(f"  {category}: {count}")
            lines.append("")
        
        if stats.languages:
            lines.extend([
                "LANGUAGES (Top 10)",
                "-" * 40,
            ])
            top_languages = sorted(stats.languages.items(), key=lambda x: -x[1])[:10]
            for lang, count in top_languages:
                lines.append(f"  {lang}: {count} files")
            lines.append("")
        
        if stats.repositories:
            lines.extend([
                "TOP 10 LARGEST REPOSITORIES",
                "-" * 40,
            ])
            top_repos = sorted(stats.repositories, key=lambda x: -x.size_bytes)[:10]
            for repo in top_repos:
                lines.append(f"  {repo.name}: {repo.size_mb:.2f} MB")
        
        lines.extend(["", "=" * 60])
        
        return "\n".join(lines)
    
    def get_growth_stats(self) -> dict[str, Any]:
        """Get backup growth statistics from history."""
        if len(self._history) < 2:
            return {
                "has_data": False,
                "message": "Not enough history for growth analysis",
            }
        
        first = self._history[0]
        last = self._history[-1]
        
        total_repos = sum(h.repos_cloned + h.repos_updated for h in self._history)
        total_failures = sum(h.repos_failed for h in self._history)
        total_duration = sum(h.duration_seconds for h in self._history)
        
        return {
            "has_data": True,
            "backup_count": len(self._history),
            "first_backup": first.started_at,
            "last_backup": last.started_at,
            "total_repos_processed": total_repos,
            "total_failures": total_failures,
            "success_rate": ((total_repos - total_failures) / total_repos * 100) if total_repos > 0 else 100,
            "avg_duration_seconds": total_duration / len(self._history),
            "total_duration_hours": total_duration / 3600,
        }
