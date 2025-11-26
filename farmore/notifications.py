"""
Farmore Notifications Module - Notify users about backup events.

"The best backup is the one you know happened." — schema.cx
"""

import json
import smtplib
import ssl
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any


class NotificationLevel(str, Enum):
    """Severity level of notification."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class NotificationEvent:
    """Represents a notification event."""
    
    title: str
    message: str
    level: NotificationLevel = NotificationLevel.INFO
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "message": self.message,
            "level": self.level.value,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    
    # Email settings
    email_enabled: bool = False
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_from: str = ""
    email_to: list[str] = field(default_factory=list)
    email_use_tls: bool = True
    
    # Slack settings
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    slack_channel: str = ""
    slack_username: str = "Farmore Bot"
    slack_icon_emoji: str = ":floppy_disk:"
    
    # Discord settings
    discord_enabled: bool = False
    discord_webhook_url: str = ""
    discord_username: str = "Farmore"
    discord_avatar_url: str = ""
    
    # Generic webhook settings
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_method: str = "POST"
    webhook_headers: dict[str, str] = field(default_factory=dict)
    
    # Notification preferences
    notify_on_success: bool = True
    notify_on_failure: bool = True
    notify_on_warning: bool = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            "email_enabled": self.email_enabled,
            "email_smtp_host": self.email_smtp_host,
            "email_smtp_port": self.email_smtp_port,
            "email_from": self.email_from,
            "email_to": self.email_to,
            "slack_enabled": self.slack_enabled,
            "slack_channel": self.slack_channel,
            "discord_enabled": self.discord_enabled,
            "webhook_enabled": self.webhook_enabled,
            "webhook_url": self.webhook_url,
            "notify_on_success": self.notify_on_success,
            "notify_on_failure": self.notify_on_failure,
            "notify_on_warning": self.notify_on_warning,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "NotificationConfig":
        """Create from dictionary."""
        return cls(
            email_enabled=data.get("email_enabled", False),
            email_smtp_host=data.get("email_smtp_host", ""),
            email_smtp_port=data.get("email_smtp_port", 587),
            email_smtp_user=data.get("email_smtp_user", ""),
            email_smtp_password=data.get("email_smtp_password", ""),
            email_from=data.get("email_from", ""),
            email_to=data.get("email_to", []),
            email_use_tls=data.get("email_use_tls", True),
            slack_enabled=data.get("slack_enabled", False),
            slack_webhook_url=data.get("slack_webhook_url", ""),
            slack_channel=data.get("slack_channel", ""),
            slack_username=data.get("slack_username", "Farmore Bot"),
            slack_icon_emoji=data.get("slack_icon_emoji", ":floppy_disk:"),
            discord_enabled=data.get("discord_enabled", False),
            discord_webhook_url=data.get("discord_webhook_url", ""),
            discord_username=data.get("discord_username", "Farmore"),
            discord_avatar_url=data.get("discord_avatar_url", ""),
            webhook_enabled=data.get("webhook_enabled", False),
            webhook_url=data.get("webhook_url", ""),
            webhook_method=data.get("webhook_method", "POST"),
            webhook_headers=data.get("webhook_headers", {}),
            notify_on_success=data.get("notify_on_success", True),
            notify_on_failure=data.get("notify_on_failure", True),
            notify_on_warning=data.get("notify_on_warning", True),
        )


class NotificationProvider(ABC):
    """Base class for notification providers."""
    
    @abstractmethod
    def send(self, event: NotificationEvent) -> bool:
        """Send a notification. Returns True if successful."""
        pass
    
    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test the connection. Returns (success, message)."""
        pass


