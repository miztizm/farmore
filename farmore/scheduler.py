"""
Backup scheduling for Farmore.

"Automation is the art of making the future happen on time." — schema.cx
"""

import json
import signal
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

try:
    import schedule
except ImportError:
    schedule = None  # type: ignore


@dataclass
class ScheduledBackup:
    """
    A scheduled backup configuration.

    "Schedules are promises to your future self." — schema.cx
    """

    name: str
    profile_name: str
    interval: str  # "daily", "weekly", "hourly", "every 6 hours", etc.
    enabled: bool = True

    # Timing
    at_time: str | None = None  # "02:00" for daily/weekly
    on_day: str | None = None  # "monday" for weekly

    # Status
    last_run: str | None = None
    next_run: str | None = None
    run_count: int = 0
    last_status: str = "never_run"
    last_error: str | None = None

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduledBackup":
        """Create from dictionary."""
        return cls(
            name=data.get("name", "unnamed"),
            profile_name=data.get("profile_name", ""),
            interval=data.get("interval", "daily"),
            enabled=data.get("enabled", True),
            at_time=data.get("at_time"),
            on_day=data.get("on_day"),
            last_run=data.get("last_run"),
            next_run=data.get("next_run"),
            run_count=data.get("run_count", 0),
            last_status=data.get("last_status", "never_run"),
            last_error=data.get("last_error"),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


class BackupScheduler:
    """
    Manages scheduled backups.

    "A scheduler is just a very patient assistant." — schema.cx
    """

    DEFAULT_SCHEDULE_DIR = Path.home() / ".config" / "farmore"
    SCHEDULES_FILE = "schedules.json"

    def __init__(
        self,
        schedule_dir: Path | None = None,
        backup_callback: Callable[[str], bool] | None = None,
    ) -> None:
        """
        Initialize the scheduler.

        Args:
            schedule_dir: Directory for schedule storage
            backup_callback: Function to call when running a backup (receives profile name)
        """
        self.schedule_dir = schedule_dir or self.DEFAULT_SCHEDULE_DIR
        self.schedules_path = self.schedule_dir / self.SCHEDULES_FILE
        self.backup_callback = backup_callback
        self._running = False
        self._stop_event = threading.Event()
        self._ensure_schedule_dir()

    def _ensure_schedule_dir(self) -> None:
        """Ensure the schedule directory exists."""
        self.schedule_dir.mkdir(parents=True, exist_ok=True)

    def _load_schedules(self) -> dict[str, dict[str, Any]]:
        """Load all schedules from file."""
        if not self.schedules_path.exists():
            return {}

        try:
            with open(self.schedules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("schedules", {})
        except Exception:
            return {}

    def _save_schedules(self, schedules: dict[str, dict[str, Any]]) -> None:
        """Save all schedules to file."""
        with open(self.schedules_path, "w", encoding="utf-8") as f:
            json.dump({"schedules": schedules}, f, indent=2)

    def add_backup(self, backup: ScheduledBackup) -> None:
        """
        Add a scheduled backup.

        Args:
            backup: The backup schedule to add
        """
        schedules = self._load_schedules()
        schedules[backup.name] = backup.to_dict()
        self._save_schedules(schedules)

    def remove_backup(self, name: str) -> bool:
        """
        Remove a scheduled backup.

        Args:
            name: The backup name

        Returns:
            True if removed, False if not found
        """
        schedules = self._load_schedules()
        if name not in schedules:
            return False
        del schedules[name]
        self._save_schedules(schedules)
        return True

    def get_backup(self, name: str) -> ScheduledBackup | None:
        """
        Get a scheduled backup by name.

        Args:
            name: The backup name

        Returns:
            The backup schedule or None
        """
        schedules = self._load_schedules()
        if name not in schedules:
            return None
        return ScheduledBackup.from_dict(schedules[name])

    def list_backups(self) -> list[ScheduledBackup]:
        """
        List all scheduled backups.

        Returns:
            List of all backup schedules
        """
        schedules = self._load_schedules()
        return [ScheduledBackup.from_dict(data) for data in schedules.values()]

    def enable_backup(self, name: str) -> bool:
        """Enable a scheduled backup."""
        backup = self.get_backup(name)
        if backup is None:
            return False
        backup.enabled = True
        self.add_backup(backup)
        return True

    def disable_backup(self, name: str) -> bool:
        """Disable a scheduled backup."""
        backup = self.get_backup(name)
        if backup is None:
            return False
        backup.enabled = False
        self.add_backup(backup)
        return True

    def _run_backup(self, backup_name: str) -> None:
        """
        Execute a backup.

        Args:
            backup_name: Name of the backup to run
        """
        backup = self.get_backup(backup_name)
        if backup is None or not backup.enabled:
            return

        backup.last_run = datetime.now().isoformat()
        backup.run_count += 1

        try:
            if self.backup_callback:
                success = self.backup_callback(backup.profile_name)
                backup.last_status = "success" if success else "failed"
                backup.last_error = None if success else "Backup callback returned False"
            else:
                backup.last_status = "skipped"
                backup.last_error = "No backup callback configured"
        except Exception as e:
            backup.last_status = "error"
            backup.last_error = str(e)

        self.add_backup(backup)

    def _parse_interval(self, backup: ScheduledBackup) -> Any:
        """
        Parse interval string and create schedule job.

        Args:
            backup: The backup schedule

        Returns:
            Configured schedule job or None
        """
        if schedule is None:
            return None

        interval = backup.interval.lower()

        # Handle "every X hours/minutes" patterns
        if interval.startswith("every"):
            parts = interval.split()
            if len(parts) >= 3:
                try:
                    value = int(parts[1])
                    unit = parts[2].rstrip("s")  # Remove trailing 's'

                    if unit == "hour":
                        job = schedule.every(value).hours
                    elif unit == "minute":
                        job = schedule.every(value).minutes
                    elif unit == "day":
                        job = schedule.every(value).days
                    elif unit == "week":
                        job = schedule.every(value).weeks
                    else:
                        return None

                    return job.do(self._run_backup, backup.name)
                except ValueError:
                    return None

        # Handle simple intervals
        if interval == "hourly":
            job = schedule.every().hour
            return job.do(self._run_backup, backup.name)
        elif interval == "daily":
            job = schedule.every().day
            if backup.at_time:
                job = job.at(backup.at_time)
            return job.do(self._run_backup, backup.name)
        elif interval == "weekly":
            if backup.on_day:
                day = backup.on_day.lower()
                if day == "monday":
                    job = schedule.every().monday
                elif day == "tuesday":
                    job = schedule.every().tuesday
                elif day == "wednesday":
                    job = schedule.every().wednesday
                elif day == "thursday":
                    job = schedule.every().thursday
                elif day == "friday":
                    job = schedule.every().friday
                elif day == "saturday":
                    job = schedule.every().saturday
                elif day == "sunday":
                    job = schedule.every().sunday
                else:
                    job = schedule.every().week
            else:
                job = schedule.every().week

            if backup.at_time:
                job = job.at(backup.at_time)
            return job.do(self._run_backup, backup.name)

        return None

    def run(self, run_once: bool = False) -> None:
        """
        Start the scheduler daemon.

        Args:
            run_once: If True, run pending jobs once and exit
        """
        if schedule is None:
            raise RuntimeError("schedule library not installed. Install with: pip install schedule")

        self._running = True
        self._stop_event.clear()

        # Setup signal handlers
        def signal_handler(signum: int, frame: Any) -> None:
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Clear existing jobs
        schedule.clear()

        # Setup all schedules
        for backup in self.list_backups():
            if backup.enabled:
                self._parse_interval(backup)

        if run_once:
            schedule.run_all()
            return

        # Run scheduler loop
        while self._running and not self._stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)

    def stop(self) -> None:
        """Stop the scheduler daemon."""
        self._running = False
        self._stop_event.set()

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running


def create_scheduled_backup(
    name: str,
    profile_name: str,
    interval: str = "daily",
    at_time: str | None = None,
    on_day: str | None = None,
) -> ScheduledBackup:
    """
    Create a new scheduled backup.

    "Creation is just organization waiting to happen." — schema.cx
    """
    return ScheduledBackup(
        name=name,
        profile_name=profile_name,
        interval=interval,
        at_time=at_time,
        on_day=on_day,
    )
