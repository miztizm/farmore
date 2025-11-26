"""
Tests for backup scheduling.

"Scheduled tests catch scheduled bugs." — schema.cx
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from farmore.scheduler import BackupScheduler, ScheduledBackup, create_scheduled_backup


class TestScheduledBackup:
    """Tests for ScheduledBackup dataclass."""

    def test_create_scheduled_backup(self) -> None:
        """Test creating a scheduled backup."""
        backup = ScheduledBackup(
            name="test-schedule",
            profile_name="my-profile",
            interval="daily",
        )

        assert backup.name == "test-schedule"
        assert backup.profile_name == "my-profile"
        assert backup.interval == "daily"
        assert backup.enabled is True
        assert backup.last_status == "never_run"

    def test_backup_to_dict(self) -> None:
        """Test converting backup to dictionary."""
        backup = ScheduledBackup(
            name="test",
            profile_name="profile",
            interval="weekly",
            at_time="02:00",
            on_day="monday",
        )

        data = backup.to_dict()

        assert data["name"] == "test"
        assert data["interval"] == "weekly"
        assert data["at_time"] == "02:00"
        assert data["on_day"] == "monday"

    def test_backup_from_dict(self) -> None:
        """Test creating backup from dictionary."""
        data = {
            "name": "imported",
            "profile_name": "my-profile",
            "interval": "hourly",
            "run_count": 5,
        }

        backup = ScheduledBackup.from_dict(data)

        assert backup.name == "imported"
        assert backup.interval == "hourly"
        assert backup.run_count == 5


class TestBackupScheduler:
    """Tests for BackupScheduler class."""

    def test_add_and_get_backup(self) -> None:
        """Test adding and retrieving a scheduled backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            backup = ScheduledBackup(
                name="test-backup",
                profile_name="my-profile",
                interval="daily",
            )

            scheduler.add_backup(backup)
            retrieved = scheduler.get_backup("test-backup")

            assert retrieved is not None
            assert retrieved.name == "test-backup"
            assert retrieved.profile_name == "my-profile"

    def test_get_nonexistent_backup(self) -> None:
        """Test getting a backup that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            result = scheduler.get_backup("nonexistent")

            assert result is None

    def test_remove_backup(self) -> None:
        """Test removing a scheduled backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            backup = ScheduledBackup(
                name="to-remove",
                profile_name="profile",
                interval="hourly",
            )
            scheduler.add_backup(backup)

            # Verify it exists
            assert scheduler.get_backup("to-remove") is not None

            # Remove it
            result = scheduler.remove_backup("to-remove")
            assert result is True

            # Verify it's gone
            assert scheduler.get_backup("to-remove") is None

    def test_remove_nonexistent_backup(self) -> None:
        """Test removing a backup that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            result = scheduler.remove_backup("nonexistent")

            assert result is False

    def test_list_backups(self) -> None:
        """Test listing all scheduled backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            # Initially empty
            assert scheduler.list_backups() == []

            # Add some backups
            for i in range(3):
                backup = ScheduledBackup(
                    name=f"backup-{i}",
                    profile_name=f"profile-{i}",
                    interval="daily",
                )
                scheduler.add_backup(backup)

            backups = scheduler.list_backups()

            assert len(backups) == 3

    def test_enable_disable_backup(self) -> None:
        """Test enabling and disabling a backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            backup = ScheduledBackup(
                name="toggleable",
                profile_name="profile",
                interval="daily",
            )
            scheduler.add_backup(backup)

            # Disable it
            result = scheduler.disable_backup("toggleable")
            assert result is True

            retrieved = scheduler.get_backup("toggleable")
            assert retrieved is not None
            assert retrieved.enabled is False

            # Enable it
            result = scheduler.enable_backup("toggleable")
            assert result is True

            retrieved = scheduler.get_backup("toggleable")
            assert retrieved is not None
            assert retrieved.enabled is True

    def test_enable_nonexistent_backup(self) -> None:
        """Test enabling a backup that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            result = scheduler.enable_backup("nonexistent")

            assert result is False


class TestSchedulerParsing:
    """Tests for interval parsing."""

    @patch("farmore.scheduler.schedule")
    def test_parse_daily_interval(self, mock_schedule: MagicMock) -> None:
        """Test parsing daily interval."""
        mock_job = MagicMock()
        mock_schedule.every.return_value.day = mock_job
        mock_job.at.return_value = mock_job
        mock_job.do.return_value = mock_job

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            backup = ScheduledBackup(
                name="daily-test",
                profile_name="profile",
                interval="daily",
                at_time="02:00",
            )

            result = scheduler._parse_interval(backup)

            # Should have created a job
            assert result is not None

    @patch("farmore.scheduler.schedule")
    def test_parse_hourly_interval(self, mock_schedule: MagicMock) -> None:
        """Test parsing hourly interval."""
        mock_job = MagicMock()
        mock_schedule.every.return_value.hour = mock_job
        mock_job.do.return_value = mock_job

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            backup = ScheduledBackup(
                name="hourly-test",
                profile_name="profile",
                interval="hourly",
            )

            result = scheduler._parse_interval(backup)

            assert result is not None

    @patch("farmore.scheduler.schedule")
    def test_parse_every_x_hours(self, mock_schedule: MagicMock) -> None:
        """Test parsing 'every X hours' interval."""
        mock_job = MagicMock()
        mock_schedule.every.return_value.hours = mock_job
        mock_job.do.return_value = mock_job

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = BackupScheduler(schedule_dir=Path(tmpdir))

            backup = ScheduledBackup(
                name="every-6-hours",
                profile_name="profile",
                interval="every 6 hours",
            )

            result = scheduler._parse_interval(backup)

            mock_schedule.every.assert_called_with(6)


class TestCreateScheduledBackup:
    """Tests for create_scheduled_backup helper function."""

    def test_create_minimal(self) -> None:
        """Test creating a minimal scheduled backup."""
        backup = create_scheduled_backup(
            name="minimal",
            profile_name="my-profile",
        )

        assert backup.name == "minimal"
        assert backup.profile_name == "my-profile"
        assert backup.interval == "daily"

    def test_create_with_options(self) -> None:
        """Test creating a scheduled backup with all options."""
        backup = create_scheduled_backup(
            name="full",
            profile_name="my-profile",
            interval="weekly",
            at_time="03:00",
            on_day="sunday",
        )

        assert backup.interval == "weekly"
        assert backup.at_time == "03:00"
        assert backup.on_day == "sunday"
