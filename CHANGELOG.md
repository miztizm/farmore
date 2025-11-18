# Changelog

All notable changes to Farmore will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