class EmailNotifier(NotificationProvider):
    """Email notification provider."""
    
    def __init__(self, config: NotificationConfig):
        """Initialize email notifier."""
        self.config = config
    
    def send(self, event: NotificationEvent) -> bool:
        """Send email notification."""
        if not self.config.email_enabled or not self.config.email_to:
            return False
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[Farmore] {event.title}"
            msg["From"] = self.config.email_from
            msg["To"] = ", ".join(self.config.email_to)
            
            # Create plain text version
            text_content = self._create_text_message(event)
            msg.attach(MIMEText(text_content, "plain"))
            
            # Create HTML version
            html_content = self._create_html_message(event)
            msg.attach(MIMEText(html_content, "html"))
            
            # Send email
            if self.config.email_use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port) as server:
                    server.starttls(context=context)
                    if self.config.email_smtp_user and self.config.email_smtp_password:
                        server.login(self.config.email_smtp_user, self.config.email_smtp_password)
                    server.sendmail(
                        self.config.email_from,
                        self.config.email_to,
                        msg.as_string(),
                    )
            else:
                with smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port) as server:
                    if self.config.email_smtp_user and self.config.email_smtp_password:
                        server.login(self.config.email_smtp_user, self.config.email_smtp_password)
                    server.sendmail(
                        self.config.email_from,
                        self.config.email_to,
                        msg.as_string(),
                    )
            
            return True
        
        except Exception:
            return False
    
    def test_connection(self) -> tuple[bool, str]:
        """Test SMTP connection."""
        try:
            if self.config.email_use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port, timeout=10) as server:
                    server.starttls(context=context)
                    if self.config.email_smtp_user and self.config.email_smtp_password:
                        server.login(self.config.email_smtp_user, self.config.email_smtp_password)
            else:
                with smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port, timeout=10) as server:
                    if self.config.email_smtp_user and self.config.email_smtp_password:
                        server.login(self.config.email_smtp_user, self.config.email_smtp_password)
            
            return True, "SMTP connection successful"
        
        except Exception as e:
            return False, f"SMTP connection failed: {e}"
    
    def _create_text_message(self, event: NotificationEvent) -> str:
        """Create plain text message."""
        lines = [
            f"Farmore Backup Notification",
            f"=" * 40,
            "",
            f"Status: {event.level.value.upper()}",
            f"Time: {event.timestamp}",
            "",
            event.message,
        ]
        
        if event.details:
            lines.extend(["", "Details:", "-" * 20])
            for key, value in event.details.items():
                lines.append(f"  {key}: {value}")
        
        return "\n".join(lines)
    
    def _create_html_message(self, event: NotificationEvent) -> str:
        """Create HTML message."""
        level_colors = {
            NotificationLevel.INFO: "#2196F3",
            NotificationLevel.SUCCESS: "#4CAF50",
            NotificationLevel.WARNING: "#FF9800",
            NotificationLevel.ERROR: "#F44336",
        }
        
        color = level_colors.get(event.level, "#2196F3")
        
        details_html = ""
        if event.details:
            details_items = "".join(
                f"<tr><td style='padding: 5px; font-weight: bold;'>{k}:</td><td style='padding: 5px;'>{v}</td></tr>"
                for k, v in event.details.items()
            )
            details_html = f"""
            <h3 style='margin-top: 20px;'>Details</h3>
            <table style='border-collapse: collapse;'>{details_items}</table>
            """
        
        return f"""
        <html>
        <body style='font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 20px;'>
            <div style='max-width: 600px; margin: 0 auto;'>
                <div style='background-color: {color}; color: white; padding: 15px 20px; border-radius: 5px 5px 0 0;'>
                    <h2 style='margin: 0;'>🥔 Farmore Backup</h2>
                </div>
                <div style='background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 5px 5px;'>
                    <h3 style='margin-top: 0; color: {color};'>{event.title}</h3>
                    <p>{event.message}</p>
                    <p style='color: #666; font-size: 12px;'>Time: {event.timestamp}</p>
                    {details_html}
                </div>
            </div>
        </body>
        </html>
        """


class SlackNotifier(NotificationProvider):
    """Slack notification provider."""
    
    def __init__(self, config: NotificationConfig):
        """Initialize Slack notifier."""
        self.config = config
    
    def send(self, event: NotificationEvent) -> bool:
        """Send Slack notification."""
        if not self.config.slack_enabled or not self.config.slack_webhook_url:
            return False
        
        try:
            level_colors = {
                NotificationLevel.INFO: "#2196F3",
                NotificationLevel.SUCCESS: "#4CAF50",
                NotificationLevel.WARNING: "#FF9800",
                NotificationLevel.ERROR: "#F44336",
            }
            
            level_emojis = {
                NotificationLevel.INFO: "ℹ️",
                NotificationLevel.SUCCESS: "✅",
                NotificationLevel.WARNING: "⚠️",
                NotificationLevel.ERROR: "❌",
            }
            
            # Build Slack message
            payload = {
                "username": self.config.slack_username,
                "icon_emoji": self.config.slack_icon_emoji,
                "attachments": [
                    {
                        "color": level_colors.get(event.level, "#2196F3"),
                        "title": f"{level_emojis.get(event.level, '')} {event.title}",
                        "text": event.message,
                        "footer": "Farmore Backup",
                        "ts": datetime.now().timestamp(),
                        "fields": [
                            {"title": k, "value": str(v), "short": True}
                            for k, v in event.details.items()
                        ] if event.details else [],
                    }
                ],
            }
            
            if self.config.slack_channel:
                payload["channel"] = self.config.slack_channel
            
            return self._post_webhook(self.config.slack_webhook_url, payload)
        
        except Exception:
            return False
    
    def test_connection(self) -> tuple[bool, str]:
        """Test Slack webhook."""
        try:
            payload = {
                "username": self.config.slack_username,
                "icon_emoji": self.config.slack_icon_emoji,
                "text": "🧪 Farmore test notification - connection successful!",
            }
            
            if self._post_webhook(self.config.slack_webhook_url, payload):
                return True, "Slack webhook test successful"
            else:
                return False, "Slack webhook test failed"
        
        except Exception as e:
            return False, f"Slack webhook test failed: {e}"
    
    def _post_webhook(self, url: str, payload: dict) -> bool:
        """Post to webhook URL."""
        data = json.dumps(payload).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except urllib.error.HTTPError:
            return False


