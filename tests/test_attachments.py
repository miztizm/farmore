"""
Tests for the attachments module.

"Attachments are the files we forget to backup. Tests help us remember." — schema.cx
"""

import pytest
from pathlib import Path
import tempfile

from farmore.attachments import (
    Attachment,
    AttachmentManifest,
    AttachmentExtractor,
    ATTACHMENT_PATTERNS,
)


class TestAttachment:
    """Test Attachment dataclass."""

    def test_attachment_creation(self):
        """Test creating an Attachment instance."""
        attachment = Attachment(
            url="https://github.com/user-attachments/assets/abc123",
            filename="image.png",
            source_type="issue",
            source_number=42,
        )
        
        assert attachment.url == "https://github.com/user-attachments/assets/abc123"
        assert attachment.filename == "image.png"
        assert attachment.source_type == "issue"
        assert attachment.source_number == 42
        assert attachment.size == 0
        assert attachment.content_type is None

    def test_attachment_with_all_fields(self):
        """Test Attachment with all fields populated."""
        attachment = Attachment(
            url="https://example.com/file.pdf",
            filename="file.pdf",
            local_path=Path("/tmp/file.pdf"),
            content_type="application/pdf",
            size=1024,
            checksum="abc123",
            source_type="pull_request",
            source_number=10,
            success=True,
            error=None,
        )
        
        assert attachment.local_path == Path("/tmp/file.pdf")
        assert attachment.size == 1024
        assert attachment.success is True


class TestAttachmentManifest:
    """Test AttachmentManifest dataclass."""

    def test_manifest_creation(self):
        """Test creating an AttachmentManifest."""
        manifest = AttachmentManifest(
            repository="owner/repo",
            total_urls_found=5,
            total_downloaded=3,
            total_failed=2,
        )
        
        assert manifest.repository == "owner/repo"
        assert manifest.total_urls_found == 5
        assert manifest.total_downloaded == 3
        assert manifest.total_failed == 2

    def test_manifest_to_dict(self):
        """Test converting manifest to dictionary."""
        attachment = Attachment(
            url="https://example.com/img.png",
            filename="img.png",
            source_type="issue",
            source_number=1,
        )
        manifest = AttachmentManifest(
            repository="owner/repo",
            total_urls_found=1,
            total_downloaded=1,
            total_failed=0,
            attachments=[attachment],
        )
        
        data = manifest.to_dict()
        
        assert data["repository"] == "owner/repo"
        assert len(data["attachments"]) == 1
        assert data["attachments"][0]["filename"] == "img.png"


class TestAttachmentExtractor:
    """Test AttachmentExtractor class."""

    def test_extractor_creation(self):
        """Test creating an extractor."""
        extractor = AttachmentExtractor()
        assert extractor is not None
        assert len(extractor.patterns) > 0

    def test_extract_urls_github_assets(self):
        """Test extracting GitHub user-attachments URLs."""
        extractor = AttachmentExtractor()
        
        # Use a valid UUID-style URL that matches the pattern
        markdown = "Here is an image: ![screenshot](https://github.com/user-attachments/assets/12345678-abcd-1234-5678-abcdef123456)"
        
        urls = extractor.extract_urls(markdown)
        
        # Should find the user-attachments URL
        assert len(urls) == 1
        assert "user-attachments/assets" in urls[0]

    def test_extract_urls_githubusercontent(self):
        """Test extracting githubusercontent URLs."""
        extractor = AttachmentExtractor()
        
        # Use a URL that matches the user-images pattern
        markdown = "![image](https://user-images.githubusercontent.com/12345/67890-image.png)"
        
        urls = extractor.extract_urls(markdown)
        
        # Should find the user-images URL
        assert len(urls) == 1
        assert "user-images.githubusercontent.com" in urls[0]

    def test_extract_urls_empty_markdown(self):
        """Test extracting from empty markdown."""
        extractor = AttachmentExtractor()
        
        urls = extractor.extract_urls("")
        
        assert urls == []

    def test_extract_urls_none_markdown(self):
        """Test extracting from None."""
        extractor = AttachmentExtractor()
        
        urls = extractor.extract_urls(None)
        
        assert urls == []

    def test_remove_code_blocks(self):
        """Test removing code blocks from text."""
        extractor = AttachmentExtractor()
        
        text = """
        Some text
        ```
        code block
        ```
        More text
        `inline code`
        Final text
        """
        
        result = extractor._remove_code_blocks(text)
        
        # Code blocks should be removed
        assert "```" not in result or "code block" not in result

    def test_extract_from_issue(self):
        """Test extracting URLs from issue data."""
        extractor = AttachmentExtractor()
        
        issue_data = {
            "number": 42,
            "body": "![image](https://github.com/user-attachments/assets/abc-12345678-1234-1234-1234-123456789012)",
            "comments": [],
        }
        
        results = extractor.extract_from_issue(issue_data)
        
        # Results are (url, source_type, source_number) tuples
        assert isinstance(results, list)

    def test_extract_from_pull_request(self):
        """Test extracting URLs from PR data."""
        extractor = AttachmentExtractor()
        
        pr_data = {
            "number": 10,
            "body": "Before: ![](https://user-images.githubusercontent.com/123/456-before.png)",
            "comments": [],
        }
        
        results = extractor.extract_from_pull_request(pr_data)
        
        # Should extract URLs from PR body
        assert isinstance(results, list)


class TestAttachmentPatterns:
    """Test the attachment URL patterns."""

    def test_patterns_exist(self):
        """Test that patterns are defined."""
        assert len(ATTACHMENT_PATTERNS) > 0

    def test_pattern_types(self):
        """Test that patterns are strings (regex patterns)."""
        for pattern in ATTACHMENT_PATTERNS:
            assert isinstance(pattern, str)
