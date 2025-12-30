"""
Alerting and Notification Module
Provides alert management and notification delivery
"""

import json
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
from enum import Enum

from .utils import get_logger, MANAGER_DIR

logger = get_logger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertType(Enum):
    """Types of alerts"""
    SSL_EXPIRING = "ssl_expiring"
    SSL_EXPIRED = "ssl_expired"
    NGINX_DOWN = "nginx_down"
    BACKEND_DOWN = "backend_down"
    SECURITY_ISSUE = "security_issue"
    DISK_SPACE = "disk_space"
    HIGH_TRAFFIC = "high_traffic"
    SYSTEM_UPDATE = "system_update"


class Alert:
    """Represents an alert"""
    
    def __init__(self, alert_type: AlertType, level: AlertLevel, title: str, 
                 message: str, details: Dict = None):
        self.alert_type = alert_type
        self.level = level
        self.title = title
        self.message = message
        self.details = details or {}
        self.created_at = datetime.now()
        self.acknowledged = False
    
    def to_dict(self) -> Dict:
        return {
            "type": self.alert_type.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        alert = cls(
            alert_type=AlertType(data["type"]),
            level=AlertLevel(data["level"]),
            title=data["title"],
            message=data["message"],
            details=data.get("details", {})
        )
        alert.created_at = datetime.fromisoformat(data["created_at"])
        alert.acknowledged = data.get("acknowledged", False)
        return alert


class NotificationChannel:
    """Base class for notification channels"""
    
    def send(self, alert: Alert) -> Tuple[bool, str]:
        """Send notification - to be implemented by subclasses"""
        raise NotImplementedError


class EmailNotification(NotificationChannel):
    """Email notification channel"""
    
    def __init__(self, config: Dict):
        self.smtp_host = config.get("smtp_host", "localhost")
        self.smtp_port = config.get("smtp_port", 587)
        self.smtp_user = config.get("smtp_user", "")
        self.smtp_password = config.get("smtp_password", "")
        self.from_email = config.get("from_email", "vps-manager@localhost")
        self.to_emails = config.get("to_emails", [])
        self.use_tls = config.get("use_tls", True)
    
    def send(self, alert: Alert) -> Tuple[bool, str]:
        """Send email notification"""
        if not self.to_emails:
            return False, "No recipient emails configured"
        
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)
            msg["Subject"] = f"[{alert.level.value.upper()}] {alert.title}"
            
            body = f"""
VPS Manager Alert
================

Level: {alert.level.value.upper()}
Type: {alert.alert_type.value}
Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}

Details:
{json.dumps(alert.details, indent=2)}

---
This is an automated message from VPS Manager
"""
            
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent for alert: {alert.title}")
            return True, "Email sent successfully"
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False, f"Failed to send email: {e}"


class WebhookNotification(NotificationChannel):
    """Webhook notification channel (Slack, Discord, etc.)"""
    
    def __init__(self, config: Dict):
        self.webhook_url = config.get("webhook_url", "")
        self.webhook_type = config.get("type", "generic")  # slack, discord, generic
    
    def send(self, alert: Alert) -> Tuple[bool, str]:
        """Send webhook notification"""
        if not self.webhook_url:
            return False, "No webhook URL configured"
        
        try:
            import urllib.request
            import urllib.parse
            
            if self.webhook_type == "slack":
                payload = self._format_slack(alert)
            elif self.webhook_type == "discord":
                payload = self._format_discord(alert)
            else:
                payload = self._format_generic(alert)
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200, 201, 204]:
                    logger.info(f"Webhook notification sent for alert: {alert.title}")
                    return True, "Webhook sent successfully"
                else:
                    return False, f"Webhook returned status {response.status}"
        
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False, f"Failed to send webhook: {e}"
    
    def _format_slack(self, alert: Alert) -> Dict:
        """Format alert for Slack"""
        color_map = {
            AlertLevel.CRITICAL: "danger",
            AlertLevel.WARNING: "warning",
            AlertLevel.INFO: "good"
        }
        
        return {
            "attachments": [{
                "color": color_map.get(alert.level, "good"),
                "title": alert.title,
                "text": alert.message,
                "fields": [
                    {"title": "Level", "value": alert.level.value.upper(), "short": True},
                    {"title": "Type", "value": alert.alert_type.value, "short": True},
                    {"title": "Time", "value": alert.created_at.strftime('%Y-%m-%d %H:%M:%S'), "short": False}
                ],
                "footer": "VPS Manager",
                "ts": int(alert.created_at.timestamp())
            }]
        }
    
    def _format_discord(self, alert: Alert) -> Dict:
        """Format alert for Discord"""
        color_map = {
            AlertLevel.CRITICAL: 0xFF0000,  # Red
            AlertLevel.WARNING: 0xFFA500,   # Orange
            AlertLevel.INFO: 0x00FF00        # Green
        }
        
        return {
            "embeds": [{
                "title": alert.title,
                "description": alert.message,
                "color": color_map.get(alert.level, 0x00FF00),
                "fields": [
                    {"name": "Level", "value": alert.level.value.upper(), "inline": True},
                    {"name": "Type", "value": alert.alert_type.value, "inline": True}
                ],
                "footer": {"text": "VPS Manager"},
                "timestamp": alert.created_at.isoformat()
            }]
        }
    
    def _format_generic(self, alert: Alert) -> Dict:
        """Format alert for generic webhook"""
        return {
            "level": alert.level.value,
            "type": alert.alert_type.value,
            "title": alert.title,
            "message": alert.message,
            "details": alert.details,
            "timestamp": alert.created_at.isoformat()
        }


