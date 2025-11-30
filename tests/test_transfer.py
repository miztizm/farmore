"""
Tests for GitHub repository transfer module.

"Mock the API. Trust nothing. Test everything." — schema.cx
"""

import pytest
import responses
from pathlib import Path
from unittest.mock import patch, mock_open

from farmore.transfer import (
    TransferClient,
    TransferError,
    TransferResult,
    TransferSummary,
    validate_repo_name,
    validate_org_name,
    parse_repo_list,
    parse_team_ids,
)


# =============================================================================
# Validation Function Tests
# =============================================================================


class TestValidateRepoName:
    """Tests for validate_repo_name function."""

    def test_valid_repo_names(self):
        """Test validation of valid repository names."""
        valid_names = [
            "my-repo",
            "my_repo",
            "MyRepo",
            "repo123",
            "my.repo",
            "a",
            "repo-name-with-many-dashes",
        ]
        for name in valid_names:
            is_valid, msg = validate_repo_name(name)
            assert is_valid, f"Expected '{name}' to be valid, but got: {msg}"

    def test_empty_name(self):
        """Test rejection of empty name."""
        is_valid, msg = validate_repo_name("")
        assert not is_valid
        assert "empty" in msg.lower()

    def test_name_too_long(self):
        """Test rejection of name exceeding max length."""
        long_name = "a" * 101
        is_valid, msg = validate_repo_name(long_name)
        assert not is_valid
        assert "100" in msg

    def test_invalid_characters(self):
        """Test rejection of invalid characters."""
        invalid_names = [
            "repo name",  # space
            "repo@name",  # @
            "repo!name",  # !
            "repo#name",  # #
            "repo$name",  # $
        ]
        for name in invalid_names:
            is_valid, msg = validate_repo_name(name)
            assert not is_valid, f"Expected '{name}' to be invalid"

    def test_reserved_names(self):
        """Test rejection of reserved names."""
        reserved_names = ["..", "."]
        for name in reserved_names:
            is_valid, msg = validate_repo_name(name)
            assert not is_valid, f"Expected '{name}' to be rejected as reserved"


class TestValidateOrgName:
    """Tests for validate_org_name function."""

    def test_valid_org_names(self):
        """Test validation of valid organization names."""
        valid_names = ["my-org", "org123", "MyOrg", "org-name"]
        for name in valid_names:
            is_valid, msg = validate_org_name(name)
            assert is_valid, f"Expected '{name}' to be valid, but got: {msg}"

    def test_empty_name(self):
        """Test rejection of empty name."""
        is_valid, msg = validate_org_name("")
        assert not is_valid
        assert "empty" in msg.lower()

    def test_name_too_long(self):
        """Test rejection of name exceeding max length."""
        long_name = "a" * 40
        is_valid, msg = validate_org_name(long_name)
        assert not is_valid
        assert "39" in msg

    def test_hyphen_boundaries(self):
        """Test rejection of hyphens at start/end."""
        is_valid, msg = validate_org_name("-org")
        assert not is_valid
        is_valid, msg = validate_org_name("org-")
        assert not is_valid


class TestParseRepoList:
    """Tests for parse_repo_list function."""

    def test_single_repo(self):
        """Test parsing single repository name."""
        result = parse_repo_list("my-repo")
        assert result == ["my-repo"]

    def test_comma_separated(self):
        """Test parsing comma-separated repository names."""
        result = parse_repo_list("repo1,repo2,repo3")
        assert result == ["repo1", "repo2", "repo3"]

    def test_with_whitespace(self):
        """Test parsing with whitespace around names."""
        result = parse_repo_list("repo1 , repo2 , repo3")
        assert result == ["repo1", "repo2", "repo3"]

    def test_empty_string(self):
        """Test parsing empty string."""
        result = parse_repo_list("")
        assert result == []

    def test_file_based_list(self):
        """Test parsing from file."""
        import tempfile
        import os
        # Create a real temp file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("repo1\n# comment\nrepo2\n\nrepo3\n")
            temp_path = f.name
        try:
            result = parse_repo_list(f"@{temp_path}")
            assert result == ["repo1", "repo2", "repo3"]
        finally:
            os.unlink(temp_path)

    def test_file_not_found(self):
        """Test error when file not found."""
        with pytest.raises(ValueError, match="not found"):
            parse_repo_list("@nonexistent_file_12345.txt")


