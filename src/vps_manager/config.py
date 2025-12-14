"""
Configuration management for VPS Manager
Handles all configuration storage and first-run setup
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from .utils import MANAGER_DIR

CONFIG_FILE = Path(MANAGER_DIR) / "config.json"

@dataclass
class EmailConfig:
    """Email notification configuration"""
    enabled: bool = False
    smtp_server: str = ""
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    to_emails: list = None
    use_tls: bool = True
    
    def __post_init__(self):
        if self.to_emails is None:
            self.to_emails = []

@dataclass
class SlackConfig:
    """Slack webhook configuration"""
    enabled: bool = False
    webhook_url: str = ""
    channel: str = ""

@dataclass
class DiscordConfig:
    """Discord webhook configuration"""
    enabled: bool = False
    webhook_url: str = ""

@dataclass
class WebhookConfig:
    """Custom webhook configuration"""
    enabled: bool = False
    url: str = ""
    headers: dict = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}

@dataclass
class AlertsConfig:
    """Alerts and monitoring configuration"""
    enabled: bool = True
    check_interval: int = 300  # 5 minutes
    email: EmailConfig = None
    slack: SlackConfig = None
    discord: DiscordConfig = None
    webhook: WebhookConfig = None
    
    def __post_init__(self):
        if self.email is None:
            self.email = EmailConfig()
        if self.slack is None:
            self.slack = SlackConfig()
        if self.discord is None:
            self.discord = DiscordConfig()
        if self.webhook is None:
            self.webhook = WebhookConfig()

@dataclass
class FirewallConfig:
    """Firewall management configuration"""
    enabled: bool = True
    auto_enable: bool = False
    default_policy_input: str = "deny"
    default_policy_output: str = "allow"
    default_policy_forward: str = "deny"

@dataclass
class SecurityConfig:
    """Security scanning configuration"""
    enabled: bool = True
    auto_scan_on_startup: bool = False
    auto_apply_fixes: bool = False

@dataclass
class DockerConfig:
    """Docker integration configuration"""
    enabled: bool = True
    auto_discover: bool = True
    auto_configure: bool = False

@dataclass
class VersionControlConfig:
    """Version control configuration"""
    enabled: bool = True
    auto_commit: bool = False
    auto_commit_message: str = "Auto-commit: Configuration changes"

@dataclass
class AppConfig:
    """Main application configuration"""
    first_run_complete: bool = False
    alerts: AlertsConfig = None
    firewall: FirewallConfig = None
    security: SecurityConfig = None
    docker: DockerConfig = None
    version_control: VersionControlConfig = None
    
    def __post_init__(self):
        if self.alerts is None:
            self.alerts = AlertsConfig()
        if self.firewall is None:
            self.firewall = FirewallConfig()
        if self.security is None:
            self.security = SecurityConfig()
        if self.docker is None:
            self.docker = DockerConfig()
        if self.version_control is None:
            self.version_control = VersionControlConfig()

class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.config: AppConfig = self.load()
    
    def load(self) -> AppConfig:
        """Load configuration from file"""
        if not self.config_file.exists():
            return AppConfig()
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            
            # Reconstruct nested dataclasses
            if 'alerts' in data and isinstance(data['alerts'], dict):
                alerts_data = data['alerts']
                if 'email' in alerts_data and isinstance(alerts_data['email'], dict):
                    alerts_data['email'] = EmailConfig(**alerts_data['email'])
                if 'slack' in alerts_data and isinstance(alerts_data['slack'], dict):
                    alerts_data['slack'] = SlackConfig(**alerts_data['slack'])
                if 'discord' in alerts_data and isinstance(alerts_data['discord'], dict):
                    alerts_data['discord'] = DiscordConfig(**alerts_data['discord'])
                if 'webhook' in alerts_data and isinstance(alerts_data['webhook'], dict):
                    alerts_data['webhook'] = WebhookConfig(**alerts_data['webhook'])
                data['alerts'] = AlertsConfig(**alerts_data)
            
            if 'firewall' in data and isinstance(data['firewall'], dict):
                data['firewall'] = FirewallConfig(**data['firewall'])
            
            if 'security' in data and isinstance(data['security'], dict):
                data['security'] = SecurityConfig(**data['security'])
            
            if 'docker' in data and isinstance(data['docker'], dict):
                data['docker'] = DockerConfig(**data['docker'])
            
            if 'version_control' in data and isinstance(data['version_control'], dict):
                data['version_control'] = VersionControlConfig(**data['version_control'])
            
            return AppConfig(**data)
        except Exception as e:
            print(f"Error loading config: {e}")
            return AppConfig()
    
    def save(self) -> bool:
        """Save configuration to file"""
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict recursively
            def to_dict(obj):
                if hasattr(obj, '__dict__'):
                    result = {}
                    for key, value in obj.__dict__.items():
                        if hasattr(value, '__dict__'):
                            result[key] = to_dict(value)
                        elif isinstance(value, list):
                            result[key] = [to_dict(item) if hasattr(item, '__dict__') else item for item in value]
                        elif isinstance(value, dict):
                            result[key] = {k: to_dict(v) if hasattr(v, '__dict__') else v for k, v in value.items()}
                        else:
                            result[key] = value
                    return result
                return obj
            
            data = to_dict(self.config)
            
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def is_first_run(self) -> bool:
        """Check if this is the first run"""
        return not self.config.first_run_complete
    
    def mark_first_run_complete(self):
        """Mark first run as complete"""
        self.config.first_run_complete = True
        self.save()
    
    def get_missing_config_options(self) -> list:
        """Get list of features that need configuration"""
        missing = []
        
        if self.config.alerts.enabled:
            if not (self.config.alerts.email.enabled or 
                   self.config.alerts.slack.enabled or 
                   self.config.alerts.discord.enabled or
                   self.config.alerts.webhook.enabled):
                missing.append("alerts")
        
        return missing
    
    def needs_selective_onboarding(self) -> bool:
        """Check if selective onboarding is needed"""
        return len(self.get_missing_config_options()) > 0
