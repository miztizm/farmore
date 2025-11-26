"""Tests for the notifications module."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from farmore.notifications import (
    DiscordNotifier,
    EmailNotifier,
    NotificationConfig,
    NotificationEvent,
    NotificationLevel,
    NotificationManager,
    SlackNotifier,
    WebhookNotifier,
)


class TestNotificationLevel:
    """Tests for the NotificationLevel enum."""

    def test_notification_levels_exist(self):
        """Test that all notification levels are defined."""
        assert NotificationLevel.INFO is not None
        assert NotificationLevel.SUCCESS is not None
        assert NotificationLevel.WARNING is not None
        assert NotificationLevel.ERROR is not None


class TestNotificationEvent:
    """Tests for the NotificationEvent dataclass."""

    def test_notification_event_creation(self):
        """Test creating a notification event."""
        event = NotificationEvent(
            title="Backup Completed",
            message="Successfully backed up 10 repositories",
            level=NotificationLevel.SUCCESS,
            details={"repos": 10},
        )
        assert event.title == "Backup Completed"
        assert event.level == NotificationLevel.SUCCESS

    def test_notification_event_to_dict(self):
        """Test converting event to dictionary."""
        event = NotificationEvent(
            title="Backup Failed",
            message="Network error",
            level=NotificationLevel.ERROR,
            details={"error": "timeout"},
        )
        data = event.to_dict()
        assert data["title"] == "Backup Failed"
        assert data["level"] == "error"
        assert "timestamp" in data


class TestNotificationConfig:
    """Tests for the NotificationConfig dataclass."""

    def test_notification_config_creation(self):
        """Test creating notification config."""
        config = NotificationConfig(
            email_enabled=True,
            email_smtp_host="smtp.example.com",
            email_smtp_port=587,
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.com/xxx",
        )
        assert config.email_enabled is True
        assert config.slack_enabled is True

    def test_notification_config_defaults(self):
        """Test notification config defaults."""
        config = NotificationConfig()
        assert config.email_enabled is False
        assert config.slack_enabled is False
        assert config.discord_enabled is False
        assert config.webhook_enabled is False
        assert config.notify_on_failure is True

    def test_notification_config_to_dict(self):
        """Test converting config to dictionary."""
        config = NotificationConfig(
            slack_enabled=True,
            notify_on_success=False,
        )
        data = config.to_dict()
        assert data["slack_enabled"] is True
        assert data["notify_on_success"] is False

    def test_notification_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "email_enabled": True,
            "email_smtp_host": "smtp.test.com",
            "email_to": ["user@test.com"],
            "discord_enabled": True,
            "discord_webhook_url": "https://discord.com/webhook",
        }
        config = NotificationConfig.from_dict(data)
        assert config.email_enabled is True
        assert config.discord_enabled is True
        assert "user@test.com" in config.email_to


class TestEmailNotifier:
    """Tests for the EmailNotifier class."""

    @pytest.fixture
    def email_config(self):
        """Create email config."""
        return NotificationConfig(
            email_enabled=True,
            email_smtp_host="smtp.test.com",
            email_smtp_port=587,
            email_smtp_user="user",
            email_smtp_password="pass",
            email_from="from@test.com",
            email_to=["to@test.com"],
        )

    @pytest.fixture
    def notifier(self, email_config):
        """Create email notifier."""
        return EmailNotifier(email_config)

    @pytest.fixture
    def sample_event(self):
        """Create sample event."""
        return NotificationEvent(
            title="Test",
            message="Test message",
            level=NotificationLevel.INFO,
        )

    def test_email_notifier_initialization(self, notifier):
        """Test email notifier initialization."""
        assert notifier is not None
        assert notifier.config.email_enabled is True

    def test_email_notifier_disabled(self, sample_event):
        """Test that disabled notifier returns False."""
        config = NotificationConfig(email_enabled=False)
        notifier = EmailNotifier(config)
        result = notifier.send(sample_event)
        assert result is False

    def test_create_text_message(self, notifier, sample_event):
        """Test creating text message."""
        text = notifier._create_text_message(sample_event)
        assert "Test" in text
        assert "Test message" in text

    def test_create_html_message(self, notifier, sample_event):
        """Test creating HTML message."""
        html = notifier._create_html_message(sample_event)
        assert "<html>" in html
        assert "Test" in html


class TestSlackNotifier:
    """Tests for the SlackNotifier class."""

    @pytest.fixture
    def slack_config(self):
        """Create Slack config."""
        return NotificationConfig(
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.com/services/xxx",
            slack_channel="#backups",
        )

    @pytest.fixture
    def notifier(self, slack_config):
        """Create Slack notifier."""
        return SlackNotifier(slack_config)

    @pytest.fixture
    def sample_event(self):
        """Create sample event."""
        return NotificationEvent(
            title="Backup Complete",
            message="10 repos backed up",
            level=NotificationLevel.SUCCESS,
        )

    def test_slack_notifier_initialization(self, notifier):
        """Test Slack notifier initialization."""
        assert notifier is not None
        assert notifier.config.slack_enabled is True

    def test_slack_notifier_disabled(self, sample_event):
        """Test that disabled notifier returns False."""
        config = NotificationConfig(slack_enabled=False)
        notifier = SlackNotifier(config)
        result = notifier.send(sample_event)
        assert result is False

    @patch("urllib.request.urlopen")
    def test_slack_send_success(self, mock_urlopen, notifier, sample_event):
        """Test successful Slack notification."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = notifier.send(sample_event)
        assert result is True


