# 🥔 Farmore

> _"Mirror every repo you own — in one command."_

**Farmore** is a comprehensive Python CLI tool for backing up GitHub repositories and their associated data. Clone repositories, export issues, download releases, backup wikis, and more — all with a single command.

**Version:** 0.3.3
**License:** MIT
**Python:** 3.10+

---

## ✨ Features

### 🔄 Repository Management
- **Bulk backups** - Clone all repos for a user or organization in one command
- **Single repo backups** - Backup individual repositories with the `repo` command
- **Repository search** - Search GitHub and clone matching repositories by keyword
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

**Python Version:** 3.10 or higher is required.

**Additional Requirements:**
- Git installed and available in PATH
- GitHub Personal Access Token (for private repos and higher rate limits)

---

### 🎯 From PyPI (Recommended)

The easiest way to install Farmore is from the Python Package Index (PyPI):

```bash
pip install farmore
```

This is the recommended method for end users. Once installed, the `farmore` command will be available globally.

**Verify installation:**
```bash
farmore --version
farmore --help
```

---

### 🧪 From TestPyPI (Pre-release Testing)

To test pre-release versions before they're published to PyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ farmore
```

**When to use this:**
- Testing new features before official release
- Helping with beta testing
- Verifying bug fixes in development versions

**Note:** TestPyPI packages may not have all dependencies available. You might need to install dependencies from regular PyPI separately.

---

### 📥 From GitHub Releases (Specific Versions)

Download a specific version from the [GitHub Releases page](https://github.com/miztizm/farmore/releases):

1. **Download the `.whl` file** from the release you want (e.g., `farmore-0.3.0-py3-none-any.whl`)
2. **Install the downloaded file:**

```bash
pip install farmore-0.3.0-py3-none-any.whl
```

**When to use this:**
- You need a specific version
- You want to verify package integrity
- You're installing in an offline environment (download first, install later)

**Alternative - Source distribution:**
```bash
# Download the .tar.gz file instead
pip install farmore-0.3.0.tar.gz
```

---

### 🔧 From Source (Development)

For developers who want to contribute or modify the code:

```bash
# Clone the repository
git clone https://github.com/miztizm/farmore.git
cd farmore

# Install in editable mode (changes to code take effect immediately)
pip install -e .

# Or install with development dependencies (recommended for contributors)
pip install -e ".[dev]"
```

**Development dependencies include:**
- `pytest` - Testing framework
- `pytest-cov` - Code coverage
- `ruff` - Linting and formatting
- `mypy` - Type checking
- Additional testing utilities

**Verify installation:**
```bash
farmore --version
farmore --help
```

---

### 🔄 Upgrading

To upgrade to the latest version:

```bash
# From PyPI
pip install --upgrade farmore

# From TestPyPI
pip install --upgrade --index-url https://test.pypi.org/simple/ farmore
```

---

### 🗑️ Uninstalling

To remove Farmore:

```bash
pip uninstall farmore
```

---

## 🚀 Quick Start

```bash
# Backup all repos for a user
farmore user miztizm

# Backup a single repository
farmore repo microsoft/vscode

# Search and clone repositories by keyword
farmore search "nuxt laravel" --limit 10

# Backup with issues and pull requests
farmore repo miztizm/hello-world --include-issues --include-pulls

# Backup everything for a repository
farmore repo python/cpython --all

# Backup all repos for an organization
farmore org github --include-issues --include-pulls

# With authentication (recommended)
export GITHUB_TOKEN=ghp_your_token_here
farmore user miztizm
```

_"They say privacy is dead. Prove them wrong. Use a token."_ — schema.cx

---

## 🔑 Authentication

Farmore uses GitHub Personal Access Tokens (PAT) for authentication. Tokens provide:
- Access to private repositories
- Higher rate limits (5,000 vs 60 requests/hour)
- Organization repository access

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

Farmore provides **14 commands** organized into 4 categories:

### 🔄 Repository Backup

#### `farmore user <username>`
Backup all private and public repositories for a GitHub user.

```bash
# Backup all repos
farmore user miztizm

# Backup with data exports
farmore user miztizm --include-issues --include-pulls

