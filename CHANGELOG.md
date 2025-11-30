# Changelog

All notable changes to Farmore will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2025-11-30

### Added
- **Repository Transfer Feature** - Transfer repositories to organizations via GitHub API
  - `transfer` command - Transfer one or multiple repositories to a target organization
  - Pre-transfer validation checks:
    - Admin access verification on source repository
    - Target organization existence check
    - Organization membership verification
    - Repository name availability check
  - `--dry-run` flag - Validate without executing transfer
  - `--new-name` option - Rename repository during transfer
  - `--team-ids` option - Grant team access after transfer
  - Multiple repository support via comma-separated list or @file.txt
  - Rich formatted output with progress indicators
  - Comprehensive error handling for 401/403/404/422 responses
  - Rate limit handling
  - Example: `farmore transfer my-repo --org my-org --dry-run`

- **New modules**:
  - `farmore/transfer.py` - Repository transfer functionality
    - `TransferClient` class for GitHub API integration
    - `TransferResult` and `TransferSummary` dataclasses
    - `validate_repo_name()` and `validate_org_name()` functions
    - `parse_repo_list()` and `parse_team_ids()` helper functions

- **New tests**:
  - `tests/test_transfer.py` - 46 comprehensive unit tests
    - Validation function tests
    - TransferClient method tests with mocked API responses
    - Error handling tests for various HTTP status codes
    - Dry-run mode tests

### Changed
- **User-Agent header** - Updated to `Farmore/0.10.0`

## [0.9.0] - 2025-11-26

### Added
- **Deployment Script** - Automated version bump, build, and release workflow
  - `scripts/deploy.py` - Full deployment automation
  - Version bump: major, minor, or patch
  - Automatic version sync across all files
  - Git commit, tag, and push automation
  - Dry-run mode for previewing changes
  - Example: `python scripts/deploy.py minor`

### Changed
- **README.md** - Refactored for clarity and professionalism
  - Reduced from 466 lines to 107 lines (77% reduction)
  - Removed excessive emoji usage
  - Added table of contents
  - Consolidated commands into scannable tables
  - Moved detailed docs to `docs/` folder
- **License format** - Updated to SPDX expression format
- **User-Agent header** - Updated to `Farmore/0.9.0`

## [0.8.0] - 2025-11-26

### Added
- **Analytics Module** - Backup statistics, reporting, and insights
  - `analytics` command - View backup statistics and generate reports
  - `analytics-history` command - View backup operation history
  - Repository statistics: size, commits, branches, tags, languages
  - Growth tracking and trend analysis
  - Report generation in text, JSON, or YAML format
  - Example: `farmore analytics ./backups --format json --output report.json`

- **Diff/Compare Module** - Compare backups and detect changes
  - `diff` command - Compare two backup directories
  - `snapshot` command - Create/save backup snapshots
  - Detect added, removed, and modified repositories
  - Track file-level changes with hash comparison
  - Commit diff tracking between backup versions
  - Example: `farmore diff ./backups/v1 ./backups/v2 --include-files`

- **Notifications Module** - Multi-channel backup notifications
  - `notify-config` command - Configure notifications
  - `notify-test` command - Test notification channels
  - Email notifications via SMTP
  - Slack notifications via webhook
  - Discord notifications via webhook
  - Generic webhook support for custom integrations
  - Event filtering: success, failure, warning
  - Example: `farmore notify-config --slack-webhook https://hooks.slack.com/...`

- **Templates Module** - Pre-built backup templates
  - `templates` command - List available templates
  - `template-apply` command - Apply a template
  - `template-create` command - Create custom template
  - `template-export` command - Export template to file
  - `template-import` command - Import template from file
  - Built-in templates:
    - `user-essential` - Quick backup of user repos
    - `user-complete` - Full backup with all data exports
    - `user-mirror` - Bare/mirror clones for true 1:1 backup
    - `org-essential` - Quick organization backup
    - `org-complete` - Full org backup with metadata
    - `org-compliance` - Compliance-focused audit backup
    - `starred-collection` - Backup starred repositories
    - `security-audit` - Security-focused backup
    - `disaster-recovery` - Full mirror for DR scenarios
    - `incremental-daily` - Daily incremental backup
    - `incremental-hourly` - Hourly incremental for critical repos
  - Example: `farmore template-apply org-complete --target my-org`