class CommandNotification(NotificationChannel):
    """Execute a command when alert is triggered"""
    
    def __init__(self, config: Dict):
        self.command = config.get("command", "")
    
    def send(self, alert: Alert) -> Tuple[bool, str]:
        """Execute command"""
        if not self.command:
            return False, "No command configured"
        
        try:
            # Replace placeholders in command
            cmd = self.command.replace("{title}", alert.title)
            cmd = cmd.replace("{message}", alert.message)
            cmd = cmd.replace("{level}", alert.level.value)
            cmd = cmd.replace("{type}", alert.alert_type.value)
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Command executed for alert: {alert.title}")
                return True, "Command executed successfully"
            else:
                return False, f"Command failed: {result.stderr}"
        
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return False, f"Failed to execute command: {e}"


class AlertManager:
    """Manages alerts and notifications"""
    
    def __init__(self, manager):
        self.manager = manager
        self.alerts: List[Alert] = []
        self.notification_channels: List[NotificationChannel] = []
        self.alerts_file = MANAGER_DIR / "alerts.json"
        self.config_file = MANAGER_DIR / "alert_config.json"
        self.load_alerts()
        self.load_notification_config()
    
    def load_alerts(self):
        """Load saved alerts"""
        if self.alerts_file.exists():
            try:
                with open(self.alerts_file, 'r') as f:
                    data = json.load(f)
                    self.alerts = [Alert.from_dict(a) for a in data]
                logger.info(f"Loaded {len(self.alerts)} alerts")
            except Exception as e:
                logger.error(f"Failed to load alerts: {e}")
                self.alerts = []
    
    def save_alerts(self):
        """Save alerts to file"""
        try:
            with open(self.alerts_file, 'w') as f:
                json.dump([a.to_dict() for a in self.alerts], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alerts: {e}")
    
    def load_notification_config(self):
        """Load notification configuration"""
        if not self.config_file.exists():
            # Create default config
            default_config = {
                "email": {
                    "enabled": False,
                    "smtp_host": "localhost",
                    "smtp_port": 587,
                    "smtp_user": "",
                    "smtp_password": "",
                    "from_email": "vps-manager@localhost",
                    "to_emails": [],
                    "use_tls": True
                },
                "webhook": {
                    "enabled": False,
                    "type": "slack",
                    "webhook_url": ""
                },
                "command": {
                    "enabled": False,
                    "command": ""
                }
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            self.notification_channels = []
            
            if config.get("email", {}).get("enabled", False):
                self.notification_channels.append(EmailNotification(config["email"]))
            
            if config.get("webhook", {}).get("enabled", False):
                self.notification_channels.append(WebhookNotification(config["webhook"]))
            
            if config.get("command", {}).get("enabled", False):
                self.notification_channels.append(CommandNotification(config["command"]))
            
            logger.info(f"Loaded {len(self.notification_channels)} notification channels")
        
        except Exception as e:
            logger.error(f"Failed to load notification config: {e}")
    
    def create_alert(self, alert_type: AlertType, level: AlertLevel, title: str,
                    message: str, details: Dict = None) -> Alert:
        """Create and send a new alert"""
        alert = Alert(alert_type, level, title, message, details)
        self.alerts.append(alert)
        self.save_alerts()
        
        # Send notifications
        for channel in self.notification_channels:
            try:
                success, msg = channel.send(alert)
                if not success:
                    logger.warning(f"Notification failed: {msg}")
            except Exception as e:
                logger.error(f"Notification error: {e}")
        
        logger.info(f"Alert created: {title}")
        return alert
    
    def acknowledge_alert(self, alert: Alert):
        """Mark alert as acknowledged"""
        alert.acknowledged = True
        self.save_alerts()
    
    def get_unacknowledged_alerts(self) -> List[Alert]:
        """Get all unacknowledged alerts"""
        return [a for a in self.alerts if not a.acknowledged]
    
    def get_alerts_by_level(self, level: AlertLevel) -> List[Alert]:
        """Get alerts by severity level"""
        return [a for a in self.alerts if a.level == level]
    
    def clear_old_alerts(self, days: int = 30):
        """Remove alerts older than specified days"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        self.alerts = [a for a in self.alerts if a.created_at > cutoff]
        self.save_alerts()
        logger.info(f"Cleared alerts older than {days} days")
    
    def check_ssl_expiration(self):
        """Check SSL certificates and create alerts if expiring"""
        from pathlib import Path
        from datetime import datetime, timedelta
        
        for domain in self.manager.domains:
            if domain.ssl:
                cert_path = Path(f"/etc/letsencrypt/live/{domain.name}/cert.pem")
                if cert_path.exists():
                    success, output = self.manager.run_command(
                        f"openssl x509 -enddate -noout -in {cert_path}"
                    )
                    
                    if success and "notAfter=" in output:
                        date_str = output.split("notAfter=")[1].strip()
                        try:
                            exp_date = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                            days_until_exp = (exp_date - datetime.now()).days
                            
                            if days_until_exp < 0:
                                self.create_alert(
                                    AlertType.SSL_EXPIRED,
                                    AlertLevel.CRITICAL,
                                    f"SSL Certificate Expired: {domain.name}",
                                    f"Certificate expired {abs(days_until_exp)} days ago",
                                    {"domain": domain.name, "days": days_until_exp}
                                )
                            elif days_until_exp < 7:
                                self.create_alert(
                                    AlertType.SSL_EXPIRING,
                                    AlertLevel.WARNING,
                                    f"SSL Certificate Expiring: {domain.name}",
                                    f"Certificate expires in {days_until_exp} days",
                                    {"domain": domain.name, "days": days_until_exp}
                                )
                        except Exception as e:
                            logger.error(f"Failed to parse certificate date: {e}")
    
    def check_nginx_status(self):
        """Check NGINX status and alert if down"""
        is_active, status = self.manager.get_nginx_status()
        if not is_active:
            self.create_alert(
                AlertType.NGINX_DOWN,
                AlertLevel.CRITICAL,
                "NGINX Service Down",
                f"NGINX service is not running: {status}",
                {"status": status}
            )
    
    def check_disk_space(self):
        """Check disk space and alert if low"""
        success, output = self.manager.run_command("df -h / | tail -1 | awk '{print $5}' | sed 's/%//'")
        
        if success and output.strip().isdigit():
            usage = int(output.strip())
            
            if usage >= 90:
                self.create_alert(
                    AlertType.DISK_SPACE,
                    AlertLevel.CRITICAL,
                    "Disk Space Critical",
                    f"Disk usage is at {usage}%",
                    {"usage": usage}
                )
            elif usage >= 80:
                self.create_alert(
                    AlertType.DISK_SPACE,
                    AlertLevel.WARNING,
                    "Disk Space Warning",
                    f"Disk usage is at {usage}%",
                    {"usage": usage}
                )
    
    def run_all_checks(self):
        """Run all monitoring checks"""
        self.check_ssl_expiration()
        self.check_nginx_status()
        self.check_disk_space()