# Filter by visibility
farmore user miztizm --visibility public

# Dry run
farmore user miztizm --dry-run
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

#### `farmore search <query>` 🆕
Search GitHub repositories by keyword and clone matching results.

```bash
# Basic search - clone top 10 results
farmore search "smsbomber"

# Search with filters
farmore search "machine learning" --language python --min-stars 1000 --limit 20

# Search and auto-confirm (skip prompt)
farmore search "react components" --limit 5 --yes

# Custom output directory
farmore search "awesome-python" --output-dir ./my-collections --limit 15

# Sort by stars (descending)
farmore search "cli tools" --language go --sort stars --order desc --limit 25

# Flat structure (no owner subdirectories)
farmore search "react hooks" --flat-structure --limit 10
```

**Key Options:**
- `--limit` (1-100): Maximum repositories to clone (default: 10)
- `--language`: Filter by programming language (e.g., "python", "javascript", "go")
- `--min-stars`: Minimum number of stars required
- `--sort`: Sort order - "best-match" (default), "stars", "forks", or "updated"
- `--order`: Sort direction - "desc" (default) or "asc"
- `--yes` / `-y`: Skip confirmation prompt
- `--output-dir`: Custom output directory (default: `./search-results/<query>/`)
- `--flat-structure`: Clone repos directly without owner subdirectories
- `--workers`: Number of parallel workers for cloning (default: 4)

**Output Structure (Default):**
```
search-results/
└── <sanitized-query>/
    ├── <owner1>/
    │   └── <repo1>/
    ├── <owner2>/
    │   └── <repo2>/
    └── <owner3>/
        └── <repo3>/
```

**Output Structure (Flat - with `--flat-structure`):**
```
search-results/
└── <sanitized-query>/
    ├── <repo1>/
    ├── <repo2>/
    └── <repo3>/
```

**Note:** When using `--flat-structure`, repositories with duplicate names will have their owner appended (e.g., `repo-owner`) to avoid conflicts.

**Rate Limits:**
- Search API: 30 requests/minute (authenticated users)
- Unauthenticated: 10 requests/minute

**Note:** The search command uses GitHub's search API with support for advanced search qualifiers. You can also use GitHub's native search syntax directly in the query (e.g., `"language:python stars:>1000"`).

---

### 📊 Data Export

#### `farmore issues <owner>/<repo>`
Export issues to JSON/YAML.

```bash
farmore issues microsoft/vscode
farmore issues miztizm/hello-world --state open --include-comments
```

**Options:** `--format [json|yaml]`, `--state [all|open|closed]`, `--include-comments`

#### `farmore pulls <owner>/<repo>`
Export pull requests to JSON/YAML.

```bash
farmore pulls microsoft/vscode
farmore pulls miztizm/hello-world --state open --include-comments
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
farmore profile miztizm      # Another user's profile
```

**Options:** `--format [json|yaml]`

#### `farmore starred [username]`
Mirror starred repositories.

```bash
farmore starred              # Your starred repos
farmore starred miztizm      # Another user's starred repos
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

1. **Discovery** - Uses GitHub API to find repositories
2. **Filtering** - Applies visibility, fork, and archived filters
3. **Parallel Processing** - Processes multiple repos simultaneously
4. **Smart Cloning** - Tries SSH first, falls back to HTTPS
5. **Progress Reporting** - Real-time progress with rich output
6. **Summary** - Final statistics and error reporting

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

- 🐛 For bugs, [**Issues**](https://github.com/miztizm/farmore/issues)
- 📩 For questions, [**Email**](mailto:&#103;&#105;&#116;&#104;&#117;&#98;&#64;&#109;&#105;&#122;&#116;&#105;&#122;&#109;&#46;&#99;&#111;&#109;)

---

## 🌟 Acknowledgments

Built with [Typer](https://typer.tiangolo.com/), [Rich](https://rich.readthedocs.io/), [Requests](https://requests.readthedocs.io/), and [PyYAML](https://pyyaml.org/).

---

_"Control is an illusion. But backups? Those are real."_ — schema.cx

**Made with 🥔 by miztizm**
