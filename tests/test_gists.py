"""
Tests for the gists module.

"Gists are code snippets. Tests are verification snippets." — schema.cx
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from farmore.gists import Gist, GistFile, GistsClient


class TestGist:
    """Test Gist dataclass."""

    def test_gist_creation(self):
        """Test creating a Gist instance."""
        gist = Gist(
            id="abc123",
            description="Test gist",
            public=True,
            html_url="https://gist.github.com/abc123",
            git_pull_url="https://gist.github.com/abc123.git",
            git_push_url="https://gist.github.com/abc123.git",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z",
            owner="testuser",
            files=[],
        )
        
        assert gist.id == "abc123"
        assert gist.public is True
        assert gist.owner == "testuser"

    def test_gist_name_property_with_description(self):
        """Test the name property of Gist with description."""
        gist = Gist(
            id="abc123",
            description="My Test Gist",
            public=True,
            html_url="https://gist.github.com/abc123",
            git_pull_url="https://gist.github.com/abc123.git",
            git_push_url="https://gist.github.com/abc123.git",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z",
            owner="testuser",
            files=[],
        )
        # Name should include ID and sanitized description
        assert gist.id in gist.name
        
    def test_gist_name_property_without_description(self):
        """Test the name property of Gist without description."""
        gist = Gist(
            id="abc123",
            description=None,
            public=True,
            html_url="https://gist.github.com/abc123",
            git_pull_url="https://gist.github.com/abc123.git",
            git_push_url="https://gist.github.com/abc123.git",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z",
            owner="testuser",
            files=[],
        )
        # Name should be just the ID
        assert gist.name == "abc123"


class TestGistFile:
    """Test GistFile dataclass."""

    def test_gist_file_creation(self):
        """Test creating a GistFile instance."""
        gist_file = GistFile(
            filename="test.py",
            type="application/x-python",
            language="Python",
            raw_url="https://gist.githubusercontent.com/raw/test.py",
            size=100,
        )
        
        assert gist_file.filename == "test.py"
        assert gist_file.language == "Python"
        assert gist_file.size == 100


class TestGistsClient:
    """Test GistsClient class."""

    def test_client_creation_with_token(self):
        """Test creating client with token."""
        client = GistsClient(token="test_token")
        
        assert "Authorization" in client.session.headers
        client.close()

    def test_client_creation_without_token(self):
        """Test creating client without token."""
        client = GistsClient()
        
        assert "Authorization" not in client.session.headers
        client.close()

    def test_client_context_manager(self):
        """Test client as context manager."""
        with GistsClient(token="test") as client:
            assert client is not None
        # Session should be closed after context

    def test_client_with_github_enterprise(self):
        """Test client with GitHub Enterprise host."""
        client = GistsClient(token="test", github_host="github.example.com")
        
        assert client.base_url == "https://github.example.com/api/v3"
        client.close()

    def test_client_default_base_url(self):
        """Test client default base URL is github.com."""
        client = GistsClient()
        
        assert client.base_url == "https://api.github.com"
        client.close()

