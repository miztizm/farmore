# CLAUDE.md — Farmore

> 🥔 Mirror every repo you own — in one command.

Farmore is a Python CLI that backs up GitHub accounts end-to-end: clone repos (bare/mirror/LFS), export issues, PRs, releases, wikis, gists, discussions, and Projects v2 — built on Typer + Rich over the GitHub REST/GraphQL APIs. See [README.md](README.md).

## Future Vision

Farmore becomes the definitive "own your GitHub" tool — one command that produces a complete, restorable, offline mirror of everything a user or org has on GitHub, with incremental state, scheduling, and analytics so a backup stays fresh without thought. It should be trustworthy enough to be the disaster-recovery plan for a whole organization, and simple enough that a solo dev runs it once and forgets it's working.

**How we build it:** correctness and completeness first — never silently drop data, always respect rate limits with backoff, keep the directory layout stable and restorable, and secrets stay secret (names only, never values); clean, typed, tested Python (ruff + mypy + pytest) under a fast, legible CLI — in code we trust.

## Stack & structure

- Python 3.10+, packaged as `farmore` on PyPI; entry point `farmore = farmore.cli:app`.
- Deps: `requests`, `typer`, `rich`, `python-dotenv`, `pyyaml`, `schedule`.
- Source in `farmore/` (`cli.py`, `config.py`, `analytics.py`, `git_utils.py`, per-domain export modules); tests in `tests/`; Docker packaging via `Dockerfile`.
- Dev tooling: ruff (line-length 100), mypy (strict untyped-def rules), pytest with coverage. GitHub Enterprise supported via `--api-url` / `GITHUB_API_URL`.
