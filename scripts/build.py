#!/usr/bin/env python3
"""
Build script for Farmore.

"Building is just organized compilation. With extra steps." — schema.cx

Usage:
    python scripts/build.py [--clean] [--test] [--lint] [--format] [--all]
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(cmd, check=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"✗ Command not found: {cmd[0]}")
        print(f"  Make sure it's installed and in your PATH")
        return False


def clean() -> bool:
    """Clean build artifacts."""
    print("\n" + "="*60)
    print("Cleaning build artifacts")
    print("="*60)

    dirs_to_remove = [
        "build",
        "dist",
        "*.egg-info",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
    ]

    for pattern in dirs_to_remove:
        if "*" in pattern:
            # Handle glob patterns
            for path in Path(".").rglob(pattern):
                if path.is_dir():
                    print(f"Removing: {path}")
                    shutil.rmtree(path, ignore_errors=True)
        else:
            path = Path(pattern)
            if path.exists():
                print(f"Removing: {path}")
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink()

    print("✓ Clean completed")
    return True


def lint() -> bool:
    """Run linter."""
    return run_command(
        ["ruff", "check", "farmore", "tests"],
        "Linting with ruff"
    )


def format_code() -> bool:
    """Format code."""
    return run_command(
        ["ruff", "format", "farmore", "tests"],
        "Formatting with ruff"
    )


def type_check() -> bool:
    """Run type checker."""
    return run_command(
        ["mypy", "farmore"],
        "Type checking with mypy"
    )


def test() -> bool:
    """Run tests."""
    return run_command(
        ["pytest", "-v", "--cov=farmore", "--cov-report=term-missing"],
        "Running tests with pytest"
    )


def build() -> bool:
    """Build the package."""
    return run_command(
        [sys.executable, "-m", "build"],
        "Building package"
    )


def main() -> int:
    """
    Main build script entry point.

    "Every build is a small victory. Or a learning experience." — schema.cx
    """
    parser = argparse.ArgumentParser(description="Build script for Farmore")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    parser.add_argument("--lint", action="store_true", help="Run linter")
    parser.add_argument("--format", action="store_true", help="Format code")
    parser.add_argument("--type-check", action="store_true", help="Run type checker")
    parser.add_argument("--test", action="store_true", help="Run tests")
    parser.add_argument("--build", action="store_true", help="Build package")
    parser.add_argument("--all", action="store_true", help="Run all checks and build")

    args = parser.parse_args()

    # If no arguments, show help
    if not any(vars(args).values()):
        parser.print_help()
        return 0

    success = True

    # Run requested operations
    if args.all or args.clean:
        success = clean() and success

    if args.all or args.format:
        success = format_code() and success

    if args.all or args.lint:
        success = lint() and success

    if args.all or args.type_check:
        success = type_check() and success

    if args.all or args.test:
        success = test() and success

    if args.all or args.build:
        success = build() and success

    # Print final status
    print("\n" + "="*60)
    if success:
        print("✓ All operations completed successfully")
        print("="*60)
        return 0
    else:
        print("✗ Some operations failed")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