class DiscordNotifier(NotificationProvider):
    """Discord notification provider."""
    
    def __init__(self, config: NotificationConfig):
        """Initialize Discord notifier."""
        self.config = config
    
    def send(self, event: NotificationEvent) -> bool:
        """Send Discord notification."""
        if not self.config.discord_enabled or not self.config.discord_webhook_url:
            return False
        
        try:
            level_colors = {
                NotificationLevel.INFO: 0x2196F3,
                NotificationLevel.SUCCESS: 0x4CAF50,
                NotificationLevel.WARNING: 0xFF9800,
                NotificationLevel.ERROR: 0xF44336,
            }
            
            # Build Discord embed
            embed = {
                "title": event.title,
                "description": event.message,
                "color": level_colors.get(event.level, 0x2196F3),
                "timestamp": event.timestamp,
                "footer": {"text": "Farmore Backup"},
            }
            
            if event.details:
                embed["fields"] = [
                    {"name": k, "value": str(v), "inline": True}
                    for k, v in event.details.items()
                ]
            
            payload = {
                "username": self.config.discord_username,
                "embeds": [embed],
            }
            
            if self.config.discord_avatar_url:
                payload["avatar_url"] = self.config.discord_avatar_url
            
            return self._post_webhook(self.config.discord_webhook_url, payload)
        
        except Exception:
            return False
    
    def test_connection(self) -> tuple[bool, str]:
        """Test Discord webhook."""
        try:
            payload = {
                "username": self.config.discord_username,
                "content": "🧪 Farmore test notification - connection successful!",
            }
            
            if self.config.discord_avatar_url:
                payload["avatar_url"] = self.config.discord_avatar_url
            
            if self._post_webhook(self.config.discord_webhook_url, payload):
                return True, "Discord webhook test successful"
            else:
                return False, "Discord webhook test failed"
        
        except Exception as e:
            return False, f"Discord webhook test failed: {e}"
    
    def _post_webhook(self, url: str, payload: dict) -> bool:
        """Post to webhook URL."""
        data = json.dumps(payload).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status in (200, 204)
        except urllib.error.HTTPError:
            return False


