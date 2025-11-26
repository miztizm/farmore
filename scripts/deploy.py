#!/usr/bin/env python3
"""
Deployment script for Farmore.

Automates version bumping, building, committing, and pushing releases.

Usage:
    python scripts/deploy.py patch     # 0.9.0 -> 0.9.1
    python scripts/deploy.py minor     # 0.9.0 -> 0.10.0
    python scripts/deploy.py major     # 0.9.0 -> 1.0.0
    python scripts/deploy.py --dry-run patch  # Preview changes
    python scripts/deploy.py --no-push minor  # Build but don't push
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


# Files containing version strings
VERSION_FILES = [
    ("farmore/__init__.py", r'__version__ = "(\d+\.\d+\.\d+)"'),
    ("pyproject.toml", r'version = "(\d+\.\d+\.\d+)"'),
    ("README.md", r'version-(\d+\.\d+\.\d+)-orange'),
]


def get_current_version() -> str:
    """Read current version from __init__.py."""
    init_file = Path("farmore/__init__.py")
    content = init_file.read_text()
    match = re.search(r'__version__ = "(\d+\.\d+\.\d+)"', content)
    if not match:
        raise ValueError("Could not find version in farmore/__init__.py")
    return match.group(1)


def bump_version(current: str, bump_type: str) -> str:
    """Calculate new version based on bump type."""
    major, minor, patch = map(int, current.split("."))
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")


def update_version_in_file(file_path: str, pattern: str, old_ver: str, new_ver: str, dry_run: bool) -> bool:
    """Update version in a single file."""
    path = Path(file_path)
    if not path.exists():
        print(f"  ⚠ File not found: {file_path}")
        return False
    
    content = path.read_text()
    new_content = content.replace(old_ver, new_ver)
    
    if content == new_content:
        print(f"  ⚠ No changes in: {file_path}")
        return False
    
    if not dry_run:
        path.write_text(new_content)
    
    print(f"  ✓ Updated: {file_path}")
    return True


def run_command(cmd: list[str], description: str, dry_run: bool = False) -> bool:
    """Run a shell command."""
    print(f"\n→ {description}")
    print(f"  $ {' '.join(cmd)}")
    
    if dry_run:
        print("  [DRY RUN - skipped]")
        return True
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().split("\n")[:5]:
                print(f"  {line}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed: {e.stderr or e.stdout or str(e)}")
        return False
    except FileNotFoundError:
        print(f"  ✗ Command not found: {cmd[0]}")
        return False


def check_git_status() -> tuple[bool, str]:
    """Check if git working directory is clean (except for expected changes)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True
    )
    return result.returncode == 0, result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy Farmore - bump version, build, commit, and push",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/deploy.py patch          # Bug fix release
  python scripts/deploy.py minor          # New feature release  
  python scripts/deploy.py major          # Breaking change release
  python scripts/deploy.py --dry-run minor  # Preview without changes
  python scripts/deploy.py --no-push patch  # Build locally only
        """
    )
    parser.add_argument(
        "bump_type",
        choices=["major", "minor", "patch"],
        help="Version increment type"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Build and commit but don't push to remote"
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Update version and build but don't commit"
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        default=True,
        help="Create a git tag for the release (default: True)"
    )
    parser.add_argument(
        "--no-tag",
        action="store_true",
        help="Don't create a git tag"
    )
    
    args = parser.parse_args()
    
    # Header
    print("=" * 60)
    print("  FARMORE DEPLOYMENT")
    print("=" * 60)
    
    if args.dry_run:
        print("\n⚠ DRY RUN MODE - No changes will be made\n")
    
    # Step 1: Get current version
    try:
        current_version = get_current_version()
    except ValueError as e:
        print(f"✗ Error: {e}")
        return 1
    
    new_version = bump_version(current_version, args.bump_type)
    
    print(f"\n📦 Version: {current_version} → {new_version} ({args.bump_type})")
    
    # Step 2: Check git status
    print("\n→ Checking git status...")
    is_clean, status = check_git_status()
    if status.strip() and not args.dry_run:
        print("  ⚠ Working directory has uncommitted changes:")
        for line in status.strip().split("\n")[:5]:
            print(f"    {line}")
        
        response = input("\n  Continue anyway? [y/N]: ").strip().lower()
        if response != "y":
            print("  Aborted.")
            return 1
    else:
        print("  ✓ Git status OK")
    
    # Step 3: Update version in all files
    print(f"\n→ Updating version to {new_version}...")
    for file_path, pattern in VERSION_FILES:
        update_version_in_file(file_path, pattern, current_version, new_version, args.dry_run)
    
    # Step 4: Run tests
    if not run_command(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        "Running tests",
        args.dry_run
    ):
        print("\n✗ Tests failed. Aborting deployment.")
        return 1
    
    # Step 5: Build package
    if not run_command(
        [sys.executable, "scripts/build.py", "--clean", "--build"],
        "Building distribution",
        args.dry_run
    ):
        print("\n✗ Build failed. Aborting deployment.")
        return 1
    
    # Step 6: Commit changes
    if not args.no_commit:
        if not run_command(
            ["git", "add", "-A"],
            "Staging changes",
            args.dry_run
        ):
            return 1
        
        commit_msg = f"chore: bump version to {new_version}"
        if not run_command(
            ["git", "commit", "-m", commit_msg],
            f"Committing: {commit_msg}",
            args.dry_run
        ):
            return 1
        
        # Step 7: Create tag
        if args.tag and not args.no_tag:
            tag_name = f"v{new_version}"
            if not run_command(
                ["git", "tag", "-a", tag_name, "-m", f"Release {new_version}"],
                f"Creating tag: {tag_name}",
                args.dry_run
            ):
                return 1
    
    # Step 8: Push to remote
    if not args.no_push and not args.no_commit:
        if not run_command(
            ["git", "push"],
            "Pushing commits",
            args.dry_run
        ):
            return 1
        
        if args.tag and not args.no_tag:
            if not run_command(
                ["git", "push", "--tags"],
                "Pushing tags",
                args.dry_run
            ):
                return 1
    
    # Summary
    print("\n" + "=" * 60)
    print("  DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"\n  Version: {new_version}")
    print(f"  Artifacts: dist/farmore-{new_version}-py3-none-any.whl")
    print(f"             dist/farmore-{new_version}.tar.gz")
    
    if not args.no_push and not args.no_commit and not args.dry_run:
        print(f"\n  Tag: v{new_version} pushed to remote")
        print("\n  Next steps:")
        print("    1. Create GitHub release from tag")
        print("    2. Upload wheel to PyPI: twine upload dist/*")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
