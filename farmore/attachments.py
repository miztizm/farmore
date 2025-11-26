"""
Attachment extraction and download module for Farmore.

"Every picture tells a story. Make sure you back it up." — schema.cx

This module handles downloading attachments (images, files) from GitHub issues
and pull requests. GitHub hosts user-uploaded files on various CDN URLs, and
this module extracts and downloads them for complete issue/PR preservation.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

from .rich_utils import console


# GitHub attachment URL patterns (updated for 2024/2025)
ATTACHMENT_PATTERNS = [
    # New format (2024+): user-attachments assets/files
    r'https://github\.com/user-attachments/assets/[a-f0-9-]+',
    r'https://github\.com/user-attachments/files/\d+/[^\s\)`"<>]+',
    # Private user images
    r'https://private-user-images\.githubusercontent\.com/\d+/[^\s\)`"<>]+',
    # Standard user images
    r'https://user-images\.githubusercontent\.com/\d+/[^\s\)`"<>]+',
    # Legacy camo URLs (proxied images)
    r'https://camo\.githubusercontent\.com/[^\s\)`"<>]+',
    # Repository attachments
    r'https://github\.com/[^/]+/[^/]+/files/\d+/[^\s\)`"<>]+',
    # Issue/PR inline attachments
    r'https://github\.com/[^/]+/[^/]+/assets/\d+/[^\s\)`"<>]+',
]


@dataclass
class Attachment:
    """
    Represents a downloaded attachment.

    "Attachments are just files that got social." — schema.cx
    """

    url: str
    filename: str
    local_path: Path | None = None
    content_type: str | None = None
    size: int = 0
    checksum: str | None = None  # SHA-256 hash
    source_type: str = "unknown"  # "issue", "pull_request", "comment"
    source_number: int | None = None  # Issue/PR number
    success: bool = False
    error: str | None = None


@dataclass
class AttachmentManifest:
    """
    Manifest tracking all downloaded attachments.

    "A manifest is just a to-do list that got done." — schema.cx
    """

    repository: str
    total_urls_found: int = 0
    total_downloaded: int = 0
    total_failed: int = 0
    total_skipped: int = 0  # Already downloaded
    attachments: list[Attachment] = field(default_factory=list)
    created_at: str | None = None
    
    def to_dict(self) -> dict:
        """Convert manifest to dictionary for JSON export."""
        return {
            "repository": self.repository,
            "total_urls_found": self.total_urls_found,
            "total_downloaded": self.total_downloaded,
            "total_failed": self.total_failed,
            "total_skipped": self.total_skipped,
            "created_at": self.created_at,
            "attachments": [
                {
                    "url": a.url,
                    "filename": a.filename,
                    "local_path": str(a.local_path) if a.local_path else None,
                    "content_type": a.content_type,
                    "size": a.size,
                    "checksum": a.checksum,
                    "source_type": a.source_type,
                    "source_number": a.source_number,
                    "success": a.success,
                    "error": a.error,
                }
                for a in self.attachments
            ],
        }


class AttachmentExtractor:
    """
    Extracts attachment URLs from markdown content.

    "Regex: because sometimes you need to find a needle in a haystack
    by describing what the needle might look like." — schema.cx
    """

    def __init__(self) -> None:
        """Initialize the extractor with compiled patterns."""
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in ATTACHMENT_PATTERNS]

    def extract_urls(self, markdown: str) -> list[str]:
        """
        Extract all attachment URLs from markdown content.

        Args:
            markdown: Markdown text containing potential attachment URLs

        Returns:
            List of unique attachment URLs found
        """
        if not markdown:
            return []

        # Remove code blocks to avoid false positives
        text_no_code = self._remove_code_blocks(markdown)

        urls = set()
        for pattern in self.patterns:
            matches = pattern.findall(text_no_code)
            urls.update(matches)

        return list(urls)

    def extract_from_issue(self, issue_data: dict) -> list[tuple[str, str, int]]:
        """
        Extract attachment URLs from an issue and its comments.

        Args:
            issue_data: Issue data dict from GitHub API

        Returns:
            List of tuples: (url, source_type, source_number)
        """
        results = []
        issue_number = issue_data.get("number", 0)

        # Extract from issue body
        body = issue_data.get("body") or ""
        for url in self.extract_urls(body):
            results.append((url, "issue", issue_number))

        # Extract from comments if present
        for comment in issue_data.get("comments", []):
            comment_body = comment.get("body") or ""
            for url in self.extract_urls(comment_body):
                results.append((url, "issue_comment", issue_number))

        return results

    def extract_from_pull_request(self, pr_data: dict) -> list[tuple[str, str, int]]:
        """
        Extract attachment URLs from a pull request and its comments.

        Args:
            pr_data: Pull request data dict from GitHub API

        Returns:
            List of tuples: (url, source_type, source_number)
        """
        results = []
        pr_number = pr_data.get("number", 0)

        # Extract from PR body
        body = pr_data.get("body") or ""
        for url in self.extract_urls(body):
            results.append((url, "pull_request", pr_number))

        # Extract from comments if present
        for comment in pr_data.get("comments", []):
            comment_body = comment.get("body") or ""
            for url in self.extract_urls(comment_body):
                results.append((url, "pr_comment", pr_number))

        return results

    def _remove_code_blocks(self, text: str) -> str:
        """Remove fenced code blocks from text."""
        # Remove triple-backtick code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # Remove indented code blocks (4 spaces or tab)
        text = re.sub(r'^(    |\t).+$', '', text, flags=re.MULTILINE)
        return text


class AttachmentDownloader:
    """
    Downloads and manages attachment files.

    "Download today what you might lose tomorrow." — schema.cx
    """

    def __init__(
        self,
        token: str | None = None,
        dest: Path | None = None,
        timeout: int = 60,
    ) -> None:
        """
        Initialize the downloader.

        Args:
            token: GitHub personal access token (for private repos)
            dest: Base destination directory for attachments
            timeout: Request timeout in seconds
        """
        self.session = requests.Session()
        self.dest = dest or Path("attachments")
        self.timeout = timeout

        # Set up headers
        headers = {
            "User-Agent": "Farmore/0.6.0 (https://github.com/miztizm/farmore)",
        }
        if token:
            headers["Authorization"] = f"token {token}"

        self.session.headers.update(headers)
        self.extractor = AttachmentExtractor()

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()

    def __enter__(self) -> "AttachmentDownloader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def download_from_issues(
        self,
        owner: str,
        repo: str,
        issues: list[dict],
        skip_existing: bool = True,
    ) -> AttachmentManifest:
        """
        Download all attachments from a list of issues.

        Args:
            owner: Repository owner
            repo: Repository name
            issues: List of issue data dicts
            skip_existing: Skip files that already exist

        Returns:
            AttachmentManifest with download results
        """
        from datetime import datetime

        manifest = AttachmentManifest(
            repository=f"{owner}/{repo}",
            created_at=datetime.utcnow().isoformat(),
        )

        # Create destination directory
        attachments_dir = self.dest / owner / repo / "attachments" / "issues"
        attachments_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"\n[cyan]📎 Extracting attachments from {len(issues)} issues...[/cyan]")

        # Extract all URLs
        all_urls = []
        for issue in issues:
            urls = self.extractor.extract_from_issue(issue)
            all_urls.extend(urls)

        manifest.total_urls_found = len(all_urls)
        console.print(f"   [dim]Found {len(all_urls)} attachment URLs[/dim]")

        if not all_urls:
            return manifest

        # Download each attachment
        seen_urls = set()
        for url, source_type, source_number in all_urls:
            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)

            attachment = self._download_attachment(
                url=url,
                dest_dir=attachments_dir,
                source_type=source_type,
                source_number=source_number,
                skip_existing=skip_existing,
            )

            manifest.attachments.append(attachment)

            if attachment.success:
                if attachment.error == "skipped":
                    manifest.total_skipped += 1
                else:
                    manifest.total_downloaded += 1
            else:
                manifest.total_failed += 1

        # Save manifest
        manifest_path = attachments_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        return manifest

    def download_from_pull_requests(
        self,
        owner: str,
        repo: str,
        pull_requests: list[dict],
        skip_existing: bool = True,
    ) -> AttachmentManifest:
        """
        Download all attachments from a list of pull requests.

        Args:
            owner: Repository owner
            repo: Repository name
            pull_requests: List of PR data dicts
            skip_existing: Skip files that already exist

        Returns:
            AttachmentManifest with download results
        """
        from datetime import datetime

        manifest = AttachmentManifest(
            repository=f"{owner}/{repo}",
            created_at=datetime.utcnow().isoformat(),
        )

        # Create destination directory
        attachments_dir = self.dest / owner / repo / "attachments" / "pulls"
        attachments_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"\n[cyan]📎 Extracting attachments from {len(pull_requests)} pull requests...[/cyan]")

        # Extract all URLs
        all_urls = []
        for pr in pull_requests:
            urls = self.extractor.extract_from_pull_request(pr)
            all_urls.extend(urls)

        manifest.total_urls_found = len(all_urls)
        console.print(f"   [dim]Found {len(all_urls)} attachment URLs[/dim]")

        if not all_urls:
            return manifest

        # Download each attachment
        seen_urls = set()
        for url, source_type, source_number in all_urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)

            attachment = self._download_attachment(
                url=url,
                dest_dir=attachments_dir,
                source_type=source_type,
                source_number=source_number,
                skip_existing=skip_existing,
            )

            manifest.attachments.append(attachment)

            if attachment.success:
                if attachment.error == "skipped":
                    manifest.total_skipped += 1
                else:
                    manifest.total_downloaded += 1
            else:
                manifest.total_failed += 1

        # Save manifest
        manifest_path = attachments_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        return manifest

    def _download_attachment(
        self,
        url: str,
        dest_dir: Path,
        source_type: str,
        source_number: int,
        skip_existing: bool = True,
    ) -> Attachment:
        """
        Download a single attachment.

        Args:
            url: URL of the attachment
            dest_dir: Destination directory
            source_type: Type of source (issue, pull_request, etc.)
            source_number: Issue/PR number
            skip_existing: Skip if file already exists

        Returns:
            Attachment object with download result
        """
        attachment = Attachment(
            url=url,
            filename=self._extract_filename(url),
            source_type=source_type,
            source_number=source_number,
        )

        try:
            # Generate safe filename
            safe_filename = self._generate_safe_filename(url, dest_dir)
            dest_path = dest_dir / safe_filename

            # Check if file exists
            if skip_existing and dest_path.exists():
                attachment.local_path = dest_path
                attachment.success = True
                attachment.error = "skipped"
                console.print(f"   [dim]⏭️  Skipped: {safe_filename}[/dim]")
                return attachment

            # Download the file
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()

            # Get content type and size
            attachment.content_type = response.headers.get("Content-Type")
            attachment.size = int(response.headers.get("Content-Length", 0))

            # Write file and compute checksum
            hasher = hashlib.sha256()
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    hasher.update(chunk)

            attachment.local_path = dest_path
            attachment.filename = safe_filename
            attachment.checksum = hasher.hexdigest()
            attachment.success = True

            console.print(f"   [green]✓ Downloaded: {safe_filename} ({attachment.size} bytes)[/green]")

        except requests.exceptions.RequestException as e:
            attachment.success = False
            attachment.error = str(e)
            console.print(f"   [red]❌ Failed: {attachment.filename} - {e}[/red]")

        except Exception as e:
            attachment.success = False
            attachment.error = str(e)
            console.print(f"   [red]❌ Error: {attachment.filename} - {e}[/red]")

        return attachment

    def _extract_filename(self, url: str) -> str:
        """Extract a filename from a URL."""
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Get the last path component
        filename = path.split("/")[-1]

        # Remove query parameters from filename
        if "?" in filename:
            filename = filename.split("?")[0]

        # If empty or too short, generate from URL hash
        if not filename or len(filename) < 3:
            filename = hashlib.sha256(url.encode()).hexdigest()[:16]

        return filename

    def _generate_safe_filename(self, url: str, dest_dir: Path) -> str:
        """
        Generate a safe, unique filename for the attachment.

        Handles collisions by appending checksum if file exists.
        """
        base_filename = self._extract_filename(url)

        # Sanitize filename
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_")
        sanitized = "".join(c if c in safe_chars else "_" for c in base_filename)

        # Limit length
        if len(sanitized) > 200:
            name, ext = self._split_filename(sanitized)
            sanitized = name[:150] + ext

        # Handle collisions
        dest_path = dest_dir / sanitized
        if dest_path.exists():
            # Add URL hash to make unique
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
            name, ext = self._split_filename(sanitized)
            sanitized = f"{name}_{url_hash}{ext}"

        return sanitized

    def _split_filename(self, filename: str) -> tuple[str, str]:
        """Split filename into name and extension."""
        if "." in filename:
            parts = filename.rsplit(".", 1)
            return parts[0], "." + parts[1]
        return filename, ""