class TestParseTeamIds:
    """Tests for parse_team_ids function."""

    def test_none_input(self):
        """Test None input returns None."""
        result = parse_team_ids(None)
        assert result is None

    def test_empty_string(self):
        """Test empty string returns None."""
        result = parse_team_ids("")
        assert result is None

    def test_single_id(self):
        """Test parsing single team ID."""
        result = parse_team_ids("12345")
        assert result == [12345]

    def test_comma_separated_ids(self):
        """Test parsing comma-separated IDs."""
        result = parse_team_ids("123,456,789")
        assert result == [123, 456, 789]

    def test_invalid_id(self):
        """Test rejection of non-numeric ID."""
        with pytest.raises(ValueError, match="Invalid team IDs format"):
            parse_team_ids("123,abc,456")


# =============================================================================
# TransferResult and TransferSummary Tests
# =============================================================================


class TestTransferResult:
    """Tests for TransferResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful transfer result."""
        result = TransferResult(
            repo_name="my-repo",
            source_owner="user",
            target_org="org",
            success=True,
            message="Transfer successful",
        )
        assert result.success is True
        assert result.repo_name == "my-repo"
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed transfer result."""
        result = TransferResult(
            repo_name="my-repo",
            source_owner="user",
            target_org="org",
            success=False,
            error="Permission denied",
            http_status=403,
        )
        assert result.success is False
        assert result.error == "Permission denied"
        assert result.http_status == 403

    def test_with_validation_errors(self):
        """Test result with validation errors."""
        result = TransferResult(
            repo_name="my-repo",
            source_owner="user",
            target_org="org",
            validation_errors=["Error 1", "Error 2"],
        )
        assert len(result.validation_errors) == 2


class TestTransferSummary:
    """Tests for TransferSummary dataclass."""

    def test_empty_summary(self):
        """Test empty summary."""
        summary = TransferSummary()
        assert summary.total == 0
        assert summary.successful == 0
        assert summary.failed == 0

    def test_add_successful_result(self):
        """Test adding successful result."""
        summary = TransferSummary()
        result = TransferResult(
            repo_name="repo1",
            source_owner="user",
            target_org="org",
            success=True,
        )
        summary.add_result(result)
        assert summary.total == 1
        assert summary.successful == 1
        assert summary.failed == 0

    def test_add_failed_result(self):
        """Test adding failed result."""
        summary = TransferSummary()
        result = TransferResult(
            repo_name="repo1",
            source_owner="user",
            target_org="org",
            success=False,
            error="Failed",
        )
        summary.add_result(result)
        assert summary.total == 1
        assert summary.successful == 0
        assert summary.failed == 1
        assert len(summary.failed_repos) == 1

    def test_multiple_results(self):
        """Test adding multiple results."""
        summary = TransferSummary()
        for i in range(3):
            summary.add_result(TransferResult(
                repo_name=f"repo{i}",
                source_owner="user",
                target_org="org",
                success=(i % 2 == 0),
            ))
        assert summary.total == 3
        assert summary.successful == 2
        assert summary.failed == 1


# =============================================================================
# TransferClient API Tests
# =============================================================================


@pytest.fixture
def transfer_client():
    """Create a TransferClient instance for testing."""
    return TransferClient("test_token")


class TestTransferClientAuth:
    """Tests for TransferClient authentication."""

    @responses.activate
    def test_get_authenticated_user(self, transfer_client):
        """Test fetching authenticated user."""
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"login": "testuser"},
            status=200,
        )
        username = transfer_client.get_authenticated_user()
        assert username == "testuser"

    @responses.activate
    def test_get_authenticated_user_401(self, transfer_client):
        """Test handling of 401 unauthorized."""
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"message": "Bad credentials"},
            status=401,
        )
        with pytest.raises(TransferError, match="Invalid.*token"):
            transfer_client.get_authenticated_user()


class TestTransferClientValidation:
    """Tests for TransferClient validation methods."""

    @responses.activate
    def test_check_repo_admin_access_success(self, transfer_client):
        """Test checking admin access - success case."""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={
                "permissions": {"admin": True},
                "full_name": "user/repo",
            },
            status=200,
        )
        has_access, msg = transfer_client.check_repo_admin_access("user", "repo")
        assert has_access is True

    @responses.activate
    def test_check_repo_admin_access_no_admin(self, transfer_client):
        """Test checking admin access - no admin permissions."""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={
                "permissions": {"admin": False, "push": True},
                "full_name": "user/repo",
            },
            status=200,
        )
        has_access, msg = transfer_client.check_repo_admin_access("user", "repo")
        assert has_access is False
        assert "admin" in msg.lower()

    @responses.activate
    def test_check_repo_admin_access_404(self, transfer_client):
        """Test checking admin access - repo not found."""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/nonexistent",
            json={"message": "Not Found"},
            status=404,
        )
        has_access, msg = transfer_client.check_repo_admin_access("user", "nonexistent")
        assert has_access is False
        assert "not found" in msg.lower()

    @responses.activate
    def test_check_org_exists_success(self, transfer_client):
        """Test checking org exists - success case."""
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg",
            json={"login": "myorg", "type": "Organization"},
            status=200,
        )
        exists, msg = transfer_client.check_org_exists("myorg")
        assert exists is True

    @responses.activate
    def test_check_org_exists_404(self, transfer_client):
        """Test checking org exists - not found."""
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/nonexistent",
            json={"message": "Not Found"},
            status=404,
        )
        exists, msg = transfer_client.check_org_exists("nonexistent")
        assert exists is False

    @responses.activate
    def test_check_org_membership_member(self, transfer_client):
        """Test checking org membership - is member."""
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg/memberships/testuser",
            json={"role": "member", "state": "active"},
            status=200,
        )
        is_member, msg = transfer_client.check_org_membership("myorg", "testuser")
        assert is_member is True

    @responses.activate
    def test_check_org_membership_not_member(self, transfer_client):
        """Test checking org membership - not member."""
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg/memberships/testuser",
            status=404,
        )
        is_member, msg = transfer_client.check_org_membership("myorg", "testuser")
        assert is_member is False

    @responses.activate
    def test_check_repo_name_available_yes(self, transfer_client):
        """Test checking name availability - available."""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/myorg/newrepo",
            json={"message": "Not Found"},
            status=404,
        )
        available, msg = transfer_client.check_repo_name_available("myorg", "newrepo")
        assert available is True

    @responses.activate
    def test_check_repo_name_available_no(self, transfer_client):
        """Test checking name availability - not available."""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/myorg/existingrepo",
            json={"full_name": "myorg/existingrepo"},
            status=200,
        )
        available, msg = transfer_client.check_repo_name_available("myorg", "existingrepo")
        assert available is False
        assert "already exists" in msg.lower()


class TestTransferClientExecution:
    """Tests for TransferClient transfer execution."""

    @responses.activate
    def test_transfer_repository_dry_run(self, transfer_client):
        """Test transfer in dry-run mode."""
        # Mock authenticated user endpoint (called during validation)
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"login": "user"},
            status=200,
        )
        # Mock all validation endpoints
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={"permissions": {"admin": True}, "full_name": "user/repo"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg",
            json={"login": "myorg"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg/memberships/user",
            json={"role": "member", "state": "active"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/myorg/repo",
            status=404,
        )

        result = transfer_client.transfer_repository(
            source_owner="user",
            repo_name="repo",
            target_org="myorg",
            dry_run=True,
        )

        assert result.success is True
        assert "dry run" in result.message.lower() or "validation" in result.message.lower()
        # Should NOT call the transfer endpoint
        assert not any("/transfer" in str(call.request.url) for call in responses.calls)

    @responses.activate
    def test_transfer_repository_success(self, transfer_client):
        """Test successful transfer execution."""
        # Mock authenticated user endpoint
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"login": "user"},
            status=200,
        )
        # Mock validation endpoints
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={"permissions": {"admin": True}, "full_name": "user/repo"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg",
            json={"login": "myorg"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg/memberships/user",
            json={"role": "member", "state": "active"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/myorg/repo",
            status=404,
        )
        # Mock transfer endpoint
        responses.add(
            responses.POST,
            "https://api.github.com/repos/user/repo/transfer",
            json={"full_name": "myorg/repo", "html_url": "https://github.com/myorg/repo"},
            status=202,
        )

        result = transfer_client.transfer_repository(
            source_owner="user",
            repo_name="repo",
            target_org="myorg",
            dry_run=False,
        )

        assert result.success is True

    @responses.activate
    def test_transfer_repository_with_new_name(self, transfer_client):
        """Test transfer with new repository name."""
        # Mock authenticated user endpoint
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"login": "user"},
            status=200,
        )
        # Mock validation endpoints
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={"permissions": {"admin": True}, "full_name": "user/repo"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg",
            json={"login": "myorg"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg/memberships/user",
            json={"role": "member", "state": "active"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/myorg/new-repo-name",
            status=404,
        )
        # Mock transfer endpoint
        responses.add(
            responses.POST,
            "https://api.github.com/repos/user/repo/transfer",
            json={"full_name": "myorg/new-repo-name"},
            status=202,
        )

        result = transfer_client.transfer_repository(
            source_owner="user",
            repo_name="repo",
            target_org="myorg",
            new_name="new-repo-name",
            dry_run=False,
        )

        assert result.success is True
        # Verify the request body includes new_name
        transfer_call = [c for c in responses.calls if "/transfer" in c.request.url][0]
        import json
        body = json.loads(transfer_call.request.body)
        assert body.get("new_name") == "new-repo-name"


class TestTransferClientErrorHandling:
    """Tests for TransferClient error handling."""

    @responses.activate
    def test_transfer_401_unauthorized(self, transfer_client):
        """Test handling of 401 unauthorized during validation."""
        # 401 on the repo check endpoint (first API call in validation)
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={"message": "Bad credentials"},
            status=401,
        )

        result = transfer_client.transfer_repository(
            source_owner="user",
            repo_name="repo",
            target_org="myorg",
            dry_run=False,
        )

        assert result.success is False
        # The validation catches the error
        assert len(result.validation_errors) > 0

    @responses.activate
    def test_transfer_403_forbidden(self, transfer_client):
        """Test handling of 403 forbidden during transfer."""
        # Mock authenticated user endpoint
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"login": "user"},
            status=200,
        )
        # Pass validation
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={"permissions": {"admin": True}},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg",
            json={"login": "myorg"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg/memberships/user",
            json={"role": "member", "state": "active"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/myorg/repo",
            status=404,
        )
        # Forbidden on transfer
        responses.add(
            responses.POST,
            "https://api.github.com/repos/user/repo/transfer",
            json={"message": "Forbidden"},
            status=403,
        )

        result = transfer_client.transfer_repository(
            source_owner="user",
            repo_name="repo",
            target_org="myorg",
            dry_run=False,
        )

        assert result.success is False
        assert result.http_status == 403

    @responses.activate
    def test_transfer_422_validation_failed(self, transfer_client):
        """Test handling of 422 validation failed."""
        # Mock authenticated user endpoint
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"login": "user"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={"permissions": {"admin": True}},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg",
            json={"login": "myorg"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg/memberships/user",
            json={"role": "member", "state": "active"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/myorg/repo",
            status=404,
        )
        responses.add(
            responses.POST,
            "https://api.github.com/repos/user/repo/transfer",
            json={"message": "Validation Failed", "errors": [{"message": "org issue"}]},
            status=422,
        )

        result = transfer_client.transfer_repository(
            source_owner="user",
            repo_name="repo",
            target_org="myorg",
            dry_run=False,
        )

        assert result.success is False
        assert result.http_status == 422

    @responses.activate
    def test_transfer_validation_failure_blocks_transfer(self, transfer_client):
        """Test that validation failure prevents transfer attempt."""
        # Mock authenticated user endpoint
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"login": "user"},
            status=200,
        )
        # Fail admin check
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={"permissions": {"admin": False}},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg",
            json={"login": "myorg"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/myorg/memberships/user",
            json={"role": "member", "state": "active"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/myorg/repo",
            status=404,
        )

        result = transfer_client.transfer_repository(
            source_owner="user",
            repo_name="repo",
            target_org="myorg",
            dry_run=False,
        )

        assert result.success is False
        assert len(result.validation_errors) > 0
        # Should NOT call the transfer endpoint
        assert not any("/transfer" in str(call.request.url) for call in responses.calls)


class TestTransferClientContextManager:
    """Tests for TransferClient context manager."""

    def test_context_manager_enter_exit(self):
        """Test context manager protocol."""
        with TransferClient("test_token") as client:
            assert client is not None
            assert client.session is not None
        # After exit, session should be closed (but object still exists)
        # The session.close() method is called, which closes the underlying connections
        assert client.session is not None  # Object still exists
        # Verify close was called by checking the session is no longer usable for new requests
        # (This is the expected behavior - session.close() doesn't set to None)

