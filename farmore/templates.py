"""
Farmore Templates Module - Pre-built backup templates for common scenarios.

"Templates are just best practices with a nice UI." — schema.cx
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class BackupTemplate:
    """A pre-built backup configuration template."""
    
    id: str
    name: str
    description: str
    category: str
    
    # Target configuration
    target_type: str = "user"  # user, org, starred
    
    # Visibility and filtering
    visibility: str = "all"  # all, public, private
    include_forks: bool = False
    include_archived: bool = False
    exclude_repos: list[str] = field(default_factory=list)
    name_regex: str | None = None
    
    # Data to include
    include_issues: bool = False
    include_pulls: bool = False
    include_releases: bool = False
    include_wikis: bool = False
    include_workflows: bool = False
    include_labels: bool = False
    include_milestones: bool = False
    include_discussions: bool = False
    
    # Git options
    bare: bool = False
    lfs: bool = False
    skip_existing: bool = False
    
    # Performance
    parallel_workers: int = 4
    
    # Scheduling (optional)
    schedule_interval: str | None = None  # daily, weekly, hourly
    schedule_time: str | None = None  # HH:MM
    
    # Notifications (optional)
    notify_on_success: bool = False
    notify_on_failure: bool = True
    
    # Metadata
    author: str = "farmore"
    version: str = "1.0"
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "target_type": self.target_type,
            "visibility": self.visibility,
            "include_forks": self.include_forks,
            "include_archived": self.include_archived,
            "exclude_repos": self.exclude_repos,
            "name_regex": self.name_regex,
            "include_issues": self.include_issues,
            "include_pulls": self.include_pulls,
            "include_releases": self.include_releases,
            "include_wikis": self.include_wikis,
            "include_workflows": self.include_workflows,
            "include_labels": self.include_labels,
            "include_milestones": self.include_milestones,
            "include_discussions": self.include_discussions,
            "bare": self.bare,
            "lfs": self.lfs,
            "skip_existing": self.skip_existing,
            "parallel_workers": self.parallel_workers,
            "schedule_interval": self.schedule_interval,
            "schedule_time": self.schedule_time,
            "notify_on_success": self.notify_on_success,
            "notify_on_failure": self.notify_on_failure,
            "author": self.author,
            "version": self.version,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "BackupTemplate":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=data.get("category", "custom"),
            target_type=data.get("target_type", "user"),
            visibility=data.get("visibility", "all"),
            include_forks=data.get("include_forks", False),
            include_archived=data.get("include_archived", False),
            exclude_repos=data.get("exclude_repos", []),
            name_regex=data.get("name_regex"),
            include_issues=data.get("include_issues", False),
            include_pulls=data.get("include_pulls", False),
            include_releases=data.get("include_releases", False),
            include_wikis=data.get("include_wikis", False),
            include_workflows=data.get("include_workflows", False),
            include_labels=data.get("include_labels", False),
            include_milestones=data.get("include_milestones", False),
            include_discussions=data.get("include_discussions", False),
            bare=data.get("bare", False),
            lfs=data.get("lfs", False),
            skip_existing=data.get("skip_existing", False),
            parallel_workers=data.get("parallel_workers", 4),
            schedule_interval=data.get("schedule_interval"),
            schedule_time=data.get("schedule_time"),
            notify_on_success=data.get("notify_on_success", False),
            notify_on_failure=data.get("notify_on_failure", True),
            author=data.get("author", "farmore"),
            version=data.get("version", "1.0"),
            tags=data.get("tags", []),
        )


# ============================================================================
# Built-in Templates
# ============================================================================

BUILTIN_TEMPLATES: list[BackupTemplate] = [
    # User Templates
    BackupTemplate(
        id="user-essential",
        name="User Essential",
        description="Quick backup of user's own public and private repositories (no forks/archived)",
        category="user",
        target_type="user",
        visibility="all",
        include_forks=False,
        include_archived=False,
        skip_existing=True,
        parallel_workers=4,
        tags=["quick", "essential", "user"],
    ),
    BackupTemplate(
        id="user-complete",
        name="User Complete",
        description="Complete backup including all data exports (issues, PRs, releases, wikis)",
        category="user",
        target_type="user",
        visibility="all",
        include_forks=False,
        include_archived=True,
        include_issues=True,
        include_pulls=True,
        include_releases=True,
        include_wikis=True,
        include_workflows=True,
        lfs=True,
        parallel_workers=8,
        tags=["complete", "full", "user"],
    ),
    BackupTemplate(
        id="user-mirror",
        name="User Mirror",
        description="Bare/mirror clones for true 1:1 backup of all refs, branches, and tags",
        category="user",
        target_type="user",
        visibility="all",
        include_forks=False,
        include_archived=False,
        bare=True,
        lfs=True,
        parallel_workers=4,
        tags=["mirror", "bare", "user"],
    ),
    
    # Organization Templates
    BackupTemplate(
        id="org-essential",
        name="Organization Essential",
        description="Quick backup of organization's main repositories",
        category="org",
        target_type="org",
        visibility="all",
        include_forks=False,
        include_archived=False,
        skip_existing=True,
        parallel_workers=8,
        tags=["quick", "essential", "org"],
    ),
    BackupTemplate(
        id="org-complete",
        name="Organization Complete",
        description="Complete organization backup with all metadata and data exports",
        category="org",
        target_type="org",
        visibility="all",
        include_forks=False,
        include_archived=True,
        include_issues=True,
        include_pulls=True,
        include_releases=True,
        include_wikis=True,
        include_workflows=True,
        include_labels=True,
        include_milestones=True,
        lfs=True,
        parallel_workers=12,
        schedule_interval="daily",
        schedule_time="02:00",
        notify_on_failure=True,
        tags=["complete", "full", "org", "enterprise"],
    ),
    BackupTemplate(
        id="org-compliance",
        name="Organization Compliance",
        description="Compliance-focused backup with all audit-relevant data",
        category="org",
        target_type="org",
        visibility="all",
        include_forks=True,
        include_archived=True,
        include_issues=True,
        include_pulls=True,
        include_releases=True,
        include_wikis=True,
        include_workflows=True,
        include_labels=True,
        include_milestones=True,
        include_discussions=True,
        bare=True,
        lfs=True,
        parallel_workers=8,
        schedule_interval="daily",
        schedule_time="03:00",
        notify_on_success=True,
        notify_on_failure=True,
        tags=["compliance", "audit", "org", "enterprise"],
    ),
    
    # Special Purpose Templates
    BackupTemplate(
        id="starred-collection",
        name="Starred Collection",
        description="Backup all repositories you've starred",
        category="special",
        target_type="starred",
        visibility="all",
        include_forks=True,
        include_archived=True,
        skip_existing=True,
        parallel_workers=4,
        tags=["starred", "collection", "discovery"],
    ),
    BackupTemplate(
        id="security-audit",
        name="Security Audit",
        description="Security-focused backup including workflows, releases, and PRs for audit",
        category="special",
        target_type="user",
        visibility="all",
        include_forks=False,
        include_archived=False,
        include_pulls=True,
        include_releases=True,
        include_workflows=True,
        parallel_workers=4,
        tags=["security", "audit"],
    ),
    BackupTemplate(
        id="documentation-only",
        name="Documentation Only",
        description="Backup wikis and documentation repos only",
        category="special",
        target_type="user",
        visibility="all",
        include_forks=False,
        include_archived=False,
        include_wikis=True,
        name_regex="^(docs?|wiki|documentation|readme).*",
        parallel_workers=2,
        tags=["documentation", "wiki", "minimal"],
    ),
    BackupTemplate(
        id="disaster-recovery",
        name="Disaster Recovery",
        description="Full mirror backup for disaster recovery scenarios",
        category="special",
        target_type="user",
        visibility="all",
        include_forks=True,
        include_archived=True,
        include_issues=True,
        include_pulls=True,
        include_releases=True,
        include_wikis=True,
        include_workflows=True,
        include_labels=True,
        include_milestones=True,
        bare=True,
        lfs=True,
        parallel_workers=4,
        schedule_interval="daily",
        schedule_time="04:00",
        notify_on_success=True,
        notify_on_failure=True,
        tags=["disaster-recovery", "full", "mirror"],
    ),
    
    # Incremental Templates
    BackupTemplate(
        id="incremental-daily",
        name="Incremental Daily",
        description="Daily incremental backup - only update changed repositories",
        category="incremental",
        target_type="user",
        visibility="all",
        include_forks=False,
        include_archived=False,
        skip_existing=False,
        parallel_workers=4,
        schedule_interval="daily",
        schedule_time="01:00",
        tags=["incremental", "daily", "scheduled"],
    ),
    BackupTemplate(
        id="incremental-hourly",
        name="Incremental Hourly",
        description="Hourly incremental backup for critical repositories",
        category="incremental",
        target_type="user",
        visibility="all",
        include_forks=False,
        include_archived=False,
        skip_existing=False,
        parallel_workers=8,
        schedule_interval="hourly",
        tags=["incremental", "hourly", "scheduled", "critical"],
    ),
]


class TemplateManager:
    """
    Manages backup templates.
    
    "Good templates save time. Great templates save careers." — schema.cx
    """
    
    CUSTOM_TEMPLATES_FILE = "templates.json"
    
    def __init__(self, config_dir: Path | None = None):
        """Initialize template manager."""
        self.config_dir = config_dir or Path.home() / ".config" / "farmore"
        self._custom_templates: list[BackupTemplate] = []
        self._load_custom_templates()
    
    def _load_custom_templates(self) -> None:
        """Load custom templates from disk."""
        templates_path = self.config_dir / self.CUSTOM_TEMPLATES_FILE
        
        if templates_path.exists():
            try:
                data = json.loads(templates_path.read_text())
                self._custom_templates = [
                    BackupTemplate.from_dict(t) for t in data.get("templates", [])
                ]
            except (json.JSONDecodeError, KeyError):
                self._custom_templates = []
    
    def _save_custom_templates(self) -> None:
        """Save custom templates to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        templates_path = self.config_dir / self.CUSTOM_TEMPLATES_FILE
        
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "templates": [t.to_dict() for t in self._custom_templates],
        }
        
        templates_path.write_text(json.dumps(data, indent=2))
    
    def list_all(self) -> list[BackupTemplate]:
        """List all templates (built-in and custom)."""
        return BUILTIN_TEMPLATES + self._custom_templates
    
    def list_builtin(self) -> list[BackupTemplate]:
        """List built-in templates only."""
        return BUILTIN_TEMPLATES.copy()
    
    def list_custom(self) -> list[BackupTemplate]:
        """List custom templates only."""
        return self._custom_templates.copy()
    
    def get(self, template_id: str) -> BackupTemplate | None:
        """Get a template by ID."""
        for template in self.list_all():
            if template.id == template_id:
                return template
        return None
    
    def get_by_category(self, category: str) -> list[BackupTemplate]:
        """Get templates by category."""
        return [t for t in self.list_all() if t.category == category]
    
    def get_by_tag(self, tag: str) -> list[BackupTemplate]:
        """Get templates by tag."""
        return [t for t in self.list_all() if tag in t.tags]
    
    def search(self, query: str) -> list[BackupTemplate]:
        """Search templates by name, description, or tags."""
        query = query.lower()
        results = []
        
        for template in self.list_all():
            if (
                query in template.name.lower() or
                query in template.description.lower() or
                any(query in tag.lower() for tag in template.tags)
            ):
                results.append(template)
        
        return results
    
    def add_custom(self, template: BackupTemplate) -> None:
        """Add a custom template."""
        # Check for duplicate ID
        existing = [t for t in self._custom_templates if t.id == template.id]
        if existing:
            # Update existing
            self._custom_templates = [
                t for t in self._custom_templates if t.id != template.id
            ]
        
        template.author = "custom"
        self._custom_templates.append(template)
        self._save_custom_templates()
    
    def remove_custom(self, template_id: str) -> bool:
        """Remove a custom template."""
        original_count = len(self._custom_templates)
        self._custom_templates = [
            t for t in self._custom_templates if t.id != template_id
        ]
        
        if len(self._custom_templates) < original_count:
            self._save_custom_templates()
            return True
        
        return False
    
    def export_template(self, template_id: str, output_path: Path) -> bool:
        """Export a template to a file."""
        template = self.get(template_id)
        
        if template is None:
            return False
        
        output_path.write_text(json.dumps(template.to_dict(), indent=2))
        return True
    
    def import_template(self, input_path: Path, new_id: str | None = None) -> BackupTemplate | None:
        """Import a template from a file."""
        try:
            data = json.loads(input_path.read_text())
            template = BackupTemplate.from_dict(data)
            
            if new_id:
                template.id = new_id
            
            self.add_custom(template)
            return template
        
        except (json.JSONDecodeError, KeyError):
            return None
    
    def create_from_profile(
        self,
        profile_name: str,
        template_id: str,
        template_name: str,
        description: str = "",
    ) -> BackupTemplate | None:
        """Create a template from an existing backup profile."""
        from .config import ConfigManager
        
        config_manager = ConfigManager(config_dir=self.config_dir)
        profile = config_manager.load_profile(profile_name)
        
        if profile is None:
            return None
        
        template = BackupTemplate(
            id=template_id,
            name=template_name,
            description=description or f"Template created from profile: {profile_name}",
            category="custom",
            target_type=profile.target_type,
            visibility=profile.visibility,
            include_forks=profile.include_forks,
            include_archived=profile.include_archived,
            exclude_repos=profile.exclude_repos or [],
            name_regex=profile.name_regex,
            include_issues=profile.include_issues,
            include_pulls=profile.include_pulls,
            include_releases=profile.include_releases,
            include_wikis=profile.include_wikis,
            include_workflows=profile.include_workflows,
            bare=profile.bare,
            lfs=profile.lfs,
            skip_existing=profile.skip_existing,
            parallel_workers=profile.parallel_workers,
        )
        
        self.add_custom(template)
        return template
    
    def apply_template(
        self,
        template_id: str,
        target_name: str,
        dest: Path | None = None,
    ) -> dict[str, Any] | None:
        """Apply a template to create CLI arguments."""
        template = self.get(template_id)
        
        if template is None:
            return None
        
        # Build CLI arguments dictionary
        args: dict[str, Any] = {
            "target_type": template.target_type,
            "target_name": target_name,
            "visibility": template.visibility,
            "include_forks": template.include_forks,
            "include_archived": template.include_archived,
            "exclude_repos": template.exclude_repos,
            "name_regex": template.name_regex,
            "include_issues": template.include_issues,
            "include_pulls": template.include_pulls,
            "include_releases": template.include_releases,
            "include_wikis": template.include_wikis,
            "include_workflows": template.include_workflows,
            "bare": template.bare,
            "lfs": template.lfs,
            "skip_existing": template.skip_existing,
            "parallel_workers": template.parallel_workers,
        }
        
        if dest:
            args["dest"] = dest
        
        return args
    
    def get_categories(self) -> list[str]:
        """Get all unique categories."""
        categories = set()
        for template in self.list_all():
            categories.add(template.category)
        return sorted(categories)
    
    def get_tags(self) -> list[str]:
        """Get all unique tags."""
        tags = set()
        for template in self.list_all():
            tags.update(template.tags)
        return sorted(tags)