class WebhookNotifier(NotificationProvider):
    """Generic webhook notification provider."""
    
    def __init__(self, config: NotificationConfig):
        """Initialize webhook notifier."""
        self.config = config
    
    def send(self, event: NotificationEvent) -> bool:
        """Send webhook notification."""
        if not self.config.webhook_enabled or not self.config.webhook_url:
            return False
        
        try:
            payload = event.to_dict()
            data = json.dumps(payload).encode("utf-8")
            
            headers = {"Content-Type": "application/json"}
            headers.update(self.config.webhook_headers)
            
            req = urllib.request.Request(
                self.config.webhook_url,
                data=data,
                headers=headers,
                method=self.config.webhook_method,
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status in (200, 201, 202, 204)
        
        except Exception:
            return False
    
    def test_connection(self) -> tuple[bool, str]:
        """Test webhook."""
        try:
            payload = {
                "type": "test",
                "message": "Farmore test notification",
                "timestamp": datetime.now().isoformat(),
            }
            
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            headers.update(self.config.webhook_headers)
            
            req = urllib.request.Request(
                self.config.webhook_url,
                data=data,
                headers=headers,
                method=self.config.webhook_method,
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in (200, 201, 202, 204):
                    return True, "Webhook test successful"
                else:
                    return False, f"Webhook returned status {response.status}"
        
        except Exception as e:
            return False, f"Webhook test failed: {e}"


class NotificationManager:
    """
    Manages notifications across multiple providers.
    
    "Never miss a backup event. Or a failure." — schema.cx
    """
    
    CONFIG_FILE = ".farmore_notifications.json"
    
    def __init__(self, config: NotificationConfig | None = None, config_dir: Path | None = None):
        """Initialize notification manager."""
        self.config_dir = config_dir or Path.home() / ".config" / "farmore"
        self.config = config or self._load_config()
        
        self.providers: list[NotificationProvider] = []
        self._setup_providers()
    
    def _load_config(self) -> NotificationConfig:
        """Load configuration from file."""
        config_path = self.config_dir / self.CONFIG_FILE
        
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                return NotificationConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        
        return NotificationConfig()
    
    def save_config(self) -> None:
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.config_dir / self.CONFIG_FILE
        
        # Note: This saves all settings including sensitive ones
        # In production, consider encrypting or using a secrets manager
        data = {
            "email_enabled": self.config.email_enabled,
            "email_smtp_host": self.config.email_smtp_host,
            "email_smtp_port": self.config.email_smtp_port,
            "email_smtp_user": self.config.email_smtp_user,
            # Password should be stored securely, not in plain JSON
            "email_from": self.config.email_from,
            "email_to": self.config.email_to,
            "email_use_tls": self.config.email_use_tls,
            "slack_enabled": self.config.slack_enabled,
            # Webhook URL should be stored securely
            "slack_channel": self.config.slack_channel,
            "slack_username": self.config.slack_username,
            "slack_icon_emoji": self.config.slack_icon_emoji,
            "discord_enabled": self.config.discord_enabled,
            "discord_username": self.config.discord_username,
            "discord_avatar_url": self.config.discord_avatar_url,
            "webhook_enabled": self.config.webhook_enabled,
            "webhook_method": self.config.webhook_method,
            "notify_on_success": self.config.notify_on_success,
            "notify_on_failure": self.config.notify_on_failure,
            "notify_on_warning": self.config.notify_on_warning,
        }
        
        config_path.write_text(json.dumps(data, indent=2))
    
    def _setup_providers(self) -> None:
        """Set up notification providers based on config."""
        self.providers = []
        
        if self.config.email_enabled:
            self.providers.append(EmailNotifier(self.config))
        
        if self.config.slack_enabled:
            self.providers.append(SlackNotifier(self.config))
        
        if self.config.discord_enabled:
            self.providers.append(DiscordNotifier(self.config))
        
        if self.config.webhook_enabled:
            self.providers.append(WebhookNotifier(self.config))
    
    def notify(self, event: NotificationEvent) -> dict[str, bool]:
        """Send notification to all configured providers."""
        # Check if we should notify for this level
        should_notify = (
            (event.level == NotificationLevel.SUCCESS and self.config.notify_on_success) or
            (event.level == NotificationLevel.ERROR and self.config.notify_on_failure) or
            (event.level == NotificationLevel.WARNING and self.config.notify_on_warning) or
            event.level == NotificationLevel.INFO
        )
        
        if not should_notify:
            return {}
        
        results = {}
        for provider in self.providers:
            provider_name = type(provider).__name__
            try:
                results[provider_name] = provider.send(event)
            except Exception:
                results[provider_name] = False
        
        return results
    
    def notify_backup_success(
        self,
        repos_count: int,
        duration_seconds: float,
        details: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Send success notification for a backup."""
        event = NotificationEvent(
            title="Backup Completed Successfully",
            message=f"Backed up {repos_count} repositories in {duration_seconds:.1f} seconds",
            level=NotificationLevel.SUCCESS,
            details=details or {
                "repositories": repos_count,
                "duration": f"{duration_seconds:.1f}s",
            },
        )
        return self.notify(event)
    
    def notify_backup_failure(
        self,
        error_message: str,
        repos_failed: int = 0,
        details: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Send failure notification for a backup."""
        event = NotificationEvent(
            title="Backup Failed",
            message=error_message,
            level=NotificationLevel.ERROR,
            details=details or {
                "failed_repositories": repos_failed,
                "error": error_message,
            },
        )
        return self.notify(event)
    
    def notify_backup_warning(
        self,
        message: str,
        repos_with_issues: int = 0,
        details: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Send warning notification for a backup."""
        event = NotificationEvent(
            title="Backup Completed with Warnings",
            message=message,
            level=NotificationLevel.WARNING,
            details=details or {
                "repositories_with_issues": repos_with_issues,
            },
        )
        return self.notify(event)
    
    def test_all_providers(self) -> dict[str, tuple[bool, str]]:
        """Test all configured providers."""
        results = {}
        for provider in self.providers:
            provider_name = type(provider).__name__
            results[provider_name] = provider.test_connection()
        return results