- **New modules**:
  - `farmore/analytics.py` - Backup analytics and reporting
    - `BackupAnalytics` class with full analysis capabilities
    - `RepositoryStats`, `BackupStats`, `BackupHistory` dataclasses
    - Language detection across repositories
    - Category analysis (private, public, starred, forks)
  - `farmore/diff.py` - Backup comparison engine
    - `BackupCompare` class for directory comparison
    - `BackupDiff`, `RepositoryDiff`, `FileChange` dataclasses
    - Snapshot creation and comparison
    - Git-level commit tracking
  - `farmore/notifications.py` - Notification system
    - `NotificationManager` class for multi-channel notifications
    - `EmailNotifier`, `SlackNotifier`, `DiscordNotifier`, `WebhookNotifier`
    - `NotificationConfig` and `NotificationEvent` dataclasses
    - HTML and plain text email formatting
  - `farmore/templates.py` - Template management
    - `TemplateManager` class for template CRUD
    - `BackupTemplate` dataclass with 20+ configuration options
    - 11 built-in templates for common scenarios
    - Custom template creation and sharing

### Changed
- **Test coverage** - Now 253 tests (up from 152)
- **User-Agent header** - Updated to `Farmore/0.8.0`
- **Keywords** - Added "analytics", "notifications" to package metadata

### Notes
- Analytics history is stored in `.farmore_history.json` within backup directory
- Snapshots are stored in `.farmore_snapshot.json` for change tracking
- Notification config stored in `~/.config/farmore/.farmore_notifications.json`
- Templates stored in `~/.config/farmore/templates.json`

## [0.7.0] - 2025-11-26

### Added
- **Configuration Profile Management** - Save and reuse backup configurations
  - `config-save` - Save a backup profile with all options
  - `config-load` - View a saved profile
  - `config-list` - List all saved profiles
  - `config-delete` - Delete a saved profile
  - `config-export` - Export profile to YAML file for sharing
  - `config-import` - Import profile from YAML file
  - Profiles stored in `~/.config/farmore/profiles.yaml`
  - Example: `farmore config-save daily-backup --type user --name miztizm --include-issues`

- **Backup Verification** - Verify integrity of backups
  - `verify` command - Check backup integrity
  - `--deep` flag - Run `git fsck` for thorough verification
  - `--checksums` flag - Verify file checksums
  - Detects corrupted repositories and missing files
  - Example: `farmore verify ./backups/miztizm --deep`

- **Backup Scheduling** - Automated backup scheduling
  - `schedule-add` - Add a scheduled backup
  - `schedule-list` - List all schedules
  - `schedule-remove` - Remove a schedule
  - `schedule-run` - Run scheduler daemon
  - Supports intervals: hourly, daily, weekly, "every X hours"
  - Example: `farmore schedule-add daily-backup --profile my-backup --interval daily --at 02:00`

- **Restore Functionality** - Restore backups to GitHub
  - `restore-issues` - Restore issues from backup
  - `restore-releases` - Restore releases from backup
  - `restore-labels` - Restore labels from backup
  - `restore-milestones` - Restore milestones from backup
  - `--dry-run` flag - Preview without creating items
  - `--skip-existing` flag - Skip items that already exist
  - Example: `farmore restore-issues ./backup/issues.json --to owner/repo`

- **New modules**:
  - `farmore/config.py` - Configuration profile management
    - `BackupProfile` dataclass
    - `ConfigManager` class for CRUD operations
  - `farmore/verify.py` - Backup verification
    - `BackupVerifier` class
    - `VerificationResult` dataclass
    - Deep git fsck verification
    - Checksum verification
  - `farmore/scheduler.py` - Backup scheduling
    - `BackupScheduler` class
    - `ScheduledBackup` dataclass
    - Integration with `schedule` library
  - `farmore/restore.py` - Restore functionality
    - `RestoreManager` class
    - Support for issues, releases, labels, milestones