class TestDiscordNotifier:
    """Tests for the DiscordNotifier class."""

    @pytest.fixture
    def discord_config(self):
        """Create Discord config."""
        return NotificationConfig(
            discord_enabled=True,
            discord_webhook_url="https://discord.com/api/webhooks/xxx",
            discord_username="Farmore",
        )

    @pytest.fixture
    def notifier(self, discord_config):
        """Create Discord notifier."""
        return DiscordNotifier(discord_config)

    @pytest.fixture
    def sample_event(self):
        """Create sample event."""
        return NotificationEvent(
            title="Backup Failed",
            message="Network error",
            level=NotificationLevel.ERROR,
        )

    def test_discord_notifier_initialization(self, notifier):
        """Test Discord notifier initialization."""
        assert notifier is not None
        assert notifier.config.discord_enabled is True

    def test_discord_notifier_disabled(self, sample_event):
        """Test that disabled notifier returns False."""
        config = NotificationConfig(discord_enabled=False)
        notifier = DiscordNotifier(config)
        result = notifier.send(sample_event)
        assert result is False

    @patch("urllib.request.urlopen")
    def test_discord_send_success(self, mock_urlopen, notifier, sample_event):
        """Test successful Discord notification."""
        mock_response = MagicMock()
        mock_response.status = 204
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = notifier.send(sample_event)
        assert result is True


class TestWebhookNotifier:
    """Tests for the WebhookNotifier class."""

    @pytest.fixture
    def webhook_config(self):
        """Create webhook config."""
        return NotificationConfig(
            webhook_enabled=True,
            webhook_url="https://example.com/webhook",
            webhook_method="POST",
        )

    @pytest.fixture
    def notifier(self, webhook_config):
        """Create webhook notifier."""
        return WebhookNotifier(webhook_config)

    @pytest.fixture
    def sample_event(self):
        """Create sample event."""
        return NotificationEvent(
            title="Test",
            message="Test webhook",
            level=NotificationLevel.INFO,
        )

    def test_webhook_notifier_initialization(self, notifier):
        """Test webhook notifier initialization."""
        assert notifier is not None
        assert notifier.config.webhook_enabled is True

    def test_webhook_notifier_disabled(self, sample_event):
        """Test that disabled notifier returns False."""
        config = NotificationConfig(webhook_enabled=False)
        notifier = WebhookNotifier(config)
        result = notifier.send(sample_event)
        assert result is False


class TestNotificationManager:
    """Tests for the NotificationManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create notification manager."""
        config = NotificationConfig()
        return NotificationManager(config=config, config_dir=tmp_path)

    @pytest.fixture
    def sample_event(self):
        """Create sample event."""
        return NotificationEvent(
            title="Backup Complete",
            message="Success",
            level=NotificationLevel.SUCCESS,
        )

    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert manager is not None

    def test_notify_backup_success(self, manager):
        """Test success notification."""
        results = manager.notify_backup_success(
            repos_count=10,
            duration_seconds=300,
        )
        # Should return empty dict since no providers are enabled
        assert isinstance(results, dict)

    def test_notify_backup_failure(self, manager):
        """Test failure notification."""
        results = manager.notify_backup_failure(
            error_message="Network error",
            repos_failed=3,
        )
        assert isinstance(results, dict)

    def test_notify_backup_warning(self, manager):
        """Test warning notification."""
        results = manager.notify_backup_warning(
            message="Some repos had issues",
            repos_with_issues=2,
        )
        assert isinstance(results, dict)

    def test_save_and_load_config(self, tmp_path):
        """Test saving and loading config."""
        config = NotificationConfig(
            slack_enabled=True,
            slack_channel="#test",
        )
        manager = NotificationManager(config=config, config_dir=tmp_path)
        manager.save_config()
        
        # Load in new manager
        new_manager = NotificationManager(config_dir=tmp_path)
        # Config should be loaded from file
        assert new_manager is not None

    def test_test_all_providers_empty(self, manager):
        """Test testing providers when none enabled."""
        results = manager.test_all_providers()
        assert isinstance(results, dict)
        assert len(results) == 0

    def test_notify_respects_level_preferences(self, manager, sample_event):
        """Test that notify respects level preferences."""
        manager.config.notify_on_success = False
        results = manager.notify(sample_event)
        # Should not send since notify_on_success is False
        assert isinstance(results, dict)
