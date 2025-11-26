"""
Tests for the incremental backup module.

"Incremental backups: why backup everything when you can backup just the changes?" — schema.cx
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from farmore.incremental import BackupState, IncrementalBackupManager


# Module constant for tests
STATE_FILE = IncrementalBackupManager.STATE_FILE


class TestBackupState:
    """Test BackupState dataclass."""

    def test_backup_state_creation(self):
        """Test creating a BackupState with required values."""
        now = datetime.now(timezone.utc).isoformat()
        state = BackupState(last_backup=now)
        
        assert state.last_backup == now
        assert state.version == "0.6.0"
        assert state.repos_backed_up == []
        assert state.repos_updated == {}
        assert state.issues_since == {}
        assert state.pulls_since == {}

    def test_backup_state_with_data(self):
        """Test creating a BackupState with custom data."""
        now = datetime.now(timezone.utc).isoformat()
        state = BackupState(
            last_backup=now,
            version="0.6.0",
            target_type="user",
            target_name="testuser",
            repos_backed_up=["owner/repo"],
            repos_updated={"owner/repo": "2024-01-01T00:00:00Z"},
            issues_since={"owner/repo": "2024-01-01T00:00:00Z"},
            pulls_since={"owner/repo": "2024-01-01T00:00:00Z"},
        )
        
        assert state.target_type == "user"
        assert state.target_name == "testuser"
        assert "owner/repo" in state.repos_backed_up
        assert "owner/repo" in state.repos_updated
        assert "owner/repo" in state.issues_since
        assert "owner/repo" in state.pulls_since

    def test_backup_state_to_dict(self):
        """Test converting BackupState to dictionary."""
        now = datetime.now(timezone.utc).isoformat()
        state = BackupState(
            last_backup=now,
            version="0.6.0",
            repos_updated={"owner/repo": "2024-01-01T00:00:00Z"},
        )
        
        data = state.to_dict()
        
        assert data["version"] == "0.6.0"
        assert data["last_backup"] == now
        assert data["repos_updated"]["owner/repo"] == "2024-01-01T00:00:00Z"

    def test_backup_state_from_dict(self):
        """Test creating BackupState from dictionary."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "version": "0.6.0",
            "last_backup": now,
            "repos_updated": {"owner/repo": "2024-01-01T00:00:00Z"},
            "issues_since": {},
            "pulls_since": {},
        }
        
        state = BackupState.from_dict(data)
        
        assert state.version == "0.6.0"
        assert state.last_backup == now
        assert state.repos_updated["owner/repo"] == "2024-01-01T00:00:00Z"

    def test_backup_state_from_dict_missing_fields(self):
        """Test creating BackupState from dict with missing fields."""
        data = {
            "last_backup": "2024-01-01T00:00:00Z",
        }
        
        state = BackupState.from_dict(data)
        
        assert state.last_backup == "2024-01-01T00:00:00Z"
        assert state.version == "0.6.0"


class TestIncrementalBackupManager:
    """Test IncrementalBackupManager class."""

    def test_manager_creation(self):
        """Test creating an IncrementalBackupManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            manager = IncrementalBackupManager(backup_dir)
            
            assert manager.backup_dir == backup_dir
            assert manager.state_file == backup_dir / STATE_FILE

    def test_load_state_no_file(self):
        """Test loading state when no state file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            manager = IncrementalBackupManager(backup_dir)
            
            state = manager.load_state()
            
            assert state is None

    def test_save_and_load_state(self):
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            manager = IncrementalBackupManager(backup_dir)
            
            now = datetime.now(timezone.utc).isoformat()
            state = BackupState(
                last_backup=now,
                version="0.6.0",
                repos_updated={"owner/repo": "2024-01-01T00:00:00Z"},
            )
            
            manager.save_state(state)
            loaded = manager.load_state()
            
            assert loaded is not None
            assert loaded.version == "0.6.0"
            assert loaded.last_backup == now
            assert loaded.repos_updated["owner/repo"] == "2024-01-01T00:00:00Z"

    def test_get_last_backup_time(self):
        """Test getting last backup time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            manager = IncrementalBackupManager(backup_dir)
            
            # No state file
            assert manager.get_last_backup_time() is None
            
            # With state file
            now = datetime.now(timezone.utc)
            state = BackupState(last_backup=now.isoformat())
            manager.save_state(state)
            
            result = manager.get_last_backup_time()
            assert result is not None
            # Compare dates (ignoring microseconds)
            assert result.date() == now.date()

    def test_should_update_repo(self):
        """Test checking if repo needs update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            manager = IncrementalBackupManager(backup_dir)
            
            # No state - should always update
            assert manager.should_update_repo("owner/repo", "2024-01-15T00:00:00Z") is True
            
            # Save state with older timestamp
            state = BackupState(
                last_backup="2024-01-01T00:00:00Z",
                repos_updated={"owner/repo": "2024-01-01T00:00:00Z"}
            )
            manager.save_state(state)
            
            # Newer update - should update
            assert manager.should_update_repo("owner/repo", "2024-01-15T00:00:00Z") is True
            
            # Same timestamp - should not update
            assert manager.should_update_repo("owner/repo", "2024-01-01T00:00:00Z") is False
            
            # Older timestamp - should not update
            assert manager.should_update_repo("owner/repo", "2023-12-01T00:00:00Z") is False

    def test_get_repo_last_update(self):
        """Test getting repo's last update timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            manager = IncrementalBackupManager(backup_dir)
            
            # No state
            assert manager.get_repo_last_update("owner/repo") is None
            
            # With state
            state = BackupState(
                last_backup="2024-01-01T00:00:00Z",
                repos_updated={"owner/repo": "2024-01-01T00:00:00Z"}
            )
            manager.save_state(state)
            
            result = manager.get_repo_last_update("owner/repo")
            assert result is not None
            assert result.year == 2024
            assert result.month == 1
            assert result.day == 1

    def test_create_new_state(self):
        """Test creating a new state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            manager = IncrementalBackupManager(backup_dir)
            
            state = manager.create_new_state(target_type="user", target_name="testuser")
            
            assert state.target_type == "user"
            assert state.target_name == "testuser"
            assert state.last_backup != ""

    def test_finalize_state(self):
        """Test finalizing backup state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            manager = IncrementalBackupManager(backup_dir)
            
            state = manager.create_new_state(target_type="user", target_name="test")
            manager.finalize_state(state)
            
            # Verify it was saved
            loaded = manager.load_state()
            assert loaded is not None
            assert loaded.target_name == "test"