### Changed
- **Dependencies** - Added `schedule>=1.2.0` for scheduling support
- **User-Agent header** - Updated to `Farmore/0.7.0`
- **Keywords** - Added "restore", "scheduler" to package metadata

### Notes
- Scheduler requires the `schedule` library (included in dependencies)
- Restore operations require GitHub token with write access
- Profiles are stored locally and can be exported for team sharing

## [0.6.0] - 2025-11-26

### Added
- **`labels` command** - Export all labels from a repository
  - Export to JSON or YAML format
  - Includes label ID, name, description, and color
  - Example: `farmore labels miztizm/farmore --format yaml`

- **`milestones` command** - Export all milestones from a repository
  - Export to JSON or YAML format
  - `--state` filter: 'open', 'closed', or 'all'
  - Includes progress tracking (open/closed issues)
  - Example: `farmore milestones myorg/myrepo --state open`

- **`webhooks` command** - Export webhook configuration
  - Requires admin access to the repository
  - Secrets are automatically redacted for security
  - Export to JSON or YAML format
  - Example: `farmore webhooks myorg/myrepo`

- **`followers` command** - Export followers and following lists
  - `--include-following` flag to export both directions
  - Works for authenticated user or specified username
  - Export to JSON or YAML format
  - Example: `farmore followers miztizm --include-following`

- **`discussions` command** - Export GitHub Discussions
  - Uses GraphQL API for complete discussion data
  - Includes category, upvote count, answer status
  - Example: `farmore discussions miztizm/farmore`

- **`projects` command** - Export GitHub Projects (v2)
  - Supports user/org level and repository level projects
  - Uses GraphQL API for complete project data
  - Includes fields, items count, status
  - Example: `farmore projects miztizm` or `farmore projects miztizm/farmore`

- **`--name-regex` / `-N` option** - Filter repos by name pattern
  - Available in `user` and `org` commands
  - Uses Python regex syntax
  - Example: `farmore user miztizm --name-regex '^my-prefix-.*'`

- **`--incremental` / `-i` flag** - Incremental backup support
  - Available in `user` and `org` commands
  - Infrastructure for tracking backup state (to be wired in future release)
  - Example: `farmore user miztizm --incremental`

- **New data models**:
  - `Label` - Repository label with color
  - `Milestone` - Project milestone with progress
  - `Webhook` - Repository webhook configuration
  - `Follower` - User follower/following relationship
  - `Discussion` - GitHub Discussion with GraphQL fields
  - `Project` - GitHub Project v2 with fields
  - `ProjectItem` - Item within a project

- **New API methods in `GitHubAPIClient`**:
  - `get_labels()` - Fetch repository labels
  - `get_milestones()` - Fetch repository milestones
  - `get_webhooks()` - Fetch repository webhooks
  - `get_followers()` - Fetch user followers
  - `get_following()` - Fetch users being followed
  - `get_discussions()` - Fetch discussions via GraphQL
  - `get_projects()` - Fetch projects via GraphQL

- **Incremental backup infrastructure**:
  - `farmore/incremental.py` - State management module
  - `BackupState` dataclass for tracking backups
  - `IncrementalBackupManager` for state persistence

### Changed
- **Repository filtering** - Added regex pattern matching
  - New `name_regex` field in Config
  - Applied during `_filter_repositories()` in API client
- **Config model** - Extended with new options:
  - `name_regex: str | None` - Regex pattern for repo name filtering
  - `incremental: bool` - Enable incremental backup mode
- **User-Agent header** - Updated to `Farmore/0.6.0`

### Notes
- GraphQL API calls require authentication (for discussions and projects)
- Webhook export requires admin access to the repository
- Incremental flag is infrastructure-ready but state tracking integration 
  will be completed in a future release

## [0.5.0] - 2025-11-26

### Added
- **`gists` command** - Backup all gists for a user
  - Clone gists as git repositories with full history
  - `--starred` flag to include starred gists
  - Support for GitHub Enterprise via `--github-host`
  - `--skip-existing` flag for incremental backups
  - Automatic deduplication of starred gists
  - Example: `farmore gists miztizm --starred`

