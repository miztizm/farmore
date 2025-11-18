#!/usr/bin/env python3
"""Script to create comprehensive standalone README.md for Farmore v0.3.0 public GitHub release"""

README_CONTENT = r"""# 🥔 Farmore

> _"Mirror every repo you own — in one command."_

**Farmore** is a comprehensive Python CLI tool for backing up GitHub repositories and their associated data. Clone repositories, export issues, download releases, backup wikis, and more — all with a single command.

**Version:** 0.3.0
**License:** MIT
**Python:** 3.10+

_"Control is an illusion. But backups? Those are real."_ — schema.cx

---

## ✨ Features

### 🔄 Repository Management
- **Bulk backups** - Clone all repos for a user or organization in one command
- **Single repo backups** - Backup individual repositories with the `repo` command
- **Smart updates** - Automatically pulls updates for existing repositories
- **Parallel processing** - Fast backups with configurable worker threads
- **SSH/HTTPS support** - Tries SSH first, falls back to HTTPS with token

### 📊 Data Export
- **Issues export** - Export all issues to JSON/YAML with optional comments
- **Pull requests export** - Export PRs with metadata and comments
- **Workflows backup** - Backup GitHub Actions workflows and run history
- **Releases download** - Download releases with metadata and binary assets
- **Wiki backup** - Clone repository wikis as git repositories

### 🔐 Access & Security
- **Private repository support** - Full access with GitHub Personal Access Tokens
- **Organization repos** - Backup all organization repositories
- **Starred & watched repos** - Mirror repositories you've starred or are watching
- **Secrets export** - Export repository secret names (values are never exposed)

### 🎯 Advanced Features
- **Flexible filtering** - By visibility (public/private/all), forks, archived status
- **Rate limit handling** - Automatic retries with exponential backoff
- **Organized structure** - Clean directory organization separating code from data
- **Cross-platform** - Works on Linux, macOS, and Windows
- **Beautiful CLI** - Powered by Typer and Rich with progress bars

---

## 📦 Installation

### Requirements
- Python 3.10 or higher
- Git installed and available in PATH
- GitHub Personal Access Token (for private repos and higher rate limits)

### From Source

```bash
# Clone the repository
git clone https://github.com/miztizm/farmore.git
cd farmore

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Verify Installation

```bash
farmore --version
farmore --help
```

---

## 🚀 Quick Start

```bash
# Backup all repos for a user
farmore user octocat

# Backup a single repository
farmore repo microsoft/vscode

# Backup with issues and pull requests
farmore repo octocat/hello-world --include-issues --include-pulls

# Backup everything for a repository
farmore repo python/cpython --all

# Backup all repos for an organization
farmore org github --include-issues --include-pulls

# With authentication (recommended)
export GITHUB_TOKEN=ghp_your_token_here
farmore user octocat
```

_"They say privacy is dead. Prove them wrong. Use a token."_ — schema.cx

---

## 🔑 Authentication

Farmore uses GitHub Personal Access Tokens (PAT) for authentication. Tokens provide:
- 🔐 Access to private repositories
- 🚀 Higher rate limits (5,000 vs 60 requests/hour)
- 🏢 Organization repository access

### Creating a Token

**⭐ Recommended: Use Classic Personal Access Token**

1. **Create a Classic PAT:** https://github.com/settings/tokens
   - Click **"Tokens (classic)"** → **"Generate new token (classic)"**
   - Give it a name: `farmore-backup`
   - Select scope: ✅ **`repo`** (required for private repositories)
   - Optional: ✅ **`delete_repo`** (only if using `farmore delete` command)
   - Click "Generate token" and **copy it immediately**

2. **Set environment variable:**

```bash
# Linux/macOS
export GITHUB_TOKEN=ghp_your_token_here

# Windows PowerShell
$env:GITHUB_TOKEN="ghp_your_token_here"

# Or create a .env file in the project directory
echo "GITHUB_TOKEN=ghp_your_token_here" > .env
```

### Why Classic PAT?
- ✅ Simple setup (just check `repo` scope)
- ✅ Works with all repository types (personal + organization)
- ✅ Proven reliability
- ✅ Broader API compatibility

### Rate Limits

| Mode | Requests/Hour | Use Case |
|------|---------------|----------|
| ❌ Unauthenticated | 60 | Small public repos only |
| ✅ Authenticated | 5,000 | Production, private repos |

### Security Best Practices

- ✅ Use environment variables or `.env` files
- ✅ Set token expiration (90 days recommended)
- ✅ Use minimal required permissions
- ❌ Never commit tokens to version control
- ❌ Avoid `--token` flag (exposes in shell history)

---

## 📚 Commands

Farmore provides **13 commands** organized into 4 categories:

### 🔄 Repository Backup

#### `farmore user <username>`
Backup all repositories for a GitHub user.

```bash
# Backup all repos
farmore user miztizm

# Backup with data exports
farmore user miztizm --include-issues --include-pulls

# Filter by visibility
farmore user octocat --visibility public

# Dry run
farmore user octocat --dry-run
```

**Key Options:** `--visibility`, `--include-forks`, `--include-archived`, `--include-issues`, `--include-pulls`, `--include-workflows`, `--include-releases`, `--include-wikis`, `--max-workers`, `--dry-run`

#### `farmore org <orgname>`
Backup all repositories for an organization. Same options as `user`.

#### `farmore repo <owner>/<repo>`
Backup a single repository with optional data exports.

```bash
# Just clone
farmore repo microsoft/vscode

# Clone + data
farmore repo microsoft/vscode --include-issues --include-pulls

# Everything
farmore repo python/cpython --all
```

**Key Options:** `--include-issues`, `--include-pulls`, `--include-workflows`, `--include-releases`, `--include-wikis`, `--all`

---

### 📊 Data Export

#### `farmore issues <owner>/<repo>`
Export issues to JSON/YAML.

```bash
farmore issues microsoft/vscode
farmore issues octocat/hello-world --state open --include-comments
```

**Options:** `--format [json|yaml]`, `--state [all|open|closed]`, `--include-comments`

#### `farmore pulls <owner>/<repo>`
Export pull requests to JSON/YAML.

```bash
farmore pulls microsoft/vscode
farmore pulls octocat/hello-world --state open --include-comments
```

**Options:** `--format [json|yaml]`, `--state [all|open|closed]`, `--include-comments`

#### `farmore workflows <owner>/<repo>`
Backup GitHub Actions workflows.

```bash
farmore workflows microsoft/vscode
farmore workflows actions/checkout --include-runs
```

**Options:** `--include-runs`

#### `farmore releases <owner>/<repo>`
Download releases and assets.

```bash
farmore releases microsoft/vscode
farmore releases nodejs/node --download-assets
```

**Options:** `--download-assets`

#### `farmore wiki <owner>/<repo>`
Clone repository wiki.

```bash
farmore wiki python/cpython
```

---

### 🔍 Profile & Discovery

#### `farmore profile [username]`
Export user profile.

```bash
farmore profile              # Your profile
farmore profile octocat      # Another user's profile
```

**Options:** `--format [json|yaml]`

#### `farmore starred [username]`
Mirror starred repositories.

```bash
farmore starred              # Your starred repos
farmore starred octocat      # Another user's starred repos
```

#### `farmore watched [username]`
Mirror watched repositories.

```bash
farmore watched
```

---

### 🔐 Security & Management

#### `farmore secrets <owner>/<repo>`
Export repository secret names (values never exposed).

```bash
farmore secrets miztizm/farmore
```

**Options:** `--format [json|yaml]`

#### `farmore delete <owner>/<repo>`
Delete a repository (requires confirmation).

```bash
farmore delete miztizm/old-project
farmore delete miztizm/test-repo --force  # Skip confirmation
```

**⚠️ Warning:** Requires `delete_repo` scope in your GitHub token.

---

## 📂 Directory Structure

Farmore organizes backups with a clean structure that separates code from metadata:

```
backups/
└── <username>/
    ├── profile.json                          # User profile
    ├── repos/                                # Git repositories
    │   ├── private/<owner>/<repo>/
    │   ├── public/<owner>/<repo>/
    │   ├── starred/<owner>/<repo>/
    │   ├── watched/<owner>/<repo>/
    │   ├── organizations/<owner>/<repo>/
    │   └── forks/<owner>/<repo>/
    └── data/                                 # Metadata
        ├── issues/<owner>_<repo>_issues.json
        ├── pulls/<owner>_<repo>_pulls.json
        ├── workflows/<owner>_<repo>/
        ├── releases/<owner>_<repo>/
        ├── wikis/<owner>_<repo>.wiki/
        └── secrets/<owner>_<repo>_secrets.json
```

**Example:**
```bash
# After: farmore user miztizm --include-issues --include-pulls
backups/miztizm/
├── profile.json
├── repos/
│   ├── public/miztizm/farmore/
│   └── private/miztizm/secret-project/
└── data/
    ├── issues/
    │   ├── miztizm_farmore_issues.json
    │   └── miztizm_secret-project_issues.json
    └── pulls/
        ├── miztizm_farmore_pulls.json
        └── miztizm_secret-project_pulls.json
```

---

## 🔧 How It Works

1. **🔍 Discovery** - Uses GitHub API to find repositories
2. **🎯 Filtering** - Applies visibility, fork, and archived filters
3. **⚡ Parallel Processing** - Processes multiple repos simultaneously
4. **🔄 Smart Cloning** - Tries SSH first, falls back to HTTPS
5. **📊 Progress Reporting** - Real-time progress with rich output
6. **✅ Summary** - Final statistics and error reporting

**Key Features:**
- **Incremental backups** - Updates existing repos, clones new ones
- **Error resilience** - Continues even if individual repos fail
- **Rate limit aware** - Handles GitHub API limits automatically
- **Organized output** - Auto-categorizes by type

---

## 🛠️ Development

### Setup

```bash
git clone https://github.com/miztizm/farmore.git
cd farmore
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### Testing

```bash
pytest                                    # Run all tests
pytest --cov=farmore --cov-report=html   # With coverage
pytest tests/test_github_api.py          # Specific test
```

### Code Quality

```bash
black farmore/        # Format
ruff check farmore/   # Lint
mypy farmore/         # Type check
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions welcome! Please:
1. Check existing issues and PRs
2. Follow the existing code style
3. Add tests for new features
4. Update documentation

---

## 💬 Support

- 🐛 **Issues:** https://github.com/miztizm/farmore/issues
- 💡 **Discussions:** https://github.com/miztizm/farmore/discussions

---

## 🌟 Acknowledgments

Built with [Typer](https://typer.tiangolo.com/), [Rich](https://rich.readthedocs.io/), [Requests](https://requests.readthedocs.io/), and [PyYAML](https://pyyaml.org/).

---

_"The cloud is just someone else's computer. Your backups? Those should be yours."_ — schema.cx

**Made with 🥔 by miztizm @ schema.cx**
"""

if __name__ == "__main__":
    import pathlib
    readme_path = pathlib.Path(__file__).parent.parent / "README.md"
    readme_path.write_text(README_CONTENT, encoding="utf-8")
    print(f"✅ Created {readme_path}")

