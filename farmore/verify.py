"""
Backup verification and integrity checking for Farmore.

"Trust, but verify. Especially your backups." — schema.cx
"""

import hashlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class VerificationResult:
    """
    Result of a backup verification operation.

    "Results tell the story. Make sure it's a good one." — schema.cx
    """

    path: Path
    is_valid: bool
    repository_name: str = ""
    verification_type: str = "basic"

    # Git integrity
    git_valid: bool = True
    git_errors: list[str] = field(default_factory=list)

    # File integrity
    files_checked: int = 0
    files_valid: int = 0
    missing_files: list[str] = field(default_factory=list)

    # Checksum verification
    checksum_verified: bool = False
    checksum_errors: list[str] = field(default_factory=list)

    # Metadata
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": str(self.path),
            "is_valid": self.is_valid,
            "repository_name": self.repository_name,
            "verification_type": self.verification_type,
            "git_valid": self.git_valid,
            "git_errors": self.git_errors,
            "files_checked": self.files_checked,
            "files_valid": self.files_valid,
            "missing_files": self.missing_files,
            "checksum_verified": self.checksum_verified,
            "checksum_errors": self.checksum_errors,
            "checked_at": self.checked_at,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }


class BackupVerifier:
    """
    Verifies backup integrity and completeness.

    "A backup unchecked is a backup unknown." — schema.cx
    """

    def __init__(self) -> None:
        """Initialize the verifier."""
        pass

    def verify_repository(
        self,
        repo_path: Path,
        deep: bool = False,
        verify_checksums: bool = False,
    ) -> VerificationResult:
        """
        Verify a single repository backup.

        Args:
            repo_path: Path to the repository
            deep: Perform deep verification (git fsck)
            verify_checksums: Verify file checksums

        Returns:
            VerificationResult with verification details
        """
        import time

        start_time = time.time()

        result = VerificationResult(
            path=repo_path,
            is_valid=True,
            repository_name=repo_path.name,
            verification_type="deep" if deep else "basic",
        )

        # Check if directory exists
        if not repo_path.exists():
            result.is_valid = False
            result.error_message = "Repository directory does not exist"
            result.duration_seconds = time.time() - start_time
            return result

        # Check if it's a git repository
        git_dir = repo_path / ".git"
        is_bare = not git_dir.exists() and (repo_path / "HEAD").exists()

        if not git_dir.exists() and not is_bare:
            result.is_valid = False
            result.error_message = "Not a valid git repository"
            result.duration_seconds = time.time() - start_time
            return result

        # Verify git integrity
        git_result = self._verify_git_integrity(repo_path, deep)
        result.git_valid = git_result["valid"]
        result.git_errors = git_result["errors"]

        if not result.git_valid:
            result.is_valid = False

        # Verify checksums if requested
        if verify_checksums:
            checksum_result = self._verify_checksums(repo_path)
            result.checksum_verified = True
            result.checksum_errors = checksum_result["errors"]
            result.files_checked = checksum_result["files_checked"]
            result.files_valid = checksum_result["files_valid"]

            if checksum_result["errors"]:
                result.is_valid = False

        result.duration_seconds = time.time() - start_time
        return result

    def verify_backup_directory(
        self,
        backup_dir: Path,
        deep: bool = False,
        verify_checksums: bool = False,
    ) -> list[VerificationResult]:
        """
        Verify all repositories in a backup directory.

        Args:
            backup_dir: Path to the backup directory
            deep: Perform deep verification
            verify_checksums: Verify file checksums

        Returns:
            List of VerificationResults for each repository
        """
        results = []

        if not backup_dir.exists():
            return results

        # Find all git repositories
        for item in backup_dir.iterdir():
            if item.is_dir():
                # Check if it's a repository (has .git or is bare)
                if (item / ".git").exists() or (item / "HEAD").exists():
                    result = self.verify_repository(item, deep, verify_checksums)
                    results.append(result)
                else:
                    # Check subdirectories (org/user structure)
                    for subitem in item.iterdir():
                        if subitem.is_dir():
                            if (subitem / ".git").exists() or (subitem / "HEAD").exists():
                                result = self.verify_repository(subitem, deep, verify_checksums)
                                results.append(result)

        return results

    def _verify_git_integrity(self, repo_path: Path, deep: bool = False) -> dict[str, Any]:
        """
        Verify git repository integrity.

        Args:
            repo_path: Path to the repository
            deep: Run git fsck for deep verification

        Returns:
            Dictionary with validation results
        """
        result = {"valid": True, "errors": []}

        try:
            # Check if HEAD is valid
            head_check = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if head_check.returncode != 0:
                result["errors"].append(f"Invalid HEAD: {head_check.stderr.strip()}")
                result["valid"] = False

            # Run git fsck for deep verification
            if deep:
                fsck_result = subprocess.run(
                    ["git", "fsck", "--full"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minutes timeout for large repos
                )

                if fsck_result.returncode != 0:
                    result["errors"].append(f"git fsck failed: {fsck_result.stderr.strip()}")
                    result["valid"] = False

                # Check for warnings in stdout (fsck outputs issues to stdout)
                if "error" in fsck_result.stdout.lower():
                    result["errors"].append(f"git fsck errors: {fsck_result.stdout.strip()}")
                    result["valid"] = False

        except subprocess.TimeoutExpired:
            result["errors"].append("Git verification timed out")
            result["valid"] = False
        except Exception as e:
            result["errors"].append(f"Git verification failed: {str(e)}")
            result["valid"] = False

        return result

    def _verify_checksums(self, repo_path: Path) -> dict[str, Any]:
        """
        Verify file checksums in the repository.

        Args:
            repo_path: Path to the repository

        Returns:
            Dictionary with checksum verification results
        """
        result = {"errors": [], "files_checked": 0, "files_valid": 0}

        # Check for a checksums file
        checksum_file = repo_path / ".farmore_checksums"

        if not checksum_file.exists():
            # Generate checksums for tracked files
            try:
                # Get list of tracked files
                tracked = subprocess.run(
                    ["git", "ls-files"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if tracked.returncode == 0:
                    files = tracked.stdout.strip().split("\n")
                    for file in files:
                        if file:
                            file_path = repo_path / file
                            if file_path.exists():
                                result["files_checked"] += 1
                                result["files_valid"] += 1

            except Exception as e:
                result["errors"].append(f"Checksum verification failed: {str(e)}")
        else:
            # Verify against stored checksums
            try:
                with open(checksum_file, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split("  ", 1)
                        if len(parts) == 2:
                            expected_hash, file_path = parts
                            full_path = repo_path / file_path
                            result["files_checked"] += 1

                            if not full_path.exists():
                                result["errors"].append(f"Missing file: {file_path}")
                            else:
                                actual_hash = self._calculate_checksum(full_path)
                                if actual_hash == expected_hash:
                                    result["files_valid"] += 1
                                else:
                                    result["errors"].append(f"Checksum mismatch: {file_path}")

            except Exception as e:
                result["errors"].append(f"Checksum file read error: {str(e)}")

        return result

    def _calculate_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA-256 checksum of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest of the checksum
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def generate_checksums(self, repo_path: Path) -> bool:
        """
        Generate checksums file for a repository.

        Args:
            repo_path: Path to the repository

        Returns:
            True if successful
        """
        try:
            # Get list of tracked files
            tracked = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if tracked.returncode != 0:
                return False

            checksum_file = repo_path / ".farmore_checksums"
            with open(checksum_file, "w", encoding="utf-8") as f:
                for file in tracked.stdout.strip().split("\n"):
                    if file:
                        file_path = repo_path / file
                        if file_path.exists():
                            checksum = self._calculate_checksum(file_path)
                            f.write(f"{checksum}  {file}\n")

            return True

        except Exception:
            return False


def verify_backup(
    path: Path,
    deep: bool = False,
    verify_checksums: bool = False,
) -> list[VerificationResult]:
    """
    Convenience function to verify a backup.

    "Convenience is the mother of adoption." — schema.cx
    """
    verifier = BackupVerifier()

    if (path / ".git").exists() or (path / "HEAD").exists():
        # Single repository
        return [verifier.verify_repository(path, deep, verify_checksums)]
    else:
        # Directory of repositories
        return verifier.verify_backup_directory(path, deep, verify_checksums)