- **`attachments` command** - Download attachments from issues and PRs
  - Extract images and files from issue/PR bodies and comments
  - Support for GitHub's new user-attachments URLs
  - Support for private-user-images URLs
  - Checksum tracking for integrity verification
  - Collision handling with unique filename generation
  - Manifest file (manifest.json) for tracking downloads
  - `--source` option: 'issues', 'pulls', or 'all'
  - Example: `farmore attachments miztizm/farmore --source all`

- **New modules**:
  - `farmore/gists.py` - Gists API client and backup handler
    - `GistsClient` - API client for gist operations
    - `GistsBackup` - Clone and update gists as repositories
    - `Gist` and `GistFile` data models
  - `farmore/attachments.py` - Attachment extraction and download
    - `AttachmentExtractor` - Extract URLs from markdown content
    - `AttachmentDownloader` - Download with checksum and collision handling
    - `AttachmentManifest` - Track download results and metadata
    - Support for 6+ GitHub attachment URL patterns

### Changed
- **Docker image** - Enhanced for production use
  - Non-root user for improved security
  - Health check endpoint
  - CA certificates and timezone support
  - Usage examples in Dockerfile comments
  - Version updated to 0.5.0

- **User-Agent header** - Updated to `Farmore/0.5.0`

### Documentation
- **COMPETITIVE_ANALYSIS.md** - Updated with Phase 2 implementation status
  - `--exclude` filter ✅ (v0.4.0)
  - `--skip-existing` flag ✅ (v0.4.0)
  - Docker support ✅ (v0.4.0, enhanced v0.5.0)
  - Gists backup ✅ (v0.5.0)
  - Attachment downloads ✅ (v0.5.0)

## [0.4.0] - 2025-11-26

### Added
- **`--bare` flag** - Create bare/mirror clones that preserve all refs, branches, and tags
  - True 1:1 backups of repositories
  - Uses `git clone --mirror` for complete repository preservation
  - Automatic detection of bare repositories for updates
- **`--lfs` flag** - Git LFS support for repositories with large files
  - Uses `git lfs clone` for LFS-enabled repositories
  - Automatic LFS availability check with helpful error messages
  - Extended timeout for large file downloads (10 minutes)
- **`--skip-existing` flag** - Skip repositories that already exist locally
  - Faster partial syncs for stable repositories
  - Useful for incremental backup strategies
- **`--exclude` option** - Exclude specific repositories by name
  - Can be used multiple times: `--exclude repo1 --exclude repo2`
  - Filters applied after API fetch for efficiency
- **`--github-host` / `-H` option** - GitHub Enterprise support
  - Connect to self-hosted GitHub Enterprise servers
  - Supports `GITHUB_HOST` environment variable
  - Automatically uses `/api/v3` endpoint path
- **Retry on transient failures** - Automatic retry with exponential backoff
  - Retries on 502, 503, 504 server errors
  - Retries on connection errors and timeouts
  - Configurable max retries (default: 3) and delay (default: 5s)
  - Backoff multiplier of 2x between retries
- **Docker support** - Official Dockerfile for containerized backups
  - Multi-stage Alpine build for minimal image size
  - Git LFS pre-installed
  - SSH key mounting support
  - Volume mounts for backups and SSH keys
- **New git operations**:
  - `is_lfs_available()` - Check if git-lfs is installed
  - `fetch_lfs()` - Fetch LFS objects from remote
  - `update_mirror()` - Update bare/mirror repositories
  - `fetch()` with `--prune` support

### Changed
- **Config model** - Extended with new options:
  - `bare: bool` - Create bare/mirror clones
  - `lfs: bool` - Use Git LFS for cloning
  - `skip_existing: bool` - Skip existing repos
  - `exclude_repos: list[str]` - Repository names to exclude
  - `github_host: str | None` - GitHub Enterprise hostname
- **GitHubAPIClient** - Now supports GitHub Enterprise
  - Dynamic `BASE_URL` based on `github_host` config
  - Updated User-Agent to version 0.4.0
- **Git repository detection** - Now correctly identifies bare repositories
  - Checks for `HEAD` and `objects` directory for bare repos
- **`_filter_repositories()`** - Added exclude repos filter
- **MirrorOrchestrator** - Passes `bare` and `lfs` options through to git operations
- **User-Agent header** - Updated to `Farmore/0.4.0`


## [0.3.5] - 2025-11-21

### Added
- **Input validation module** - Comprehensive security validation for all user inputs
  - `validate_repository_format()` - Prevents command injection and enforces GitHub naming rules
  - `validate_github_token()` - Token format and length validation
  - `validate_path_safety()` - Path traversal attack prevention
  - `validate_format_option()` - Enum validation for export formats
  - `validate_state_option()` - Enum validation for issue/PR states
  - `sanitize_filename()` - Safe filename generation from user input
  - `sanitize_command_arg()` - Command injection prevention for subprocess calls
- **Resource management** - Added context manager support to GitHubAPIClient
  - `__enter__` and `__exit__` methods for automatic session cleanup
  - `close()` method to explicitly close HTTP sessions
  - Prevents resource leaks in long-running operations
- **Comprehensive test suite** - Added 20 validation tests with 100% pass rate
  - Repository format validation tests
  - Token validation tests
  - Path safety tests
  - Format and state option tests
  - Filename sanitization tests
- **Documentation** - Added comprehensive audit documentation
  - CODE_QUALITY_AUDIT.md - Detailed code quality analysis
  - AUDIT_COMPLETION_SUMMARY.md - Implementation summary

### Changed
- **GitHubAPIClient** - Updated User-Agent header to reflect current version
- **Security posture** - Upgraded from B+ to A- grade through validation improvements

### Fixed
- **Version synchronization** - Aligned __init__.py version with pyproject.toml (0.3.4)
- **Resource leaks** - HTTP sessions now properly closed after use

### Security
- **Command injection prevention** - All user inputs validated before subprocess calls
- **Path traversal prevention** - Directory traversal attempts blocked
- **Input sanitization** - Filenames and arguments sanitized against malicious input

## [0.3.4] - 2025-11-20

### Changed
- **Repository cleanup** - Removed accidentally committed external repository references from git history

## [0.3.3] - 2024-01-XX

### Added
- **Repository search functionality** - New `search_repositories()` method in GitHubAPIClient
  - Search GitHub repositories using the Search API
  - Filter by programming language
  - Filter by minimum stars
  - Custom sorting options (stars, forks, updated, best-match)
  - Configurable result limits (1-100)
- **Comprehensive test coverage** - Added tests for search functionality
  - Basic search
  - Language filters
  - Star filters
  - Sorting options
  - Empty results handling
  - Validation and error handling

## [0.3.0] - 2024-01-XX

### Added
- **New `repo` command** - Backup single repositories with optional data exports
- **New `issues` command** - Export all issues from a repository to JSON/YAML
- **New `pulls` command** - Export all pull requests from a repository to JSON/YAML
- **New `workflows` command** - Backup GitHub Actions workflows and run history
- **New `releases` command** - Download releases with metadata and binary assets
- **New `wiki` command** - Clone repository wikis as git repositories
- **Data export integration** - Added `--include-*` flags to `user` and `org` commands:
  - `--include-issues` - Export issues for each repository
  - `--include-pulls` - Export pull requests for each repository
  - `--include-workflows` - Backup workflows for each repository
  - `--include-releases` - Download releases for each repository
  - `--include-wikis` - Backup wikis for each repository
- **`--all` flag** for `repo` command - Include all data types in one command
- **`--include-comments` option** - Include comments when exporting issues and PRs
- **`--include-runs` option** - Include workflow run history when backing up workflows
- **`--download-assets` option** - Download binary assets when backing up releases
- **`--format` option** - Export data in JSON or YAML format
- **`--state` option** - Filter issues and PRs by state (all/open/closed)
- **New directory structure** - Separation of code (`repos/`) from metadata (`data/`)
- **`get_repository()` method** in GitHubAPIClient - Fetch single repository information
- **`get_issues()` method** in GitHubAPIClient - Fetch all issues with pagination
- **`get_pull_requests()` method** in GitHubAPIClient - Fetch all PRs with pagination
- **`get_workflows()` method** in GitHubAPIClient - Fetch workflow files
- **`get_workflow_runs()` method** in GitHubAPIClient - Fetch workflow run history
- **`get_releases()` method** in GitHubAPIClient - Fetch all releases
- **`export_repository_data()` helper function** - Unified data export logic
- **`clone_wiki()` function** in git_utils - Clone repository wikis

### Changed
- **Directory structure** - Reorganized to separate repositories (`repos/`) from metadata (`data/`)
- **Documentation** - Updated README.md with comprehensive command reference
- **Documentation** - Created standalone README.md for public GitHub distribution

## [0.2.0] - 2024-01-XX

### Added
- **New `profile` command** - Export GitHub user profile information to JSON/YAML
- **New `starred` command** - Mirror all repositories starred by a user
- **New `watched` command** - Mirror all repositories watched by a user
- **New `secrets` command** - Export repository secret names (values never exposed)
- **New `delete` command** - Delete a repository with confirmation
- **`--format` option** - Export profile and secrets in JSON or YAML format
- **`--force` flag** for delete command - Skip confirmation prompt
- **Directory reorganization** - Automatic categorization by repository type:
  - `private/` - Private repositories
  - `public/` - Public repositories
  - `starred/` - Starred repositories
  - `watched/` - Watched repositories
  - `organizations/` - Organization repositories
  - `forks/` - Forked repositories
- **`get_user_profile()` method** in GitHubAPIClient - Fetch user profile
- **`get_starred_repos()` method** in GitHubAPIClient - Fetch starred repositories
- **`get_watched_repos()` method** in GitHubAPIClient - Fetch watched repositories
- **`get_repo_secrets()` method** in GitHubAPIClient - Fetch repository secrets
- **`delete_repository()` method** in GitHubAPIClient - Delete a repository
- **RepositoryCategory enum** - Type-safe repository categorization
- **Comprehensive documentation** - Added docs/ folder with detailed guides:
  - AUTHENTICATION.md - GitHub token setup guide
  - DIRECTORY_STRUCTURE.md - Backup organization guide
  - DEVELOPMENT.md - Developer setup guide
  - FEATURE_SUGGESTIONS.md - Future roadmap

### Changed
- **Default destination** - Changed from `farmore_backups/` to `backups/<username>/`
- **Repository organization** - Automatic categorization by type and ownership
- **Documentation** - Expanded README.md with new features and examples

### Fixed
- **Authenticated user endpoint** - Fixed bug where only 6 repositories were found
  - Changed from `/users/{username}/repos` to `/user/repos` for authenticated user
  - Now correctly discovers all repositories for the authenticated user

## [0.1.0] - 2024-01-XX

### Added
- **Initial release** of Farmore
- **Core functionality** - Backup GitHub repositories for users and organizations
- **`user` command** - Backup all repositories for a GitHub user
- **`org` command** - Backup all repositories for a GitHub organization
- **`mirror` command** - Mirror a single repository
- **GitHub API integration** - Full REST API v3 support with pagination
- **Authentication** - GitHub Personal Access Token support via environment variables
- **Rate limit handling** - Automatic retries with exponential backoff
- **Parallel processing** - Configurable worker threads for faster backups
- **Smart cloning** - SSH first, HTTPS fallback with token authentication
- **Incremental backups** - Updates existing repos, clones new ones
- **Filtering options**:
  - `--visibility` - Filter by public/private/all
  - `--include-forks` - Include forked repositories
  - `--include-archived` - Include archived repositories
  - `--exclude-orgs` - Exclude organization repositories
- **`--dry-run` flag** - Preview what would be backed up without doing it
- **`--max-workers` option** - Configure parallel processing threads
- **`--use-ssh` / `--no-use-ssh` flags** - Control SSH vs HTTPS cloning
- **`--dest` option** - Custom backup destination directory
- **Rich terminal output** - Progress bars and beautiful formatting
- **Error resilience** - Continues processing even if individual repos fail
- **Comprehensive logging** - Detailed operation logs
- **`.env` file support** - Load GitHub token from environment file
- **Cross-platform support** - Works on Linux, macOS, and Windows
- **Python 3.10+ support** - Modern Python with type hints
- **PEP 621 compliant** - Standard pyproject.toml packaging
- **MIT License** - Open source license

