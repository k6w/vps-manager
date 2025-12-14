import curses
import time
import datetime
from typing import List, Optional
from pathlib import Path

from .core import VPSManager, VERSION
from .utils import MANAGER_DIR, NGINX_SITES_DIR, NGINX_ENABLED_DIR, LOG_FILE

class TerminalUI:
    """Terminal-based user interface using curses"""
    
    def __init__(self, manager: VPSManager):
        self.manager = manager
        self.current_selection = 0
        self.menu_items = [
            "List Domains",
            "Add Domain",
            "Edit Domain",
            "Delete Domain",
            "NGINX Status",
            "Version Control (Git-like)",  # NEW - Enhanced backup system
            "Firewall Management",          # NEW
            "Security Scanner",             # NEW
            "Alerts & Monitoring",          # NEW
            "Docker Integration",           # NEW
            "View Logs",
            "Settings",
            "Exit"
        ]
    
    def _wait_for_input(self, stdscr):
        """Wait for user input with a small delay and buffer flush"""
        time.sleep(0.5)
        # Flush input buffer
        stdscr.nodelay(True)
        while stdscr.getch() != -1:
            pass
        stdscr.nodelay(False)
        stdscr.getch()
    
    def _check_feature_configured(self, stdscr, feature: str) -> bool:
        """Check if a feature is properly configured, show config UI if not"""
        config = self.manager.config_manager.config
        
        # Check if feature is enabled
        if feature == "firewall":
            if not config.firewall.enabled:
                return self._show_feature_setup(stdscr, "Firewall Management", [
                    "Firewall management is currently disabled.",
                    "",
                    "To use this feature, you need to:",
                    "  1. Enable UFW firewall on your system",
                    "  2. Configure default policies (deny incoming, allow outgoing)",
                    "  3. Set up basic rules for SSH, HTTP, and HTTPS",
                    "",
                    "Would you like to configure it now?"
                ], self._configure_firewall_setup)
            return True
            
        elif feature == "security":
            if not config.security.enabled:
                return self._show_feature_setup(stdscr, "Security Scanner", [
                    "Security scanner is currently disabled.",
                    "",
                    "To use this feature, you need to:",
                    "  1. Enable security scanning",
                    "  2. Choose scan frequency (manual or automatic)",
                    "",
                    "Would you like to configure it now?"
                ], self._configure_security_setup)
            return True
            
        elif feature == "alerts":
            if not config.alerts.enabled:
                return self._show_feature_setup(stdscr, "Alerts & Monitoring", [
                    "Alerts & Monitoring is currently disabled.",
                    "",
                    "To use this feature, you need to:",
                    "  1. Enable monitoring system",
                    "  2. Configure at least one notification channel:",
                    "     - Email (SMTP configuration)",
                    "     - Slack (webhook URL)",
                    "     - Discord (webhook URL)",
                    "     - Custom webhook",
                    "",
                    "Would you like to configure it now?"
                ], self._configure_alerts)
            
            # Check if at least one notification channel is configured
            has_channel = (config.alerts.email.enabled or 
                          config.alerts.slack.enabled or 
                          config.alerts.discord.enabled or 
                          config.alerts.webhook.enabled)
            
            if not has_channel:
                return self._show_feature_setup(stdscr, "Alerts Configuration Required", [
                    "Alerts & Monitoring is enabled but no notification",
                    "channels are configured.",
                    "",
                    "You need to configure at least one channel:",
                    "",
                    "EMAIL:",
                    "  - SMTP server (e.g., smtp.gmail.com)",
                    "  - SMTP port (usually 587 or 465)",
                    "  - Username and password",
                    "  - From and To email addresses",
                    "",
                    "SLACK:",
                    "  - Webhook URL from Slack app",
                    "  - Channel name (optional)",
                    "",
                    "DISCORD:",
                    "  - Webhook URL from Discord server settings",
                    "",
                    "CUSTOM WEBHOOK:",
                    "  - Any HTTP endpoint URL",
                    "  - Optional headers",
                    "",
                    "Would you like to configure a notification channel now?"
                ], self._configure_alerts)
            return True
            
        elif feature == "docker":
            if not config.docker.enabled:
                return self._show_feature_setup(stdscr, "Docker Integration", [
                    "Docker integration is currently disabled.",
                    "",
                    "To use this feature, you need to:",
                    "  1. Install Docker on your system",
                    "  2. Enable Docker integration",
                    "  3. Optionally enable auto-discovery of containers",
                    "",
                    "Would you like to configure it now?"
                ], self._configure_docker_setup)
            return True
            
        elif feature == "version_control":
            if not config.version_control.enabled:
                return self._show_feature_setup(stdscr, "Version Control", [
                    "Version Control system is currently disabled.",
                    "",
                    "This feature provides Git-like functionality for",
                    "managing your VPS configurations:",
                    "  - Commit configuration changes",
                    "  - View history and diffs",
                    "  - Restore previous states",
                    "  - Branch management",
                    "  - Tag important versions",
                    "",
                    "Would you like to enable it now?"
                ], lambda stdscr: self._enable_version_control(stdscr))
            return True
        
        return True
    
    def _show_feature_setup(self, stdscr, title: str, info_lines: list, config_func) -> bool:
        """Show feature setup information and offer to configure"""
        stdscr.clear()
        stdscr.addstr(1, 2, title, curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * len(title))
        
        y = 4
        for line in info_lines:
            if y < curses.LINES - 4:
                stdscr.addstr(y, 2, line)
                y += 1
        
        stdscr.addstr(curses.LINES - 2, 2, "Press Y to configure, N to cancel, or ESC to go back")
        stdscr.refresh()
        
        while True:
            key = stdscr.getch()
            if key == ord('y') or key == ord('Y'):
                config_func(stdscr)
                # Return True to allow access after configuration
                return True
            elif key == ord('n') or key == ord('N') or key == 27:
                return False
    
    def _enable_version_control(self, stdscr):
        """Enable version control system"""
        self.manager.config_manager.config.version_control.enabled = True
        
        stdscr.clear()
        stdscr.addstr(1, 2, "Enable Auto-Commit?")
        stdscr.addstr(2, 2, "=" * 19)
        stdscr.addstr(4, 2, "Would you like to automatically commit configuration")
        stdscr.addstr(5, 2, "changes after each domain operation? (y/n)")
        stdscr.refresh()
        
        key = stdscr.getch()
        if key == ord('y') or key == ord('Y'):
            self.manager.config_manager.config.version_control.auto_commit = True
        
        self.manager.config_manager.save()
        self._show_message(stdscr, "Success", "[OK] Version Control enabled!")
    
    def run(self):
        """Start the terminal UI"""
        # Check if this is the first run and show onboarding
        if self.manager.is_first_run():
            curses.wrapper(self._onboarding_flow)
        elif self.manager.needs_selective_onboarding():
             curses.wrapper(lambda stdscr: self._selective_onboarding_flow(stdscr, self.manager.get_missing_config_options()))
        
        curses.wrapper(self._main_loop)
    
    # ==================== SETUP WIZARD / ONBOARDING ====================
    
    def _onboarding_flow(self, stdscr):
        """First-run setup wizard"""
        curses.curs_set(0)
        stdscr.keypad(True)
        
        # Welcome screen
        stdscr.clear()
        stdscr.addstr(1, 2, "=" * 60)
        stdscr.addstr(2, 2, "VPS NGINX Domain Manager - First Run Setup".center(60))
        stdscr.addstr(3, 2, "=" * 60)
        stdscr.addstr(5, 2, "Welcome! Let's configure your VPS Manager.")
        stdscr.addstr(7, 2, "This wizard will help you set up:")
        stdscr.addstr(8, 4, "- Dependency checking (NGINX, Certbot, UFW, Docker)")
        stdscr.addstr(9, 4, "- Alert notifications (Email, Slack, Discord, Webhooks)")
        stdscr.addstr(10, 4, "- Firewall management")
        stdscr.addstr(11, 4, "- Security scanning")
        stdscr.addstr(12, 4, "- Docker integration")
        stdscr.addstr(14, 2, "You can reconfigure these later in Settings.")
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
        
        # Dependency checking
        self._check_dependencies(stdscr)
        
        # Feature configuration
        self._configure_features(stdscr)
        
        # Complete setup
        self.manager.mark_first_run_complete()
        
        stdscr.clear()
        stdscr.addstr(1, 2, "=" * 60)
        stdscr.addstr(2, 2, "Setup Complete!".center(60))
        stdscr.addstr(3, 2, "=" * 60)
        stdscr.addstr(5, 2, "[OK] Your VPS Manager is now configured.")
        stdscr.addstr(7, 2, "You can now manage domains, configure SSL, and more.")
        stdscr.addstr(9, 2, "Tip: Use the Settings menu to adjust configuration later.")
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue to main menu...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
    
    def _selective_onboarding_flow(self, stdscr, missing_options):
        """Selective onboarding for missing configuration"""
        curses.curs_set(0)
        stdscr.keypad(True)
        
        stdscr.clear()
        stdscr.addstr(1, 2, "Configuration Update Needed")
        stdscr.addstr(2, 2, "=" * 27)
        stdscr.addstr(4, 2, "Some features need configuration:")
        for i, opt in enumerate(missing_options):
            stdscr.addstr(5 + i, 4, f"- {opt}")
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to configure...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
        
        if "alerts" in missing_options:
            self._configure_alerts(stdscr)
    
    def _check_dependencies(self, stdscr):
        """Check and offer to install dependencies"""
        import shutil
        import subprocess
        
        stdscr.clear()
        stdscr.addstr(1, 2, "Checking Dependencies...")
        stdscr.addstr(2, 2, "=" * 24)
        
        y = 4
        deps = {
            'nginx': 'NGINX Web Server',
            'certbot': 'Let\'s Encrypt Certbot',
            'ufw': 'Uncomplicated Firewall',
            'docker': 'Docker Container Platform'
        }
        
        missing = []
        for cmd, name in deps.items():
            stdscr.addstr(y, 2, f"Checking {name}...")
            stdscr.refresh()
            
            if shutil.which(cmd):
                stdscr.addstr(y, 40, "[OK] Found", curses.A_BOLD)
            else:
                stdscr.addstr(y, 40, "[!] Not Found", curses.A_BOLD)
                missing.append((cmd, name))
            y += 1
        
        if missing:
            y += 1
            stdscr.addstr(y, 2, "Missing dependencies detected.")
            y += 1
            stdscr.addstr(y, 2, "Would you like to install them? (y/n)")
            stdscr.refresh()
            
            key = stdscr.getch()
            if key == ord('y') or key == ord('Y'):
                y += 2
                for cmd, name in missing:
                    stdscr.addstr(y, 2, f"Installing {name}...")
                    stdscr.refresh()
                    
                    try:
                        if cmd == 'nginx':
                            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'nginx'], check=True)
                        elif cmd == 'certbot':
                            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'certbot', 'python3-certbot-nginx'], check=True)
                        elif cmd == 'ufw':
                            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ufw'], check=True)
                        elif cmd == 'docker':
                            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'docker.io'], check=True)
                        
                        stdscr.addstr(y, 40, "[OK] Installed")
                    except Exception as e:
                        stdscr.addstr(y, 40, "[X] Failed")
                    y += 1
                
                stdscr.refresh()
                time.sleep(1)
        else:
            y += 1
            stdscr.addstr(y, 2, "[OK] All dependencies found!")
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
    
    def _configure_features(self, stdscr):
        """Configure features during setup"""
        features = [
            ("Alerts & Monitoring", self._configure_alerts),
            ("Firewall Management", self._configure_firewall_setup),
            ("Security Scanner", self._configure_security_setup),
            ("Docker Integration", self._configure_docker_setup),
        ]
        
        for name, config_func in features:
            stdscr.clear()
            stdscr.addstr(1, 2, f"Configure {name}?")
            stdscr.addstr(2, 2, "=" * (11 + len(name)))
            stdscr.addstr(4, 2, f"Would you like to enable {name}? (y/n)")
            stdscr.addstr(5, 2, "(You can change this later in Settings)")
            stdscr.refresh()
            
            key = stdscr.getch()
            if key == ord('y') or key == ord('Y'):
                config_func(stdscr)
            else:
                # Disable feature
                if name == "Alerts & Monitoring":
                    self.manager.config_manager.config.alerts.enabled = False
                elif name == "Firewall Management":
                    self.manager.config_manager.config.firewall.enabled = False
                elif name == "Security Scanner":
                    self.manager.config_manager.config.security.enabled = False
                elif name == "Docker Integration":
                    self.manager.config_manager.config.docker.enabled = False
                self.manager.config_manager.save()
    
    def _configure_alerts(self, stdscr):
        """Configure alert notifications"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Alert Notification Setup")
        stdscr.addstr(2, 2, "=" * 24)
        stdscr.addstr(4, 2, "Select notification channels to configure:")
        stdscr.addstr(6, 2, "1. Email (SMTP)")
        stdscr.addstr(7, 2, "2. Slack Webhook")
        stdscr.addstr(8, 2, "3. Discord Webhook")
        stdscr.addstr(9, 2, "4. Custom Webhook")
        stdscr.addstr(10, 2, "5. Skip for now")
        stdscr.addstr(curses.LINES - 2, 2, "Enter choice (1-5):")
        stdscr.refresh()
        
        key = stdscr.getch()
        
        if key == ord('1'):
            self._configure_email(stdscr)
        elif key == ord('2'):
            self._configure_slack(stdscr)
        elif key == ord('3'):
            self._configure_discord(stdscr)
        elif key == ord('4'):
            self._configure_webhook(stdscr)
        
        self.manager.config_manager.config.alerts.enabled = True
        self.manager.config_manager.save()
    
    def _configure_email(self, stdscr):
        """Configure email notifications"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Email Configuration")
        stdscr.addstr(2, 2, "=" * 19)
        
        server = self._get_input(stdscr, "SMTP Server (e.g., smtp.gmail.com)", 4, 2)
        if not server:
            return
        
        port = self._get_input(stdscr, "SMTP Port", 5, 2, "587")
        username = self._get_input(stdscr, "Username/Email", 6, 2)
        password = self._get_input(stdscr, "Password", 7, 2)
        from_email = self._get_input(stdscr, "From Email", 8, 2, username or "")
        to_emails = self._get_input(stdscr, "To Emails (comma-separated)", 9, 2)
        
        if server and username and password:
            self.manager.config_manager.config.alerts.email.enabled = True
            self.manager.config_manager.config.alerts.email.smtp_server = server
            self.manager.config_manager.config.alerts.email.smtp_port = int(port) if port.isdigit() else 587
            self.manager.config_manager.config.alerts.email.username = username
            self.manager.config_manager.config.alerts.email.password = password
            self.manager.config_manager.config.alerts.email.from_email = from_email or username
            self.manager.config_manager.config.alerts.email.to_emails = [e.strip() for e in to_emails.split(',') if e.strip()]
            self.manager.config_manager.save()
            
            self._show_message(stdscr, "Success", "[OK] Email configuration saved!")
    
    def _configure_slack(self, stdscr):
        """Configure Slack webhook"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Slack Configuration")
        stdscr.addstr(2, 2, "=" * 19)
        
        webhook_url = self._get_input(stdscr, "Slack Webhook URL", 4, 2)
        channel = self._get_input(stdscr, "Channel (optional)", 5, 2, "#alerts")
        
        if webhook_url:
            self.manager.config_manager.config.alerts.slack.enabled = True
            self.manager.config_manager.config.alerts.slack.webhook_url = webhook_url
            self.manager.config_manager.config.alerts.slack.channel = channel or "#alerts"
            self.manager.config_manager.save()
            
            self._show_message(stdscr, "Success", "[OK] Slack configuration saved!")
    
    def _configure_discord(self, stdscr):
        """Configure Discord webhook"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Discord Configuration")
        stdscr.addstr(2, 2, "=" * 21)
        
        webhook_url = self._get_input(stdscr, "Discord Webhook URL", 4, 2)
        
        if webhook_url:
            self.manager.config_manager.config.alerts.discord.enabled = True
            self.manager.config_manager.config.alerts.discord.webhook_url = webhook_url
            self.manager.config_manager.save()
            
            self._show_message(stdscr, "Success", "[OK] Discord configuration saved!")
    
    def _configure_webhook(self, stdscr):
        """Configure custom webhook"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Custom Webhook Configuration")
        stdscr.addstr(2, 2, "=" * 29)
        
        url = self._get_input(stdscr, "Webhook URL", 4, 2)
        
        if url:
            self.manager.config_manager.config.alerts.webhook.enabled = True
            self.manager.config_manager.config.alerts.webhook.url = url
            self.manager.config_manager.save()
            
            self._show_message(stdscr, "Success", "[OK] Webhook configuration saved!")
    
    def _configure_firewall_setup(self, stdscr):
        """Configure firewall during setup"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Firewall Setup")
        stdscr.addstr(2, 2, "=" * 14)
        stdscr.addstr(4, 2, "Enable UFW firewall with default web server rules? (y/n)")
        stdscr.addstr(5, 2, "(This will allow ports 22, 80, 443)")
        stdscr.refresh()
        
        key = stdscr.getch()
        if key == ord('y') or key == ord('Y'):
            self.manager.config_manager.config.firewall.enabled = True
            self.manager.config_manager.config.firewall.auto_enable = True
            self.manager.config_manager.save()
            
            # Auto-configure firewall
            try:
                self.manager.firewall.quick_setup_web_server()
                self._show_message(stdscr, "Success", "[OK] Firewall configured!")
            except Exception as e:
                self._show_message(stdscr, "Error", f"Failed to configure firewall: {e}", True)
        else:
            self.manager.config_manager.config.firewall.enabled = False
            self.manager.config_manager.save()
    
    def _configure_security_setup(self, stdscr):
        """Configure security scanner during setup"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Security Scanner Setup")
        stdscr.addstr(2, 2, "=" * 22)
        stdscr.addstr(4, 2, "Run security scan on startup? (y/n)")
        stdscr.refresh()
        
        key = stdscr.getch()
        self.manager.config_manager.config.security.enabled = True
        self.manager.config_manager.config.security.auto_scan_on_startup = (key == ord('y') or key == ord('Y'))
        self.manager.config_manager.save()
    
    def _configure_docker_setup(self, stdscr):
        """Configure Docker integration during setup"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Docker Integration Setup")
        stdscr.addstr(2, 2, "=" * 24)
        stdscr.addstr(4, 2, "Auto-discover running Docker containers? (y/n)")
        stdscr.refresh()
        
        key = stdscr.getch()
        self.manager.config_manager.config.docker.enabled = True
        self.manager.config_manager.config.docker.auto_discover = (key == ord('y') or key == ord('Y'))
        self.manager.config_manager.save()
    
    def _main_loop(self, stdscr):
        """Main UI loop"""
        curses.curs_set(0)  # Hide cursor
        stdscr.keypad(True)  # Enable special keys
        stdscr.timeout(100)  # Set timeout for non-blocking input
        
        while True:
            stdscr.clear()
            self._draw_header(stdscr)
            self._draw_menu(stdscr)
            self._draw_footer(stdscr)
            stdscr.refresh()
            
            key = stdscr.getch()
            
            # Handle exit shortcuts
            if key == 3:  # Ctrl+C
                break
            elif key == 24:  # Ctrl+X
                break
            elif key == 27:  # ESC
                break
            elif key == ord('q') or key == ord('Q'):  # Q key for quit
                break
            elif key == curses.KEY_UP and self.current_selection > 0:
                self.current_selection -= 1
            elif key == curses.KEY_DOWN and self.current_selection < len(self.menu_items) - 1:
                self.current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if self.current_selection == len(self.menu_items) - 1:  # Exit
                    break
                else:
                    self._handle_menu_selection(stdscr)
            elif key == -1:  # Timeout, continue loop
                continue
    
    def _draw_header(self, stdscr):
        """Draw the header"""
        header = f"VPS NGINX Domain Manager v{VERSION}"
        stdscr.addstr(1, 2, "=" * 60)
        stdscr.addstr(2, 2, header.center(56))
        stdscr.addstr(3, 2, "=" * 60)
        stdscr.addstr(4, 2, f"Domains: {len(self.manager.domains)} | Manager Dir: {MANAGER_DIR}")
        stdscr.addstr(5, 2, "=" * 60)
    
    def _draw_menu(self, stdscr):
        """Draw the main menu"""
        start_y = 7
        for i, item in enumerate(self.menu_items):
            if i == self.current_selection:
                stdscr.addstr(start_y + i, 4, f"> {item}", curses.A_REVERSE)
            else:
                stdscr.addstr(start_y + i, 4, f"  {item}")
    
    def _draw_footer(self, stdscr):
        """Draw the footer"""
        footer_y = curses.LINES - 3
        stdscr.addstr(footer_y, 2, "=" * 60)
        stdscr.addstr(footer_y + 1, 2, "Up/Down: Navigate | Enter/Space: Select | ESC/Ctrl+C/Ctrl+X/Q: Exit")
    
    def _handle_menu_selection(self, stdscr):
        """Handle menu selection"""
        selection = self.current_selection
        
        if selection == 0:  # List Domains
            self._list_domains(stdscr)
        elif selection == 1:  # Add Domain
            self._add_domain(stdscr)
        elif selection == 2:  # Edit Domain
            self._edit_domain(stdscr)
        elif selection == 3:  # Delete Domain
            self._delete_domain(stdscr)
        elif selection == 4:  # NGINX Status
            self._nginx_status(stdscr)
        elif selection == 5:  # Version Control
            if self._check_feature_configured(stdscr, "version_control"):
                self._version_control_menu(stdscr)
        elif selection == 6:  # Firewall Management
            if self._check_feature_configured(stdscr, "firewall"):
                self._firewall_management(stdscr)
        elif selection == 7:  # Security Scanner
            if self._check_feature_configured(stdscr, "security"):
                self._security_scanner(stdscr)
        elif selection == 8:  # Alerts & Monitoring
            if self._check_feature_configured(stdscr, "alerts"):
                self._alerts_monitoring(stdscr)
        elif selection == 9:  # Docker Integration
            if self._check_feature_configured(stdscr, "docker"):
                self._docker_integration(stdscr)
        elif selection == 10:  # View Logs
            self._view_logs(stdscr)
        elif selection == 11:  # Settings
            self._settings_menu(stdscr)
    
    def _get_input(self, stdscr, prompt: str, y: int, x: int, default: str = "") -> str:
        """Get user input with prompt and exit handling"""
        curses.curs_set(1)
        stdscr.addstr(y, x, f"{prompt}: ")
        if default:
            stdscr.addstr(y, x + len(prompt) + 2, default)
        stdscr.addstr(y + 1, x, "(Press ESC, Ctrl+C, or Ctrl+X to cancel)")
        stdscr.refresh()
        
        # Manual input handling for exit shortcuts
        input_str = ""
        cursor_pos = len(default)
        
        if default:
            input_str = default
        
        while True:
            # Position cursor
            stdscr.move(y, x + len(prompt) + 2 + cursor_pos)
            curses.curs_set(1)
            
            key = stdscr.getch()
            
            # Handle exit shortcuts
            if key == 27 or key == 3 or key == 24:  # ESC, Ctrl+C, Ctrl+X
                curses.curs_set(0)
                return None  # Signal cancellation
            elif key == ord('\n'):  # Enter
                break
            elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:  # Backspace
                if cursor_pos > 0:
                    input_str = input_str[:cursor_pos-1] + input_str[cursor_pos:]
                    cursor_pos -= 1
                    # Clear and redraw line
                    stdscr.move(y, x + len(prompt) + 2)
                    stdscr.clrtoeol()
                    stdscr.addstr(y, x + len(prompt) + 2, input_str)
            elif key == curses.KEY_LEFT and cursor_pos > 0:
                cursor_pos -= 1
            elif key == curses.KEY_RIGHT and cursor_pos < len(input_str):
                cursor_pos += 1
            elif 32 <= key <= 126 and len(input_str) < 50:  # Printable characters
                char = chr(key)
                input_str = input_str[:cursor_pos] + char + input_str[cursor_pos:]
                cursor_pos += 1
                # Clear and redraw line
                stdscr.move(y, x + len(prompt) + 2)
                stdscr.clrtoeol()
                stdscr.addstr(y, x + len(prompt) + 2, input_str)
        
        curses.curs_set(0)
        # Clear the cancel instruction line
        stdscr.move(y + 1, x)
        stdscr.clrtoeol()
        
        return input_str if input_str else default
    
    def _show_message(self, stdscr, title: str, message: str, is_error: bool = False):
        """Show a message dialog"""
        stdscr.clear()
        stdscr.addstr(1, 2, title)
        stdscr.addstr(2, 2, "=" * len(title))
        
        # Split long messages into multiple lines
        lines = []
        words = message.split(' ')
        current_line = ""
        max_width = curses.COLS - 6
        
        for word in words:
            if len(current_line + word) < max_width:
                current_line += word + " "
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            lines.append(current_line.strip())
        
        for i, line in enumerate(lines):
            attr = curses.A_BOLD if is_error else curses.A_NORMAL
            stdscr.addstr(4 + i, 2, line, attr)
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        stdscr.refresh()
        
        self._wait_for_input(stdscr)
    
    def _confirm_action(self, stdscr, message: str) -> bool:
        """Show confirmation dialog"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Confirmation")
        stdscr.addstr(2, 2, "=" * 12)
        stdscr.addstr(4, 2, message)
        stdscr.addstr(6, 2, "Are you sure? (y/N): ")
        stdscr.refresh()
        
        time.sleep(0.5)
        # Flush input buffer
        stdscr.nodelay(True)
        while stdscr.getch() != -1:
            pass
        stdscr.nodelay(False)
        
        key = stdscr.getch()
        return key in [ord('y'), ord('Y')]
    
    def _select_from_list(self, stdscr, title: str, items: List[str], allow_cancel: bool = True) -> Optional[int]:
        """Select item from list"""
        if not items:
            self._show_message(stdscr, title, "No items available.")
            return None
        
        current_selection = 0
        
        # Flush input buffer before starting interaction
        time.sleep(0.2)
        stdscr.nodelay(True)
        while stdscr.getch() != -1:
            pass
        stdscr.nodelay(False)
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, title)
            stdscr.addstr(2, 2, "=" * len(title))
            
            for i, item in enumerate(items):
                if i == current_selection:
                    stdscr.addstr(4 + i, 4, f"> {item}", curses.A_REVERSE)
                else:
                    stdscr.addstr(4 + i, 4, f"  {item}")
            
            if allow_cancel:
                cancel_line = 4 + len(items) + 1
                if current_selection == len(items):
                    stdscr.addstr(cancel_line, 4, "> Cancel", curses.A_REVERSE)
                else:
                    stdscr.addstr(cancel_line, 4, "  Cancel")
            
            stdscr.addstr(curses.LINES - 2, 2, "Use Up/Down to navigate, Enter to select")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            max_selection = len(items) + (1 if allow_cancel else 0) - 1
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < max_selection:
                current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if allow_cancel and current_selection == len(items):
                    return None  # Cancel
                else:
                    return current_selection
            elif key == 27:  # ESC
                return None
    
    def _list_domains(self, stdscr):
        """Display list of domains"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Domain List")
        stdscr.addstr(2, 2, "=" * 40)
        
        if not self.manager.domains:
            stdscr.addstr(4, 2, "No domains configured.")
        else:
            stdscr.addstr(4, 2, "Domain Name".ljust(25) + "Port".ljust(8) + "SSL".ljust(8) + "Config".ljust(12) + "Status")
            stdscr.addstr(5, 2, "-" * 70)
            
            for i, domain in enumerate(self.manager.domains):
                ssl_status = "Yes" if domain.ssl else "No"
                config_type = "Custom" if domain.custom_config else "Default"
                
                # Check if NGINX config exists
                config_file = NGINX_SITES_DIR / domain.name
                enabled_file = NGINX_ENABLED_DIR / domain.name
                
                if config_file.exists() and enabled_file.exists():
                    status = "Active"
                elif config_file.exists():
                    status = "Disabled"
                else:
                    status = "Missing"
                
                line = f"{domain.name[:24].ljust(25)}{str(domain.port).ljust(8)}{ssl_status.ljust(8)}{config_type[:11].ljust(12)}{status}"
                stdscr.addstr(6 + i, 2, line)
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _add_domain(self, stdscr):
        """Add a new domain"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Add New Domain")
        stdscr.addstr(2, 2, "=" * 15)
        
        try:
            # Get domain name
            domain_name = self._get_input(stdscr, "Domain name (e.g., api.v1.example.com)", 4, 2)
            if domain_name is None:  # User cancelled
                return
            if not domain_name:
                self._show_message(stdscr, "Error", "Domain name is required.", True)
                return
            
            # Get port
            port_str = self._get_input(stdscr, "Backend port (e.g., 3000)", 5, 2)
            if port_str is None:  # User cancelled
                return
            try:
                port = int(port_str)
            except ValueError:
                self._show_message(stdscr, "Error", "Invalid port number.", True)
                return
            
            # Get SSL preference (use configured default)
            default_ssl = 'y' if self.manager.config.get('default_ssl', True) else 'n'
            ssl_choice = self._get_input(stdscr, f"Enable SSL? ({'Y/n' if default_ssl == 'y' else 'y/N'})", 6, 2, default_ssl)
            if ssl_choice is None:  # User cancelled
                return
            ssl_enabled = ssl_choice.lower() in ['y', 'yes']
            
            # Get custom config preference
            custom_choice = self._get_input(stdscr, "Use custom config? (Y/n)", 7, 2, "y")
            if custom_choice is None:  # User cancelled
                return
            custom_config = None
            
            if custom_choice.lower() in ['y', 'yes']:
                # List available custom configs
                custom_configs_dir = MANAGER_DIR / "custom-configs"
                if custom_configs_dir.exists():
                    configs = [f.name for f in custom_configs_dir.iterdir() if f.is_file() and f.suffix == '.conf']
                    if configs:
                        selection = self._select_from_list(stdscr, "Select Custom Configuration", configs)
                        if selection is not None:
                            custom_config = configs[selection]
                    else:
                        self._show_message(stdscr, "Info", "No custom configurations found. Using default template.")
            
            # Show summary and confirm
            summary = f"Domain: {domain_name}\nPort: {port}\nSSL: {'Yes' if ssl_enabled else 'No'}\nConfig: {custom_config or 'Default'}"
            
            stdscr.clear()
            stdscr.addstr(1, 2, "Confirm Domain Addition")
            stdscr.addstr(2, 2, "=" * 23)
            
            lines = summary.split('\n')
            for i, line in enumerate(lines):
                stdscr.addstr(4 + i, 2, line)
            
            if self._confirm_action(stdscr, "\nProceed with domain creation?"):
                # Show progress
                stdscr.clear()
                stdscr.addstr(1, 2, "Creating Domain...")
                stdscr.addstr(3, 2, "Please wait, this may take a few moments...")
                stdscr.refresh()
                
                # Create backup if auto-backup is enabled
                if self.manager.config.get('auto_backup', False):
                    stdscr.addstr(4, 2, "Creating backup...")
                    stdscr.refresh()
                    self.manager.create_domain_backup(domain_name)
                
                # Add domain
                success, message = self.manager.add_domain(domain_name, port, ssl_enabled, custom_config)
                
                if success:
                    self._show_message(stdscr, "Success", message)
                else:
                    self._show_message(stdscr, "Error", message, True)
            
        except Exception as e:
            self._show_message(stdscr, "Error", f"An error occurred: {str(e)}", True)
    
    def _edit_domain(self, stdscr):
        """Edit existing domain"""
        if not self.manager.domains:
            self._show_message(stdscr, "Edit Domain", "No domains available to edit.")
            return
        
        # Select domain to edit
        domain_names = [d.name for d in self.manager.domains]
        selection = self._select_from_list(stdscr, "Select Domain to Edit", domain_names)
        
        if selection is None:
            return
        
        domain = self.manager.domains[selection]
        
        try:
            stdscr.clear()
            stdscr.addstr(1, 2, f"Edit Domain: {domain.name}")
            stdscr.addstr(2, 2, "=" * (13 + len(domain.name)))
            stdscr.addstr(4, 2, "Leave empty to keep current value")
            
            # Get new values
            new_name = self._get_input(stdscr, f"Domain name ({domain.name})", 6, 2)
            if new_name is None:  # User cancelled
                return
            new_port_str = self._get_input(stdscr, f"Port ({domain.port})", 7, 2)
            if new_port_str is None:  # User cancelled
                return
            new_ssl_str = self._get_input(stdscr, f"SSL ({'Yes' if domain.ssl else 'No'})", 8, 2)
            if new_ssl_str is None:  # User cancelled
                return
            
            # Process inputs
            new_port = None
            if new_port_str:
                try:
                    new_port = int(new_port_str)
                except ValueError:
                    self._show_message(stdscr, "Error", "Invalid port number.", True)
                    return
            
            new_ssl = None
            if new_ssl_str:
                new_ssl = new_ssl_str.lower() in ['y', 'yes', 'true', '1']
            
            # Confirm changes
            changes = []
            if new_name and new_name != domain.name:
                changes.append(f"Name: {domain.name} -> {new_name}")
            if new_port and new_port != domain.port:
                changes.append(f"Port: {domain.port} -> {new_port}")
            if new_ssl is not None and new_ssl != domain.ssl:
                changes.append(f"SSL: {'Yes' if domain.ssl else 'No'} -> {'Yes' if new_ssl else 'No'}")
            
            if not changes:
                self._show_message(stdscr, "Info", "No changes specified.")
                return
            
            changes_text = "\n".join(changes)
            if self._confirm_action(stdscr, f"Apply these changes?\n\n{changes_text}"):
                # Show progress
                stdscr.clear()
                stdscr.addstr(1, 2, "Updating Domain...")
                stdscr.addstr(3, 2, "Please wait...")
                stdscr.refresh()
                
                # Apply changes
                success, message = self.manager.edit_domain(
                    domain.name, new_name, new_port, new_ssl
                )
                
                if success:
                    self._show_message(stdscr, "Success", message)
                else:
                    self._show_message(stdscr, "Error", message, True)
        
        except Exception as e:
            self._show_message(stdscr, "Error", f"An error occurred: {str(e)}", True)
    
    def _delete_domain(self, stdscr):
        """Delete a domain"""
        if not self.manager.domains:
            self._show_message(stdscr, "Delete Domain", "No domains available to delete.")
            return
        
        # Select domain to delete
        domain_names = [d.name for d in self.manager.domains]
        selection = self._select_from_list(stdscr, "Select Domain to Delete", domain_names)
        
        if selection is None:
            return
        
        domain_name = domain_names[selection]
        
        if self._confirm_action(stdscr, f"Delete domain '{domain_name}'?\n\nThis will remove the NGINX configuration and disable the site."):
            # Show progress with proper timing
            stdscr.clear()
            stdscr.addstr(1, 2, "Deleting Domain...", curses.A_BOLD)
            stdscr.addstr(3, 2, "Please wait...", curses.A_DIM)
            stdscr.refresh()
            
            # Add a small delay to ensure the message is visible
            time.sleep(0.5)
            
            # Show detailed progress
            stdscr.addstr(5, 2, "- Disabling site...")
            stdscr.refresh()
            time.sleep(0.3)
            
            # Delete domain
            success, message = self.manager.delete_domain(domain_name)
            
            if success:
                stdscr.addstr(6, 2, "- Removing NGINX configuration...")
                stdscr.refresh()
                time.sleep(0.3)
                stdscr.addstr(7, 2, "- Reloading NGINX...")
                stdscr.refresh()
                time.sleep(0.5)
                
                self._show_message(stdscr, "Success", message)
            else:
                self._show_message(stdscr, "Error", message, True)
    
    def _nginx_status(self, stdscr):
        """Show NGINX status and management options"""
        stdscr.clear()
        stdscr.addstr(1, 2, "NGINX Status & Management")
        stdscr.addstr(2, 2, "=" * 25)
        
        # Get NGINX status
        is_active, status = self.manager.get_nginx_status()
        status_text = "Running" if is_active else "Stopped"
        status_attr = curses.A_NORMAL if is_active else curses.A_BOLD
        
        stdscr.addstr(4, 2, f"NGINX Status: ", curses.A_BOLD)
        stdscr.addstr(4, 16, status_text, status_attr)
        
        # Test configuration
        stdscr.addstr(6, 2, "Testing configuration...", curses.A_DIM)
        stdscr.refresh()
        
        test_success, test_output = self.manager.run_command("nginx -t")
        test_status = "Valid" if test_success else "Invalid"
        test_attr = curses.A_NORMAL if test_success else curses.A_BOLD
        
        stdscr.addstr(6, 2, f"Configuration: ")
        stdscr.addstr(6, 17, test_status, test_attr)
        
        if not test_success:
            stdscr.addstr(7, 2, "Error: ", curses.A_BOLD)
            stdscr.addstr(7, 9, test_output[:curses.COLS - 12])
        
        # Management options
        options = ["Reload NGINX", "Restart NGINX", "Test Configuration", "Back to Main Menu"]
        
        stdscr.addstr(9, 2, "Management Options:")
        for i, option in enumerate(options):
            stdscr.addstr(11 + i, 4, f"{i + 1}. {option}")
        
        stdscr.addstr(curses.LINES - 2, 2, "Select option (1-4): ")
        stdscr.refresh()
        
        time.sleep(0.5)
        # Flush input buffer
        stdscr.nodelay(True)
        while stdscr.getch() != -1:
            pass
        stdscr.nodelay(False)
        
        key = stdscr.getch()
        
        if key == ord('1'):  # Reload
            stdscr.clear()
            stdscr.addstr(1, 2, "Reloading NGINX...")
            stdscr.refresh()
            success, output = self.manager.run_command("systemctl reload nginx")
            message = "NGINX reloaded successfully" if success else f"Failed to reload NGINX: {output}"
            self._show_message(stdscr, "Reload Result", message, not success)
        
        elif key == ord('2'):  # Restart
            if self._confirm_action(stdscr, "Restart NGINX service?"):
                stdscr.clear()
                stdscr.addstr(1, 2, "Restarting NGINX...")
                stdscr.refresh()
                success, output = self.manager.restart_nginx()
                message = "NGINX restarted successfully" if success else f"Failed to restart NGINX: {output}"
                self._show_message(stdscr, "Restart Result", message, not success)
        
        elif key == ord('3'):  # Test
            stdscr.clear()
            stdscr.addstr(1, 2, "Testing NGINX Configuration")
            stdscr.addstr(2, 2, "=" * 28)
            success, output = self.manager.run_command("nginx -t")
            
            if success:
                stdscr.addstr(4, 2, "[OK] Configuration is valid", curses.A_BOLD)
            else:
                stdscr.addstr(4, 2, "[X] Configuration has errors:", curses.A_BOLD)
                lines = output.split('\n')
                for i, line in enumerate(lines[:10]):  # Show first 10 lines
                    stdscr.addstr(6 + i, 2, line[:curses.COLS - 4])
            
            stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
            self._wait_for_input(stdscr)
    
    def _backup_configurations(self, stdscr):
        """Backup configurations"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Backup Configurations")
        stdscr.addstr(2, 2, "=" * 21)
        
        if self._confirm_action(stdscr, "Create a full backup of all configurations?"):
            stdscr.clear()
            stdscr.addstr(1, 2, "Creating Backup...")
            stdscr.addstr(3, 2, "Please wait...")
            stdscr.refresh()
            
            success, message = self.manager.create_full_backup()
            
            if success:
                self._show_message(stdscr, "Success", message)
            else:
                self._show_message(stdscr, "Error", message, True)
    
    def _restore_backup(self, stdscr):
        """Restore from backup"""
        backups = self.manager.list_backups()
        
        if not backups:
            self._show_message(stdscr, "Restore Backup", "No backups available.")
            return
        
        selection = self._select_from_list(stdscr, "Select Backup to Restore", backups)
        
        if selection is None:
            return
        
        backup_name = backups[selection]
        
        if self._confirm_action(stdscr, f"Restore from backup '{backup_name}'?\n\nThis will overwrite current configurations."):
            self._show_message(stdscr, "Info", "Backup restore functionality would be implemented here.\nFor now, backups are stored in ~/manager/backups/")
    
    def _view_logs(self, stdscr):
        """View system logs"""
        log_options = [
            ("NGINX Error Log", "tail -n 50 /var/log/nginx/error.log"),
            ("NGINX Access Log", "tail -n 50 /var/log/nginx/access.log"),
            ("System Log (nginx)", "journalctl -u nginx -n 50 --no-pager"),
            ("Certbot Log", "tail -n 50 /var/log/letsencrypt/letsencrypt.log"),
            ("Manager Log", f"tail -n 50 {LOG_FILE}")
        ]
        
        log_names = [option[0] for option in log_options]
        selection = self._select_from_list(stdscr, "Select Log to View", log_names)
        
        if selection is None:
            return
        
        log_name, log_command = log_options[selection]
        
        stdscr.clear()
        stdscr.addstr(1, 2, f"Loading {log_name}...")
        stdscr.refresh()
        
        success, output = self.manager.run_command(log_command)
        
        if not success:
            self._show_message(stdscr, "Error", f"Failed to read log: {output}", True)
            return
        
        # Display log content
        lines = output.split('\n')
        current_line = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, f"{log_name} (Lines {current_line + 1}-{min(current_line + curses.LINES - 6, len(lines))})")
            stdscr.addstr(2, 2, "=" * (len(log_name) + 20))
            
            # Display lines
            display_lines = lines[current_line:current_line + curses.LINES - 6]
            for i, line in enumerate(display_lines):
                if i < curses.LINES - 6:
                    # Truncate long lines
                    display_line = line[:curses.COLS - 4] if len(line) > curses.COLS - 4 else line
                    stdscr.addstr(4 + i, 2, display_line)
            
            # Navigation info
            nav_info = "Up/Down: Scroll, q: Quit, r: Refresh"
            stdscr.addstr(curses.LINES - 2, 2, nav_info)
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == ord('q') or key == 27:  # q or ESC
                break
            elif key == ord('r'):  # Refresh
                stdscr.clear()
                stdscr.addstr(1, 2, f"Refreshing {log_name}...")
                stdscr.refresh()
                success, output = self.manager.run_command(log_command)
                if success:
                    lines = output.split('\n')
                    current_line = max(0, len(lines) - (curses.LINES - 6))  # Go to end
            elif key == curses.KEY_UP and current_line > 0:
                current_line -= 1
            elif key == curses.KEY_DOWN and current_line < len(lines) - (curses.LINES - 6):
                current_line += 1
            elif key == curses.KEY_PPAGE:  # Page Up
                current_line = max(0, current_line - (curses.LINES - 6))
            elif key == curses.KEY_NPAGE:  # Page Down
                current_line = min(len(lines) - (curses.LINES - 6), current_line + (curses.LINES - 6))
                current_line = max(0, current_line)
    
    def _onboarding_flow(self, stdscr):
        """First-time setup onboarding flow"""
        curses.curs_set(0)
        stdscr.keypad(True)
        
        # Welcome screen
        stdscr.clear()
        stdscr.addstr(1, 2, "Welcome to VPS NGINX Domain Manager!")
        stdscr.addstr(2, 2, "=" * 38)
        stdscr.addstr(4, 2, "This appears to be your first time running the manager.")
        stdscr.addstr(5, 2, "Let's set up some basic configuration.")
        stdscr.addstr(7, 2, "Press any key to continue...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
        
        # Collect email for Certbot
        stdscr.clear()
        stdscr.addstr(1, 2, "SSL Certificate Configuration")
        stdscr.addstr(2, 2, "=" * 29)
        stdscr.addstr(4, 2, "For SSL certificates, we need an email address for Let's Encrypt.")
        stdscr.addstr(5, 2, "This email will be used for certificate notifications.")
        stdscr.addstr(7, 2, "Leave empty to use domain-specific emails (admin@domain.com)")
        
        email = self._get_input(stdscr, "Email address", 9, 2)
        if email is None:  # User cancelled
            return
        if email:
            self.manager.config['certbot_email'] = email
        
        # Ask about auto-backup
        stdscr.clear()
        stdscr.addstr(1, 2, "Backup Configuration")
        stdscr.addstr(2, 2, "=" * 20)
        stdscr.addstr(4, 2, "Would you like to enable automatic backups before making changes?")
        
        auto_backup = self._get_input(stdscr, "Enable auto-backup? (y/N)", 6, 2, "y")
        if auto_backup is None:  # User cancelled
            return
        self.manager.config['auto_backup'] = auto_backup.lower() in ['y', 'yes']
        
        # Ask about default SSL
        stdscr.clear()
        stdscr.addstr(1, 2, "Default SSL Setting")
        stdscr.addstr(2, 2, "=" * 19)
        stdscr.addstr(4, 2, "Would you like SSL to be enabled by default for new domains?")
        
        default_ssl = self._get_input(stdscr, "Enable SSL by default? (Y/n)", 6, 2, "y")
        if default_ssl is None:  # User cancelled
            return
        self.manager.config['default_ssl'] = default_ssl.lower() not in ['n', 'no']
        
        # Ask about auto-update
        stdscr.clear()
        stdscr.addstr(1, 2, "Auto-Update Configuration")
        stdscr.addstr(2, 2, "=" * 25)
        stdscr.addstr(4, 2, "Would you like to enable automatic update checking?")
        stdscr.addstr(5, 2, "This will check for new versions when the application starts.")
        
        auto_update = self._get_input(stdscr, "Enable auto-update? (Y/n)", 7, 2, "y")
        if auto_update is None:  # User cancelled
            return
        self.manager.config['auto_update'] = auto_update.lower() not in ['n', 'no']
        
        # Summary and confirmation
        stdscr.clear()
        stdscr.addstr(1, 2, "Configuration Summary")
        stdscr.addstr(2, 2, "=" * 21)
        
        y_pos = 4
        stdscr.addstr(y_pos, 2, f"Email for SSL: {self.manager.config.get('certbot_email', 'Domain-specific')}")
        y_pos += 1
        stdscr.addstr(y_pos, 2, f"Auto-backup: {'Yes' if self.manager.config.get('auto_backup', False) else 'No'}")
        y_pos += 1
        stdscr.addstr(y_pos, 2, f"Default SSL: {'Yes' if self.manager.config.get('default_ssl', True) else 'No'}")
        y_pos += 1
        stdscr.addstr(y_pos, 2, f"Auto-update: {'Yes' if self.manager.config.get('auto_update', True) else 'No'}")
        y_pos += 2
        
        stdscr.addstr(y_pos, 2, "Press any key to save configuration and continue...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
        
        # Save configuration and mark setup as complete
        self.manager.complete_setup()
        
        # Show completion message
        stdscr.clear()
        stdscr.addstr(1, 2, "Setup Complete!")
        stdscr.addstr(2, 2, "=" * 15)
        stdscr.addstr(4, 2, "Configuration has been saved successfully.")
        stdscr.addstr(5, 2, "You can change these settings later from the Settings menu.")
        stdscr.addstr(7, 2, "Press any key to continue to the main menu...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
    
    def _selective_onboarding_flow(self, stdscr, missing_options: List[str]):
        """Selective onboarding flow for new configuration options"""
        curses.curs_set(0)
        stdscr.keypad(True)
        
        # Welcome screen for selective onboarding
        stdscr.clear()
        stdscr.addstr(1, 2, "New Configuration Options Available!")
        stdscr.addstr(2, 2, "=" * 36)
        stdscr.addstr(4, 2, "The VPS Manager has been updated with new features.")
        stdscr.addstr(5, 2, "Let's configure the new options.")
        stdscr.addstr(7, 2, "Press any key to continue...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
        
        # Handle each missing option
        for option in missing_options:
            if option == 'auto_update':
                self._configure_auto_update_option(stdscr)
            # Add more options here as they are introduced in future versions
        
        # Show completion message
        stdscr.clear()
        stdscr.addstr(1, 2, "Configuration Updated!")
        stdscr.addstr(2, 2, "=" * 22)
        stdscr.addstr(4, 2, "New configuration options have been set successfully.")
        stdscr.addstr(5, 2, "You can change these settings later from the Settings menu.")
        stdscr.addstr(7, 2, "Press any key to continue...")
        stdscr.refresh()
        self._wait_for_input(stdscr)
        
        # Update config version after selective onboarding
        self.manager.update_config_version()
    
    def _configure_auto_update_option(self, stdscr):
        """Configure the auto-update option during selective onboarding"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Auto-Update Configuration")
        stdscr.addstr(2, 2, "=" * 25)
        stdscr.addstr(4, 2, "NEW FEATURE: Automatic Update Checking")
        stdscr.addstr(6, 2, "Would you like to enable automatic update checking?")
        stdscr.addstr(7, 2, "This will check for new versions when the application starts.")
        stdscr.addstr(8, 2, "You can always change this setting later.")
        
        auto_update = self._get_input(stdscr, "Enable auto-update? (Y/n)", 10, 2, "y")
        if auto_update is None:  # User cancelled, set default
            auto_update = "y"
        self.manager.config['auto_update'] = auto_update.lower() not in ['n', 'no']
        self.manager.save_config()
    
    def _settings_menu(self, stdscr):
        """Settings management menu"""
        settings_options = [
            "Change Certbot Email",
            "Toggle Auto-backup",
            "Toggle Default SSL",
            "Toggle Auto-update",
            "Check for Updates",
            "Configure Alerts & Notifications",
            "Configure Firewall Settings",
            "Configure Security Scanner",
            "Configure Docker Integration",
            "Configure Version Control",
            "View Current Settings",
            "Reset to Defaults",
            "Back to Main Menu"
        ]
        
        current_selection = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, "Settings Menu")
            stdscr.addstr(2, 2, "=" * 13)
            
            for i, option in enumerate(settings_options):
                if i == current_selection:
                    stdscr.addstr(4 + i, 4, f"> {option}", curses.A_REVERSE)
                else:
                    stdscr.addstr(4 + i, 4, f"  {option}")
            
            stdscr.addstr(curses.LINES - 2, 2, "Use Up/Down to navigate, Enter to select")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(settings_options) - 1:
                current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if current_selection == 0:  # Change Certbot Email
                    self._change_certbot_email(stdscr)
                elif current_selection == 1:  # Toggle Auto-backup
                    self._toggle_auto_backup(stdscr)
                elif current_selection == 2:  # Toggle Default SSL
                    self._toggle_default_ssl(stdscr)
                elif current_selection == 3:  # Toggle Auto-update
                    self._toggle_auto_update(stdscr)
                elif current_selection == 4:  # Check for Updates
                    self._manual_update_check(stdscr)
                elif current_selection == 5:  # Configure Alerts
                    self._configure_alerts(stdscr)
                elif current_selection == 6:  # Configure Firewall
                    self._configure_firewall_setup(stdscr)
                elif current_selection == 7:  # Configure Security
                    self._configure_security_setup(stdscr)
                elif current_selection == 8:  # Configure Docker
                    self._configure_docker_setup(stdscr)
                elif current_selection == 9:  # Configure Version Control
                    self._enable_version_control(stdscr)
                elif current_selection == 10:  # View Current Settings
                    self._view_current_settings(stdscr)
                elif current_selection == 11:  # Reset to Defaults
                    self._reset_settings(stdscr)
                elif current_selection == 12:  # Back
                    break
            elif key == 27:  # ESC
                break
    
    def _change_certbot_email(self, stdscr):
        """Change Certbot email setting"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Change Certbot Email")
        stdscr.addstr(2, 2, "=" * 20)
        
        current_email = self.manager.config.get('certbot_email', 'Not set')
        stdscr.addstr(4, 2, f"Current email: {current_email}")
        
        new_email = self._get_input(stdscr, "New email address", 6, 2)
        
        if new_email:
            self.manager.config['certbot_email'] = new_email
            self.manager.save_config()
            self._show_message(stdscr, "Success", "Email address updated successfully.")
    
    def _toggle_auto_backup(self, stdscr):
        """Toggle auto-backup setting"""
        current = self.manager.config.get('auto_backup', False)
        new_value = not current
        self.manager.config['auto_backup'] = new_value
        self.manager.save_config()
        
        status = "enabled" if new_value else "disabled"
        self._show_message(stdscr, "Success", f"Auto-backup has been {status}.")
    
    def _toggle_default_ssl(self, stdscr):
        """Toggle default SSL setting"""
        current = self.manager.config.get('default_ssl', True)
        new_value = not current
        self.manager.config['default_ssl'] = new_value
        self.manager.save_config()
        
        status = "enabled" if new_value else "disabled"
        self._show_message(stdscr, "Success", f"Default SSL has been {status}.")
    
    def _toggle_auto_update(self, stdscr):
        """Toggle auto-update setting"""
        current = self.manager.config.get('auto_update', True)
        new_value = not current
        self.manager.config['auto_update'] = new_value
        self.manager.save_config()
        
        status = "enabled" if new_value else "disabled"
        self._show_message(stdscr, "Success", f"Auto-update has been {status}.")
    
    def _manual_update_check(self, stdscr):
        """Manually check for updates"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Checking for Updates...")
        stdscr.refresh()
        
        has_update, current, latest = self.manager.check_for_updates()
        
        if has_update:
            if self._confirm_action(stdscr, f"Update available: {latest} (Current: {current})\n\nDownload and install update?"):
                stdscr.clear()
                stdscr.addstr(1, 2, "Downloading Update...")
                stdscr.refresh()
                
                # Note: In the package version, we might want to just tell them to pip install --upgrade
                # But for now, let's just show a message since self-update is tricky
                self._show_message(stdscr, "Update Available", f"Please run 'pip install --upgrade vps-manager' to update to version {latest}.")
        else:
            self._show_message(stdscr, "No Updates", f"You are running the latest version ({current}).")
    
    def _view_current_settings(self, stdscr):
        """View current configuration settings"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Current Settings")
        stdscr.addstr(2, 2, "=" * 16)
        
        config = self.manager.config
        app_config = self.manager.config_manager.config
        y = 4
        
        # Legacy settings
        stdscr.addstr(y, 2, "General Settings:", curses.A_BOLD)
        y += 1
        for key, value in config.items():
            if y < curses.LINES - 4:
                stdscr.addstr(y, 4, f"{key}: {value}")
                y += 1
        
        y += 1
        if y < curses.LINES - 4:
            stdscr.addstr(y, 2, "Feature Configuration:", curses.A_BOLD)
            y += 1
            
            # Alerts
            status = "Enabled" if app_config.alerts.enabled else "Disabled"
            stdscr.addstr(y, 4, f"Alerts & Monitoring: {status}")
            y += 1
            if app_config.alerts.enabled:
                channels = []
                if app_config.alerts.email.enabled:
                    channels.append("Email")
                if app_config.alerts.slack.enabled:
                    channels.append("Slack")
                if app_config.alerts.discord.enabled:
                    channels.append("Discord")
                if app_config.alerts.webhook.enabled:
                    channels.append("Webhook")
                if channels:
                    stdscr.addstr(y, 6, f"Channels: {', '.join(channels)}")
                    y += 1
            
            # Firewall
            status = "Enabled" if app_config.firewall.enabled else "Disabled"
            stdscr.addstr(y, 4, f"Firewall Management: {status}")
            y += 1
            
            # Security
            status = "Enabled" if app_config.security.enabled else "Disabled"
            stdscr.addstr(y, 4, f"Security Scanner: {status}")
            y += 1
            if app_config.security.auto_scan_on_startup:
                stdscr.addstr(y, 6, "Auto-scan: Yes")
                y += 1
            
            # Docker
            status = "Enabled" if app_config.docker.enabled else "Disabled"
            stdscr.addstr(y, 4, f"Docker Integration: {status}")
            y += 1
            if app_config.docker.auto_discover:
                stdscr.addstr(y, 6, "Auto-discover: Yes")
                y += 1
            
            # Version Control
            status = "Enabled" if app_config.version_control.enabled else "Disabled"
            stdscr.addstr(y, 4, f"Version Control: {status}")
            y += 1
            if app_config.version_control.auto_commit:
                stdscr.addstr(y, 6, "Auto-commit: Yes")
                y += 1
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _reset_settings(self, stdscr):
        """Reset settings to defaults"""
        if self._confirm_action(stdscr, "Reset all settings to defaults?\n\nThis will not affect your domains."):
            self.manager.config = {}
            self.manager.save_config()
            self._show_message(stdscr, "Success", "Settings have been reset to defaults.")
    
    # ==================== NEW FEATURES ====================
    
    def _firewall_management(self, stdscr):
        """Firewall management menu"""
        # Check if UFW is installed
        is_installed, msg = self.manager.firewall.is_installed()
        if not is_installed:
            self._show_message(stdscr, "UFW Not Installed", 
                             f"{msg}\n\nInstall with: sudo apt install ufw", True)
            return
        
        menu_items = [
            "View Firewall Status",
            "Enable Firewall",
            "Disable Firewall",
            "Allow Port",
            "Deny Port",
            "Limit Port (Rate Limit)",
            "Delete Rule",
            "Allow from IP",
            "Deny from IP",
            "Quick Setup (Web Server)",
            "List All Rules",
            "Back to Main Menu"
        ]
        
        current_selection = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, "Firewall Management (UFW)")
            stdscr.addstr(2, 2, "=" * 26)
            
            # Show current status
            success, output, is_active = self.manager.firewall.get_status()
            status_text = "ACTIVE" if is_active else "INACTIVE"
            status_attr = curses.A_NORMAL if is_active else curses.A_DIM
            stdscr.addstr(4, 2, f"Status: ", curses.A_BOLD)
            stdscr.addstr(4, 10, status_text, status_attr)
            
            # Draw menu
            for i, item in enumerate(menu_items):
                if i == current_selection:
                    stdscr.addstr(6 + i, 4, f"> {item}", curses.A_REVERSE)
                else:
                    stdscr.addstr(6 + i, 4, f"  {item}")
            
            stdscr.addstr(curses.LINES - 2, 2, "Use Up/Down to navigate, Enter to select, ESC to go back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(menu_items) - 1:
                current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if current_selection == 0:  # View Status
                    self._firewall_view_status(stdscr)
                elif current_selection == 1:  # Enable
                    success, msg = self.manager.firewall.enable()
                    self._show_message(stdscr, "Firewall", msg, not success)
                elif current_selection == 2:  # Disable
                    if self._confirm_action(stdscr, "Disable firewall? This may expose your server."):
                        success, msg = self.manager.firewall.disable()
                        self._show_message(stdscr, "Firewall", msg, not success)
                elif current_selection == 3:  # Allow Port
                    self._firewall_allow_port(stdscr)
                elif current_selection == 4:  # Deny Port
                    self._firewall_deny_port(stdscr)
                elif current_selection == 5:  # Limit Port
                    self._firewall_limit_port(stdscr)
                elif current_selection == 6:  # Delete Rule
                    self._firewall_delete_rule(stdscr)
                elif current_selection == 7:  # Allow from IP
                    self._firewall_allow_ip(stdscr)
                elif current_selection == 8:  # Deny from IP
                    self._firewall_deny_ip(stdscr)
                elif current_selection == 9:  # Quick Setup
                    if self._confirm_action(stdscr, "Configure firewall for web server?\n\nThis will allow ports 22, 80, 443"):
                        success, msg = self.manager.firewall.quick_setup_web_server()
                        self._show_message(stdscr, "Quick Setup", msg, not success)
                elif current_selection == 10:  # List Rules
                    self._firewall_list_rules(stdscr)
                elif current_selection == 11:  # Back
                    break
            elif key == 27:  # ESC
                break
    
    def _firewall_view_status(self, stdscr):
        """View detailed firewall status"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Firewall Status")
        stdscr.addstr(2, 2, "=" * 15)
        
        success, output, is_active = self.manager.firewall.get_status()
        
        if success:
            lines = output.split('\n')
            for i, line in enumerate(lines[:curses.LINES - 6]):
                stdscr.addstr(4 + i, 2, line[:curses.COLS - 4])
        
        policies = self.manager.firewall.get_default_policies()
        y = min(len(lines) + 5, curses.LINES - 8)
        stdscr.addstr(y, 2, f"Default Policies:", curses.A_BOLD)
        stdscr.addstr(y + 1, 2, f"  Incoming: {policies['incoming']}")
        stdscr.addstr(y + 2, 2, f"  Outgoing: {policies['outgoing']}")
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _firewall_allow_port(self, stdscr):
        """Allow a port through firewall"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Allow Port")
        stdscr.addstr(2, 2, "=" * 10)
        
        port_str = self._get_input(stdscr, "Port number", 4, 2)
        if port_str is None:
            return
        
        try:
            port = int(port_str)
        except ValueError:
            self._show_message(stdscr, "Error", "Invalid port number", True)
            return
        
        protocol = self._get_input(stdscr, "Protocol (tcp/udp)", 5, 2, "tcp")
        if protocol is None:
            return
        
        comment = self._get_input(stdscr, "Comment (optional)", 6, 2, "")
        
        success, msg = self.manager.firewall.allow_port(port, protocol, comment or None)
        self._show_message(stdscr, "Allow Port", msg, not success)
    
    def _firewall_deny_port(self, stdscr):
        """Deny a port through firewall"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Deny Port")
        stdscr.addstr(2, 2, "=" * 9)
        
        port_str = self._get_input(stdscr, "Port number", 4, 2)
        if port_str is None:
            return
        
        try:
            port = int(port_str)
        except ValueError:
            self._show_message(stdscr, "Error", "Invalid port number", True)
            return
        
        protocol = self._get_input(stdscr, "Protocol (tcp/udp)", 5, 2, "tcp")
        if protocol is None:
            return
        
        success, msg = self.manager.firewall.deny_port(port, protocol)
        self._show_message(stdscr, "Deny Port", msg, not success)
    
    def _firewall_limit_port(self, stdscr):
        """Rate limit a port"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Rate Limit Port")
        stdscr.addstr(2, 2, "=" * 15)
        stdscr.addstr(4, 2, "Rate limiting prevents brute-force attacks (max 6 connections/30 sec)")
        
        port_str = self._get_input(stdscr, "Port number", 6, 2)
        if port_str is None:
            return
        
        try:
            port = int(port_str)
        except ValueError:
            self._show_message(stdscr, "Error", "Invalid port number", True)
            return
        
        protocol = self._get_input(stdscr, "Protocol (tcp/udp)", 7, 2, "tcp")
        if protocol is None:
            return
        
        success, msg = self.manager.firewall.limit_port(port, protocol)
        self._show_message(stdscr, "Limit Port", msg, not success)
    
    def _firewall_delete_rule(self, stdscr):
        """Delete a firewall rule"""
        success, rules = self.manager.firewall.list_rules()
        if not success or not rules:
            self._show_message(stdscr, "Delete Rule", "No rules to delete")
            return
        
        rule_strings = [str(rule) for rule in rules]
        selection = self._select_from_list(stdscr, "Select Rule to Delete", rule_strings)
        
        if selection is not None:
            rule = rules[selection]
            if self._confirm_action(stdscr, f"Delete rule {rule.number}?\n\n{rule}"):
                success, msg = self.manager.firewall.delete_rule(rule.number)
                self._show_message(stdscr, "Delete Rule", msg, not success)
    
    def _firewall_allow_ip(self, stdscr):
        """Allow traffic from specific IP"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Allow from IP")
        stdscr.addstr(2, 2, "=" * 13)
        
        ip = self._get_input(stdscr, "IP address", 4, 2)
        if ip is None:
            return
        
        success, msg = self.manager.firewall.allow_from_ip(ip)
        self._show_message(stdscr, "Allow IP", msg, not success)
    
    def _firewall_deny_ip(self, stdscr):
        """Deny traffic from specific IP"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Deny from IP")
        stdscr.addstr(2, 2, "=" * 12)
        
        ip = self._get_input(stdscr, "IP address", 4, 2)
        if ip is None:
            return
        
        success, msg = self.manager.firewall.deny_from_ip(ip)
        self._show_message(stdscr, "Deny IP", msg, not success)
    
    def _firewall_list_rules(self, stdscr):
        """List all firewall rules"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Firewall Rules")
        stdscr.addstr(2, 2, "=" * 14)
        
        success, rules = self.manager.firewall.list_rules()
        
        if not success or not rules:
            stdscr.addstr(4, 2, "No rules configured")
        else:
            stdscr.addstr(4, 2, f"Total Rules: {len(rules)}")
            stdscr.addstr(5, 2, "-" * 60)
            
            for i, rule in enumerate(rules[:curses.LINES - 10]):
                stdscr.addstr(6 + i, 2, str(rule)[:curses.COLS - 4])
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _security_scanner(self, stdscr):
        """Security scanning and hardening"""
        menu_items = [
            "Run Security Scan",
            "View Last Scan Results",
            "Apply Security Headers (Domain)",
            "View Security Score",
            "Export Security Report",
            "Back to Main Menu"
        ]
        
        current_selection = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, "Security Scanner")
            stdscr.addstr(2, 2, "=" * 16)
            
            # Show security score if available
            if hasattr(self.manager.security, 'issues') and self.manager.security.issues:
                score = self.manager.security.get_security_score()
                score_color = curses.A_NORMAL
                if score < 50:
                    score_color = curses.A_BOLD
                stdscr.addstr(4, 2, f"Security Score: ", curses.A_BOLD)
                stdscr.addstr(4, 18, f"{score}/100", score_color)
            
            # Draw menu
            start_y = 6
            for i, item in enumerate(menu_items):
                if i == current_selection:
                    stdscr.addstr(start_y + i, 4, f"> {item}", curses.A_REVERSE)
                else:
                    stdscr.addstr(start_y + i, 4, f"  {item}")
            
            stdscr.addstr(curses.LINES - 2, 2, "Use Up/Down to navigate, Enter to select, ESC to go back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(menu_items) - 1:
                current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if current_selection == 0:  # Run Scan
                    self._security_run_scan(stdscr)
                elif current_selection == 1:  # View Results
                    self._security_view_results(stdscr)
                elif current_selection == 2:  # Apply Headers
                    self._security_apply_headers(stdscr)
                elif current_selection == 3:  # View Score
                    self._security_view_score(stdscr)
                elif current_selection == 4:  # Export Report
                    self._security_export_report(stdscr)
                elif current_selection == 5:  # Back
                    break
            elif key == 27:  # ESC
                break
    
    def _security_run_scan(self, stdscr):
        """Run security scan"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Running Security Scan...", curses.A_BOLD)
        stdscr.addstr(3, 2, "Please wait, this may take a minute...")
        stdscr.refresh()
        
        # Run scan
        issues = self.manager.security.scan_all()
        
        # Show summary
        stdscr.clear()
        stdscr.addstr(1, 2, "Security Scan Complete", curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * 22)
        
        grouped = self.manager.security.get_issues_by_severity()
        score = self.manager.security.get_security_score()
        
        y = 4
        stdscr.addstr(y, 2, f"Security Score: {score}/100")
        y += 1
        stdscr.addstr(y, 2, f"Total Issues: {len(issues)}")
        y += 2
        
        from .security import SecurityIssue
        for severity in [SecurityIssue.SEVERITY_CRITICAL, SecurityIssue.SEVERITY_HIGH,
                        SecurityIssue.SEVERITY_MEDIUM, SecurityIssue.SEVERITY_LOW]:
            count = len(grouped[severity])
            if count > 0:
                stdscr.addstr(y, 2, f"{severity}: {count}")
                y += 1
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to view details...")
        self._wait_for_input(stdscr)
        
        # Show detailed results
        self._security_view_results(stdscr)
    
    def _security_view_results(self, stdscr):
        """View security scan results"""
        if not hasattr(self.manager.security, 'issues') or not self.manager.security.issues:
            self._show_message(stdscr, "Security Scan", "No scan results available. Run a scan first.")
            return
        
        issues = self.manager.security.issues
        current_issue = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, f"Security Issues ({current_issue + 1}/{len(issues)})")
            stdscr.addstr(2, 2, "=" * 40)
            
            issue = issues[current_issue]
            
            y = 4
            stdscr.addstr(y, 2, f"Severity: {issue.severity}", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 2, f"Category: {issue.category}")
            y += 2
            stdscr.addstr(y, 2, f"Title:", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 2, issue.title)
            y += 2
            stdscr.addstr(y, 2, f"Description:", curses.A_BOLD)
            y += 1
            
            # Wrap description
            desc_lines = []
            words = issue.description.split()
            current_line = ""
            for word in words:
                if len(current_line + word) < curses.COLS - 6:
                    current_line += word + " "
                else:
                    desc_lines.append(current_line)
                    current_line = word + " "
            if current_line:
                desc_lines.append(current_line)
            
            for line in desc_lines:
                stdscr.addstr(y, 2, line)
                y += 1
            
            y += 1
            stdscr.addstr(y, 2, f"Recommendation:", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 2, issue.recommendation)
            
            stdscr.addstr(curses.LINES - 2, 2, "Left/Right: Navigate | ESC/Q: Back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_LEFT and current_issue > 0:
                current_issue -= 1
            elif key == curses.KEY_RIGHT and current_issue < len(issues) - 1:
                current_issue += 1
            elif key == 27 or key == ord('q'):
                break
    
    def _security_apply_headers(self, stdscr):
        """Apply security headers to a domain"""
        if not self.manager.domains:
            self._show_message(stdscr, "Apply Headers", "No domains configured")
            return
        
        domain_names = [d.name for d in self.manager.domains]
        selection = self._select_from_list(stdscr, "Select Domain", domain_names)
        
        if selection is not None:
            domain_name = domain_names[selection]
            
            if self._confirm_action(stdscr, f"Apply security headers to {domain_name}?"):
                from .security import SecurityHardening
                hardening = SecurityHardening(self.manager)
                success, msg = hardening.apply_nginx_security_headers(domain_name)
                self._show_message(stdscr, "Apply Headers", msg, not success)
    
    def _security_view_score(self, stdscr):
        """View security score breakdown"""
        if not hasattr(self.manager.security, 'issues'):
            self._show_message(stdscr, "Security Score", "Run a security scan first")
            return
        
        stdscr.clear()
        stdscr.addstr(1, 2, "Security Score Breakdown")
        stdscr.addstr(2, 2, "=" * 24)
        
        score = self.manager.security.get_security_score()
        grouped = self.manager.security.get_issues_by_severity()
        
        y = 4
        stdscr.addstr(y, 2, f"Overall Score: {score}/100", curses.A_BOLD)
        y += 2
        
        from .security import SecurityIssue
        stdscr.addstr(y, 2, "Issues by Severity:")
        y += 1
        
        for severity in [SecurityIssue.SEVERITY_CRITICAL, SecurityIssue.SEVERITY_HIGH,
                        SecurityIssue.SEVERITY_MEDIUM, SecurityIssue.SEVERITY_LOW]:
            count = len(grouped[severity])
            stdscr.addstr(y, 4, f"{severity}: {count}")
            y += 1
        
        y += 1
        stdscr.addstr(y, 2, "Score Interpretation:")
        y += 1
        stdscr.addstr(y, 4, "90-100: Excellent security posture")
        y += 1
        stdscr.addstr(y, 4, "70-89:  Good, minor improvements needed")
        y += 1
        stdscr.addstr(y, 4, "50-69:  Fair, several issues to address")
        y += 1
        stdscr.addstr(y, 4, "0-49:   Poor, immediate action required")
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _security_export_report(self, stdscr):
        """Export security report to file"""
        if not hasattr(self.manager.security, 'issues'):
            self._show_message(stdscr, "Export Report", "Run a security scan first")
            return
        
        report = self.manager.security.generate_report()
        report_file = MANAGER_DIR / f"security_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        try:
            with open(report_file, 'w') as f:
                f.write(report)
            self._show_message(stdscr, "Export Report", f"Report saved to:\n{report_file}")
        except Exception as e:
            self._show_message(stdscr, "Error", f"Failed to export report: {e}", True)
    
    def _alerts_monitoring(self, stdscr):
        """Alerts and monitoring menu"""
        menu_items = [
            "View Active Alerts",
            "Run All Checks Now",
            "Acknowledge Alert",
            "Clear Old Alerts",
            "Configure Notifications",
            "Test Notification",
            "Back to Main Menu"
        ]
        
        current_selection = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, "Alerts & Monitoring")
            stdscr.addstr(2, 2, "=" * 19)
            
            # Show alert count
            unack_alerts = self.manager.alerts.get_unacknowledged_alerts()
            alert_count = len(unack_alerts)
            
            if alert_count > 0:
                stdscr.addstr(4, 2, f"Unacknowledged Alerts: {alert_count}", curses.A_BOLD)
            else:
                stdscr.addstr(4, 2, "No active alerts")
            
            # Draw menu
            start_y = 6
            for i, item in enumerate(menu_items):
                if i == current_selection:
                    stdscr.addstr(start_y + i, 4, f"> {item}", curses.A_REVERSE)
                else:
                    stdscr.addstr(start_y + i, 4, f"  {item}")
            
            stdscr.addstr(curses.LINES - 2, 2, "Use Up/Down to navigate, Enter to select, ESC to go back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(menu_items) - 1:
                current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if current_selection == 0:  # View Alerts
                    self._alerts_view_active(stdscr)
                elif current_selection == 1:  # Run Checks
                    self._alerts_run_checks(stdscr)
                elif current_selection == 2:  # Acknowledge
                    self._alerts_acknowledge(stdscr)
                elif current_selection == 3:  # Clear Old
                    self._alerts_clear_old(stdscr)
                elif current_selection == 4:  # Configure
                    self._alerts_configure_notifications(stdscr)
                elif current_selection == 5:  # Test
                    self._alerts_test_notification(stdscr)
                elif current_selection == 6:  # Back
                    break
            elif key == 27:  # ESC
                break
    
    def _alerts_view_active(self, stdscr):
        """View active alerts"""
        alerts = self.manager.alerts.get_unacknowledged_alerts()
        
        if not alerts:
            self._show_message(stdscr, "Active Alerts", "No active alerts")
            return
        
        current_alert = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, f"Active Alerts ({current_alert + 1}/{len(alerts)})")
            stdscr.addstr(2, 2, "=" * 40)
            
            alert = alerts[current_alert]
            
            y = 4
            stdscr.addstr(y, 2, f"Level: {alert.level.value.upper()}", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 2, f"Type: {alert.alert_type.value}")
            y += 1
            stdscr.addstr(y, 2, f"Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            y += 2
            stdscr.addstr(y, 2, f"Title:", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 2, alert.title)
            y += 2
            stdscr.addstr(y, 2, f"Message:", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 2, alert.message)
            
            if alert.details:
                y += 2
                stdscr.addstr(y, 2, f"Details:", curses.A_BOLD)
                y += 1
                for key, value in alert.details.items():
                    stdscr.addstr(y, 4, f"{key}: {value}")
                    y += 1
            
            stdscr.addstr(curses.LINES - 2, 2, "Left/Right: Navigate | A: Acknowledge | ESC/Q: Back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_LEFT and current_alert > 0:
                current_alert -= 1
            elif key == curses.KEY_RIGHT and current_alert < len(alerts) - 1:
                current_alert += 1
            elif key == ord('a') or key == ord('A'):
                self.manager.alerts.acknowledge_alert(alert)
                alerts = self.manager.alerts.get_unacknowledged_alerts()
                if not alerts:
                    self._show_message(stdscr, "Alerts", "All alerts acknowledged")
                    break
                current_alert = min(current_alert, len(alerts) - 1)
            elif key == 27 or key == ord('q'):
                break
    
    def _alerts_run_checks(self, stdscr):
        """Run all monitoring checks"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Running Monitoring Checks...", curses.A_BOLD)
        stdscr.addstr(3, 2, "Please wait...")
        stdscr.refresh()
        
        self.manager.alerts.run_all_checks()
        
        new_alerts = self.manager.alerts.get_unacknowledged_alerts()
        self._show_message(stdscr, "Monitoring Checks", 
                          f"Checks complete.\n{len(new_alerts)} unacknowledged alerts.")
    
    def _alerts_acknowledge(self, stdscr):
        """Acknowledge an alert"""
        alerts = self.manager.alerts.get_unacknowledged_alerts()
        
        if not alerts:
            self._show_message(stdscr, "Acknowledge", "No alerts to acknowledge")
            return
        
        alert_strings = [f"[{a.level.value.upper()}] {a.title}" for a in alerts]
        selection = self._select_from_list(stdscr, "Select Alert to Acknowledge", alert_strings)
        
        if selection is not None:
            self.manager.alerts.acknowledge_alert(alerts[selection])
            self._show_message(stdscr, "Acknowledge", "Alert acknowledged")
    
    def _alerts_clear_old(self, stdscr):
        """Clear old acknowledged alerts"""
        days_str = self._get_input(stdscr, "Clear alerts older than (days)", 4, 2, "30")
        if days_str is None:
            return
        
        try:
            days = int(days_str)
        except ValueError:
            self._show_message(stdscr, "Error", "Invalid number of days", True)
            return
        
        if self._confirm_action(stdscr, f"Clear alerts older than {days} days?"):
            self.manager.alerts.clear_old_alerts(days)
            self._show_message(stdscr, "Clear Old Alerts", "Old alerts cleared")
    
    def _alerts_configure_notifications(self, stdscr):
        """Configure notification channels"""
        self._show_message(stdscr, "Configure Notifications",
                          f"Edit notification configuration at:\n{MANAGER_DIR / 'alert_config.json'}\n\n"
                          "Supports: Email, Slack, Discord, Custom Webhooks, Commands")
    
    def _alerts_test_notification(self, stdscr):
        """Send test notification"""
        from .alerts import Alert, AlertType, AlertLevel
        
        test_alert = Alert(
            AlertType.SYSTEM_UPDATE,
            AlertLevel.INFO,
            "Test Notification",
            "This is a test notification from VPS Manager",
            {"test": True}
        )
        
        # Try to send through configured channels
        for channel in self.manager.alerts.notification_channels:
            try:
                success, msg = channel.send(test_alert)
                self._show_message(stdscr, "Test Notification", 
                                  f"Channel: {channel.__class__.__name__}\n{msg}",
                                  not success)
                return
            except Exception as e:
                self._show_message(stdscr, "Test Failed", str(e), True)
                return
        
        self._show_message(stdscr, "Test Notification", 
                          "No notification channels configured.\nConfigure in alert_config.json")
    
    def _docker_integration(self, stdscr):
        """Docker integration menu"""
        # Check if Docker is installed
        is_installed, msg = self.manager.docker.is_installed()
        if not is_installed:
            self._show_message(stdscr, "Docker Not Available", 
                             f"{msg}\n\nInstall with: curl -fsSL https://get.docker.com | sh", True)
            return
        
        menu_items = [
            "List Running Containers",
            "Auto-Configure Container",
            "Scan & Suggest Configs",
            "Container Details",
            "Container Logs",
            "Start Container",
            "Stop Container",
            "Restart Container",
            "Back to Main Menu"
        ]
        
        current_selection = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, "Docker Integration")
            stdscr.addstr(2, 2, "=" * 17)
            
            # Show Docker version
            success, version = self.manager.docker.get_version()
            if success:
                stdscr.addstr(4, 2, f"Docker: {version}")
            
            # Draw menu
            start_y = 6
            for i, item in enumerate(menu_items):
                if i == current_selection:
                    stdscr.addstr(start_y + i, 4, f"> {item}", curses.A_REVERSE)
                else:
                    stdscr.addstr(start_y + i, 4, f"  {item}")
            
            stdscr.addstr(curses.LINES - 2, 2, "Use Up/Down to navigate, Enter to select, ESC to go back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(menu_items) - 1:
                current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if current_selection == 0:  # List Containers
                    self._docker_list_containers(stdscr)
                elif current_selection == 1:  # Auto-Configure
                    self._docker_auto_configure(stdscr)
                elif current_selection == 2:  # Scan & Suggest
                    self._docker_scan_suggest(stdscr)
                elif current_selection == 3:  # Container Details
                    self._docker_container_details(stdscr)
                elif current_selection == 4:  # Container Logs
                    self._docker_container_logs(stdscr)
                elif current_selection == 5:  # Start
                    self._docker_start_container(stdscr)
                elif current_selection == 6:  # Stop
                    self._docker_stop_container(stdscr)
                elif current_selection == 7:  # Restart
                    self._docker_restart_container(stdscr)
                elif current_selection == 8:  # Back
                    break
            elif key == 27:  # ESC
                break
    
    def _docker_list_containers(self, stdscr):
        """List Docker containers"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Docker Containers")
        stdscr.addstr(2, 2, "=" * 17)
        
        success, containers = self.manager.docker.list_containers()
        
        if not success or not containers:
            stdscr.addstr(4, 2, "No running containers found")
        else:
            stdscr.addstr(4, 2, f"Name".ljust(20) + "Image".ljust(25) + "Status".ljust(15) + "Ports")
            stdscr.addstr(5, 2, "-" * 75)
            
            for i, container in enumerate(containers[:curses.LINES - 10]):
                name = container.name[:19]
                image = container.image[:24]
                status = container.status[:14]
                ports = str(container.get_external_port() or "") or "-"
                
                line = f"{name.ljust(20)}{image.ljust(25)}{status.ljust(15)}{ports}"
                stdscr.addstr(6 + i, 2, line[:curses.COLS - 4])
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _docker_auto_configure(self, stdscr):
        """Auto-configure NGINX for a Docker container"""
        success, containers = self.manager.docker.list_containers()
        
        if not success or not containers:
            self._show_message(stdscr, "Auto-Configure", "No running containers found")
            return
        
        container_names = [c.name for c in containers]
        selection = self._select_from_list(stdscr, "Select Container", container_names)
        
        if selection is None:
            return
        
        container_name = container_names[selection]
        
        stdscr.clear()
        stdscr.addstr(1, 2, f"Auto-Configure: {container_name}")
        stdscr.addstr(2, 2, "=" * (16 + len(container_name)))
        
        # Get domain
        suggested_domain = f"{container_name}.example.com"
        domain = self._get_input(stdscr, "Domain name", 4, 2, suggested_domain)
        if domain is None:
            return
        
        # Get SSL preference
        ssl_choice = self._get_input(stdscr, "Enable SSL? (Y/n)", 5, 2, "y")
        if ssl_choice is None:
            return
        ssl_enabled = ssl_choice.lower() in ['y', 'yes']
        
        # Configure
        stdscr.clear()
        stdscr.addstr(1, 2, "Configuring...")
        stdscr.refresh()
        
        success, msg = self.manager.docker.auto_configure_container(container_name, domain, ssl_enabled)
        self._show_message(stdscr, "Auto-Configure", msg, not success)
    
    def _docker_scan_suggest(self, stdscr):
        """Scan containers and suggest configurations"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Scanning Docker Containers...")
        stdscr.refresh()
        
        suggestions = self.manager.docker.scan_and_suggest_configs()
        
        if not suggestions:
            self._show_message(stdscr, "Scan Results", "No web containers found")
            return
        
        stdscr.clear()
        stdscr.addstr(1, 2, "Configuration Suggestions")
        stdscr.addstr(2, 2, "=" * 25)
        
        y = 4
        for i, sug in enumerate(suggestions[:curses.LINES - 10]):
            configured = "[OK] Configured" if sug['already_configured'] else "[ ] Not Configured"
            stdscr.addstr(y, 2, f"{i + 1}. {sug['container_name']}")
            y += 1
            stdscr.addstr(y, 4, f"Image: {sug['image'][:40]}")
            y += 1
            stdscr.addstr(y, 4, f"Suggested Domain: {sug['suggested_domain']}")
            y += 1
            stdscr.addstr(y, 4, f"Port: {sug['port']} | {configured}")
            y += 2
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _docker_container_details(self, stdscr):
        """View container details"""
        success, containers = self.manager.docker.list_containers(all_containers=True)
        
        if not success or not containers:
            self._show_message(stdscr, "Container Details", "No containers found")
            return
        
        container_names = [c.name for c in containers]
        selection = self._select_from_list(stdscr, "Select Container", container_names)
        
        if selection is None:
            return
        
        container = containers[selection]
        
        stdscr.clear()
        stdscr.addstr(1, 2, f"Container: {container.name}")
        stdscr.addstr(2, 2, "=" * (11 + len(container.name)))
        
        y = 4
        stdscr.addstr(y, 2, f"ID: {container.container_id}")
        y += 1
        stdscr.addstr(y, 2, f"Image: {container.image}")
        y += 1
        stdscr.addstr(y, 2, f"Status: {container.status}")
        y += 2
        
        if container.ports:
            stdscr.addstr(y, 2, "Port Mappings:")
            y += 1
            for internal, external in container.ports.items():
                stdscr.addstr(y, 4, f"{external} -> {internal}")
                y += 1
        
        ip = self.manager.docker.get_container_ip(container.name)
        if ip:
            y += 1
            stdscr.addstr(y, 2, f"IP Address: {ip}")
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _docker_container_logs(self, stdscr):
        """View container logs"""
        success, containers = self.manager.docker.list_containers()
        
        if not success or not containers:
            self._show_message(stdscr, "Container Logs", "No running containers found")
            return
        
        container_names = [c.name for c in containers]
        selection = self._select_from_list(stdscr, "Select Container", container_names)
        
        if selection is None:
            return
        
        container_name = container_names[selection]
        
        stdscr.clear()
        stdscr.addstr(1, 2, f"Loading logs for {container_name}...")
        stdscr.refresh()
        
        success, logs = self.manager.docker.get_container_logs(container_name, lines=100)
        
        if not success:
            self._show_message(stdscr, "Error", logs, True)
            return
        
        # Display logs
        lines = logs.split('\n')
        current_line = max(0, len(lines) - (curses.LINES - 6))
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, f"Logs: {container_name}")
            stdscr.addstr(2, 2, "=" * (6 + len(container_name)))
            
            display_lines = lines[current_line:current_line + curses.LINES - 6]
            for i, line in enumerate(display_lines):
                if i < curses.LINES - 6:
                    stdscr.addstr(4 + i, 2, line[:curses.COLS - 4])
            
            stdscr.addstr(curses.LINES - 2, 2, "Up/Down: Scroll | R: Refresh | Q: Quit")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == ord('q') or key == ord('Q') or key == 27:
                break
            elif key == ord('r') or key == ord('R'):
                success, logs = self.manager.docker.get_container_logs(container_name, lines=100)
                if success:
                    lines = logs.split('\n')
                    current_line = max(0, len(lines) - (curses.LINES - 6))
            elif key == curses.KEY_UP and current_line > 0:
                current_line -= 1
            elif key == curses.KEY_DOWN and current_line < len(lines) - (curses.LINES - 6):
                current_line += 1
    
    def _docker_start_container(self, stdscr):
        """Start a Docker container"""
        success, containers = self.manager.docker.list_containers(all_containers=True)
        
        if not success or not containers:
            self._show_message(stdscr, "Start Container", "No containers found")
            return
        
        # Filter stopped containers
        stopped = [c for c in containers if "Up" not in c.status]
        
        if not stopped:
            self._show_message(stdscr, "Start Container", "No stopped containers found")
            return
        
        container_names = [c.name for c in stopped]
        selection = self._select_from_list(stdscr, "Select Container to Start", container_names)
        
        if selection is not None:
            container_name = container_names[selection]
            success, msg = self.manager.docker.start_container(container_name)
            self._show_message(stdscr, "Start Container", msg, not success)
    
    def _docker_stop_container(self, stdscr):
        """Stop a Docker container"""
        success, containers = self.manager.docker.list_containers()
        
        if not success or not containers:
            self._show_message(stdscr, "Stop Container", "No running containers found")
            return
        
        container_names = [c.name for c in containers]
        selection = self._select_from_list(stdscr, "Select Container to Stop", container_names)
        
        if selection is not None:
            container_name = container_names[selection]
            if self._confirm_action(stdscr, f"Stop container '{container_name}'?"):
                success, msg = self.manager.docker.stop_container(container_name)
                self._show_message(stdscr, "Stop Container", msg, not success)
    
    def _docker_restart_container(self, stdscr):
        """Restart a Docker container"""
        success, containers = self.manager.docker.list_containers()
        
        if not success or not containers:
            self._show_message(stdscr, "Restart Container", "No running containers found")
            return
        
        container_names = [c.name for c in containers]
        selection = self._select_from_list(stdscr, "Select Container to Restart", container_names)
        
        if selection is not None:
            container_name = container_names[selection]
            if self._confirm_action(stdscr, f"Restart container '{container_name}'?"):
                success, msg = self.manager.docker.restart_container(container_name)
                self._show_message(stdscr, "Restart Container", msg, not success)
    
    # ==================== VERSION CONTROL (GIT-LIKE) ====================
    
    def _version_control_menu(self, stdscr):
        """Version control menu - Git-like interface"""
        menu_items = [
            "[*] Status & Overview",
            "[+] Commit Changes",
            "[=] View History (Log)",
            "[?] Show Commit Details",
            "[<] Checkout/Restore",
            "[~] Manage Branches",
            "[@] Tag Commit",
            "[%] Compare (Diff)",
            "[#] Repository Stats",
            "Back to Main Menu"
        ]
        
        current_selection = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, ">> Version Control System (Git-like)", curses.A_BOLD)
            stdscr.addstr(2, 2, "=" * 40)
            
            # Show quick status
            success, status = self.manager.vcs.status()
            if success:
                y = 4
                stdscr.addstr(y, 2, f"Branch: ", curses.A_BOLD)
                stdscr.addstr(y, 10, status['branch'], curses.A_REVERSE)
                y += 1
                
                if status['last_commit']:
                    stdscr.addstr(y, 2, f"Last Commit: {status['last_commit']} - {status['last_commit_message'][:30]}")
                    y += 1
                
                if status['has_uncommitted_changes']:
                    stdscr.addstr(y, 2, "[!] Uncommitted changes detected", curses.A_BOLD)
                else:
                    stdscr.addstr(y, 2, "[OK] Working tree clean", curses.A_DIM)
                y += 1
                
                stdscr.addstr(y, 2, f"Total Commits: {status['total_commits']} | Domains: {status['domains_count']}")
            
            # Draw menu
            start_y = 10
            for i, item in enumerate(menu_items):
                if i == current_selection:
                    stdscr.addstr(start_y + i, 4, f"> {item}", curses.A_REVERSE)
                else:
                    stdscr.addstr(start_y + i, 4, f"  {item}")
            
            stdscr.addstr(curses.LINES - 2, 2, "Up/Down: Navigate | Enter: Select | ESC: Back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(menu_items) - 1:
                current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if current_selection == 0:  # Status
                    self._vcs_status(stdscr)
                elif current_selection == 1:  # Commit
                    self._vcs_commit(stdscr)
                elif current_selection == 2:  # Log
                    self._vcs_log(stdscr)
                elif current_selection == 3:  # Show
                    self._vcs_show(stdscr)
                elif current_selection == 4:  # Checkout
                    self._vcs_checkout(stdscr)
                elif current_selection == 5:  # Branches
                    self._vcs_branches(stdscr)
                elif current_selection == 6:  # Tag
                    self._vcs_tag(stdscr)
                elif current_selection == 7:  # Diff
                    self._vcs_diff(stdscr)
                elif current_selection == 8:  # Stats
                    self._vcs_stats(stdscr)
                elif current_selection == 9:  # Back
                    break
            elif key == 27:  # ESC
                break
    
    def _vcs_status(self, stdscr):
        """Show detailed VCS status"""
        stdscr.clear()
        stdscr.addstr(1, 2, "[*] Version Control Status", curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * 27)
        
        success, status = self.manager.vcs.status()
        
        if not success:
            self._show_message(stdscr, "Error", "Failed to get status", True)
            return
        
        y = 4
        stdscr.addstr(y, 2, f"Current Branch: ", curses.A_BOLD)
        stdscr.addstr(y, 18, status['branch'], curses.A_REVERSE)
        y += 2
        
        if status['last_commit']:
            stdscr.addstr(y, 2, f"Last Commit:")
            y += 1
            stdscr.addstr(y, 4, f"Hash: {status['last_commit']}")
            y += 1
            stdscr.addstr(y, 4, f"Message: {status['last_commit_message']}")
            y += 1
            stdscr.addstr(y, 4, f"Time: {status['last_commit_time'][:19]}")
            y += 2
        else:
            stdscr.addstr(y, 2, "No commits yet")
            y += 2
        
        stdscr.addstr(y, 2, f"Repository Info:")
        y += 1
        stdscr.addstr(y, 4, f"Total Commits: {status['total_commits']}")
        y += 1
        stdscr.addstr(y, 4, f"Domains Tracked: {status['domains_count']}")
        y += 2
        
        if status['has_uncommitted_changes']:
            stdscr.addstr(y, 2, "[!] Working Tree Status:", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 4, "You have uncommitted changes", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 4, "Use 'Commit Changes' to save your work")
        else:
            stdscr.addstr(y, 2, "[OK] Working Tree Clean:", curses.A_BOLD)
            y += 1
            stdscr.addstr(y, 4, "No uncommitted changes", curses.A_DIM)
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _vcs_commit(self, stdscr):
        """Create a new commit"""
        # Check if there are changes
        success, status = self.manager.vcs.status()
        if success and not status['has_uncommitted_changes']:
            if not self._confirm_action(stdscr, "No changes detected. Create commit anyway?"):
                return
        
        stdscr.clear()
        stdscr.addstr(1, 2, "[+] Create Commit", curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * 18)
        
        # Get commit message
        message = self._get_input(stdscr, "Commit message (required)", 4, 2)
        if message is None or not message.strip():
            self._show_message(stdscr, "Error", "Commit message is required", True)
            return
        
        # Get description (optional)
        description = self._get_input(stdscr, "Description (optional)", 5, 2, "")
        if description is None:
            description = ""
        
        # Get tags (optional)
        tags_str = self._get_input(stdscr, "Tags (comma-separated, optional)", 6, 2, "")
        if tags_str is None:
            tags_str = ""
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        
        # Get author (optional)
        author = self._get_input(stdscr, "Author (optional)", 7, 2, "admin")
        if author is None:
            author = "admin"
        
        # Show summary
        stdscr.clear()
        stdscr.addstr(1, 2, "Commit Summary", curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * 14)
        
        y = 4
        stdscr.addstr(y, 2, f"Message: {message}")
        y += 1
        if description:
            stdscr.addstr(y, 2, f"Description: {description[:50]}")
            y += 1
        if tags:
            stdscr.addstr(y, 2, f"Tags: {', '.join(tags)}")
            y += 1
        stdscr.addstr(y, 2, f"Author: {author}")
        
        if self._confirm_action(stdscr, "\nCreate this commit?"):
            # Show progress
            stdscr.clear()
            stdscr.addstr(1, 2, "Creating commit...", curses.A_BOLD)
            stdscr.refresh()
            
            success, msg, commit = self.manager.vcs.commit(
                message=message,
                description=description,
                author=author,
                tags=tags
            )
            
            if success and commit:
                result_msg = f"[OK] Commit created successfully!\n\nCommit: {commit.short_hash()}\nMessage: {message}"
                if tags:
                    result_msg += f"\nTags: {', '.join(tags)}"
                self._show_message(stdscr, "Success", result_msg)
            else:
                self._show_message(stdscr, "Error", msg, True)
    
    def _vcs_log(self, stdscr):
        """View commit history"""
        # Get limit
        limit_str = self._get_input(stdscr, "Number of commits to show", 4, 2, "10")
        if limit_str is None:
            return
        
        try:
            limit = int(limit_str)
        except ValueError:
            limit = 10
        
        commits = self.manager.vcs.log(limit=limit)
        
        if not commits:
            self._show_message(stdscr, "Log", "No commits yet")
            return
        
        current_commit = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, f"[=] Commit History ({current_commit + 1}/{len(commits)})", curses.A_BOLD)
            stdscr.addstr(2, 2, "=" * 50)
            
            commit = commits[current_commit]
            
            y = 4
            stdscr.addstr(y, 2, f"Commit: ", curses.A_BOLD)
            stdscr.addstr(y, 10, commit.short_hash(), curses.A_REVERSE)
            y += 1
            
            if commit.tags:
                stdscr.addstr(y, 2, f"Tags: ", curses.A_BOLD)
                stdscr.addstr(y, 8, ", ".join(commit.tags), curses.A_DIM)
                y += 1
            
            stdscr.addstr(y, 2, f"Author: {commit.author}")
            y += 1
            stdscr.addstr(y, 2, f"Date: {commit.timestamp[:19]}")
            y += 2
            
            stdscr.addstr(y, 2, f"Message:", curses.A_BOLD)
            y += 1
            # Wrap message
            message_lines = []
            words = commit.message.split()
            current_line = ""
            for word in words:
                if len(current_line + word) < curses.COLS - 8:
                    current_line += word + " "
                else:
                    message_lines.append(current_line)
                    current_line = word + " "
            if current_line:
                message_lines.append(current_line)
            
            for line in message_lines:
                stdscr.addstr(y, 4, line)
                y += 1
            
            if commit.description:
                y += 1
                stdscr.addstr(y, 2, f"Description:", curses.A_BOLD)
                y += 1
                stdscr.addstr(y, 4, commit.description[:curses.COLS - 8])
                y += 1
            
            y += 1
            stdscr.addstr(y, 2, f"Changes:", curses.A_BOLD)
            y += 1
            stats = commit.stats
            stdscr.addstr(y, 4, f"+{stats.get('domains_added', 0)} domains added, "
                                f"-{stats.get('domains_removed', 0)} removed, "
                                f"~{stats.get('domains_modified', 0)} modified")
            y += 1
            stdscr.addstr(y, 4, f"{stats.get('configs_changed', 0)} configs changed")
            
            if commit.files_changed:
                y += 2
                stdscr.addstr(y, 2, f"Files:", curses.A_BOLD)
                y += 1
                for i, file in enumerate(commit.files_changed[:5]):
                    stdscr.addstr(y, 4, f"- {file}")
                    y += 1
                if len(commit.files_changed) > 5:
                    stdscr.addstr(y, 4, f"... and {len(commit.files_changed) - 5} more")
            
            stdscr.addstr(curses.LINES - 2, 2, "Left/Right: Navigate | C: Checkout | D: Diff | ESC: Back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_LEFT and current_commit > 0:
                current_commit -= 1
            elif key == curses.KEY_RIGHT and current_commit < len(commits) - 1:
                current_commit += 1
            elif key == ord('c') or key == ord('C'):
                if self._confirm_action(stdscr, f"Checkout commit {commits[current_commit].short_hash()}?\n\nThis will restore your configuration."):
                    success, msg = self.manager.vcs.checkout(commits[current_commit].hash)
                    self._show_message(stdscr, "Checkout", msg, not success)
                    if success:
                        break
            elif key == ord('d') or key == ord('D'):
                success, diff_text = self.manager.vcs.diff(commits[current_commit].hash)
                if success:
                    self._show_text_viewer(stdscr, "Diff", diff_text)
            elif key == 27 or key == ord('q'):
                break
    
    def _vcs_show(self, stdscr):
        """Show commit details"""
        # Get commits for selection
        commits = self.manager.vcs.log(limit=20)
        
        if not commits:
            self._show_message(stdscr, "Show Commit", "No commits yet")
            return
        
        commit_strings = [f"{c.short_hash()} - {c.message[:40]}" for c in commits]
        selection = self._select_from_list(stdscr, "Select Commit to View", commit_strings)
        
        if selection is None:
            return
        
        commit = commits[selection]
        success, _, diff_text = self.manager.vcs.show(commit.hash)
        
        if success:
            self._show_text_viewer(stdscr, f"Commit {commit.short_hash()}", diff_text)
        else:
            self._show_message(stdscr, "Error", "Failed to show commit", True)
    
    def _vcs_checkout(self, stdscr):
        """Checkout/restore a commit"""
        # Get commits
        commits = self.manager.vcs.log(limit=20)
        
        if not commits:
            self._show_message(stdscr, "Checkout", "No commits to checkout")
            return
        
        commit_strings = [f"{c.short_hash()} - {c.message[:40]} ({c.timestamp[:10]})" for c in commits]
        selection = self._select_from_list(stdscr, "Select Commit to Restore", commit_strings)
        
        if selection is None:
            return
        
        commit = commits[selection]
        
        # Show warning
        warning = (
            f"[!] WARNING: Checkout will restore configuration to:\n\n"
            f"Commit: {commit.short_hash()}\n"
            f"Message: {commit.message}\n"
            f"Date: {commit.timestamp[:19]}\n\n"
            f"Your current configuration will be backed up first.\n\n"
            f"Continue?"
        )
        
        if self._confirm_action(stdscr, warning):
            stdscr.clear()
            stdscr.addstr(1, 2, "Restoring configuration...", curses.A_BOLD)
            stdscr.addstr(3, 2, "This may take a moment...")
            stdscr.refresh()
            
            success, msg = self.manager.vcs.checkout(commit.hash)
            
            if success:
                self._show_message(stdscr, "Success", 
                                  f"[OK] Successfully restored to commit {commit.short_hash()}\n\n"
                                  f"Your previous state was saved as a commit.")
            else:
                self._show_message(stdscr, "Error", msg, True)
    
    def _vcs_branches(self, stdscr):
        """Manage branches"""
        menu_items = [
            "List Branches",
            "Create Branch",
            "Switch Branch",
            "Delete Branch",
            "Back"
        ]
        
        current_selection = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, "[~] Branch Management", curses.A_BOLD)
            stdscr.addstr(2, 2, "=" * 22)
            
            # Show current branch
            current_branch = self.manager.vcs._get_current_branch()
            stdscr.addstr(4, 2, f"Current Branch: ", curses.A_BOLD)
            stdscr.addstr(4, 18, current_branch, curses.A_REVERSE)
            
            # Draw menu
            start_y = 6
            for i, item in enumerate(menu_items):
                if i == current_selection:
                    stdscr.addstr(start_y + i, 4, f"> {item}", curses.A_REVERSE)
                else:
                    stdscr.addstr(start_y + i, 4, f"  {item}")
            
            stdscr.addstr(curses.LINES - 2, 2, "Up/Down: Navigate | Enter: Select | ESC: Back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(menu_items) - 1:
                current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if current_selection == 0:  # List
                    self._vcs_list_branches(stdscr)
                elif current_selection == 1:  # Create
                    self._vcs_create_branch(stdscr)
                elif current_selection == 2:  # Switch
                    self._vcs_switch_branch(stdscr)
                elif current_selection == 3:  # Delete
                    self._vcs_delete_branch(stdscr)
                elif current_selection == 4:  # Back
                    break
            elif key == 27:
                break
    
    def _vcs_list_branches(self, stdscr):
        """List all branches"""
        success, msg, branches = self.manager.vcs.branch("list")
        
        if not success or not branches:
            self._show_message(stdscr, "Branches", "No branches found")
            return
        
        current_branch = self.manager.vcs._get_current_branch()
        
        stdscr.clear()
        stdscr.addstr(1, 2, "[~] All Branches", curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * 17)
        
        y = 4
        for branch in branches:
            indicator = "* " if branch.name == current_branch else "  "
            attr = curses.A_REVERSE if branch.name == current_branch else curses.A_NORMAL
            
            stdscr.addstr(y, 2, f"{indicator}{branch.name}", attr)
            y += 1
            stdscr.addstr(y, 4, f"Created: {branch.created_at[:19]}")
            y += 1
            if branch.description:
                stdscr.addstr(y, 4, f"Description: {branch.description[:50]}")
                y += 1
            if branch.current_commit:
                stdscr.addstr(y, 4, f"Head: {branch.current_commit[:7]}")
                y += 1
            y += 1
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _vcs_create_branch(self, stdscr):
        """Create a new branch"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Create Branch", curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * 13)
        
        name = self._get_input(stdscr, "Branch name", 4, 2)
        if name is None or not name.strip():
            return
        
        description = self._get_input(stdscr, "Description (optional)", 5, 2, "")
        if description is None:
            description = ""
        
        success, msg, _ = self.manager.vcs.branch("create", name, description)
        self._show_message(stdscr, "Create Branch", msg, not success)
    
    def _vcs_switch_branch(self, stdscr):
        """Switch to another branch"""
        success, _, branches = self.manager.vcs.branch("list")
        
        if not success or not branches:
            self._show_message(stdscr, "Switch Branch", "No branches available")
            return
        
        current_branch = self.manager.vcs._get_current_branch()
        branch_names = [f"{b.name} {'(current)' if b.name == current_branch else ''}" for b in branches]
        
        selection = self._select_from_list(stdscr, "Select Branch to Switch To", branch_names)
        
        if selection is None:
            return
        
        target_branch = branches[selection]
        
        if target_branch.name == current_branch:
            self._show_message(stdscr, "Switch Branch", "Already on this branch")
            return
        
        if self._confirm_action(stdscr, f"Switch to branch '{target_branch.name}'?\n\nThis will restore that branch's configuration."):
            stdscr.clear()
            stdscr.addstr(1, 2, "Switching branch...", curses.A_BOLD)
            stdscr.refresh()
            
            success, msg, _ = self.manager.vcs.branch("switch", target_branch.name)
            self._show_message(stdscr, "Switch Branch", msg, not success)
    
    def _vcs_delete_branch(self, stdscr):
        """Delete a branch"""
        success, _, branches = self.manager.vcs.branch("list")
        
        if not success or not branches:
            self._show_message(stdscr, "Delete Branch", "No branches available")
            return
        
        # Filter out main and current branch
        current_branch = self.manager.vcs._get_current_branch()
        deletable = [b for b in branches if b.name != "main" and b.name != current_branch]
        
        if not deletable:
            self._show_message(stdscr, "Delete Branch", "No branches available for deletion")
            return
        
        branch_names = [b.name for b in deletable]
        selection = self._select_from_list(stdscr, "Select Branch to Delete", branch_names)
        
        if selection is None:
            return
        
        target_branch = deletable[selection]
        
        if self._confirm_action(stdscr, f"Delete branch '{target_branch.name}'?\n\nThis cannot be undone."):
            success, msg, _ = self.manager.vcs.branch("delete", target_branch.name)
            self._show_message(stdscr, "Delete Branch", msg, not success)
    
    def _vcs_tag(self, stdscr):
        """Tag a commit"""
        # Get commits
        commits = self.manager.vcs.log(limit=20)
        
        if not commits:
            self._show_message(stdscr, "Tag Commit", "No commits to tag")
            return
        
        commit_strings = [f"{c.short_hash()} - {c.message[:40]}" for c in commits]
        selection = self._select_from_list(stdscr, "Select Commit to Tag", commit_strings)
        
        if selection is None:
            return
        
        commit = commits[selection]
        
        stdscr.clear()
        stdscr.addstr(1, 2, f"Tag Commit {commit.short_hash()}", curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * (11 + len(commit.short_hash())))
        
        tag_name = self._get_input(stdscr, "Tag name (e.g., v1.0, prod-2025)", 4, 2)
        if tag_name is None or not tag_name.strip():
            return
        
        message = self._get_input(stdscr, "Tag message (optional)", 5, 2, "")
        if message is None:
            message = ""
        
        success, msg = self.manager.vcs.tag(commit.hash, tag_name, message)
        self._show_message(stdscr, "Tag Commit", msg, not success)
    
    def _vcs_diff(self, stdscr):
        """Compare commits"""
        commits = self.manager.vcs.log(limit=20)
        
        if not commits:
            self._show_message(stdscr, "Diff", "No commits to compare")
            return
        
        # Select first commit
        commit_strings = [f"{c.short_hash()} - {c.message[:40]}" for c in commits]
        commit_strings.append("Current working state")
        
        selection1 = self._select_from_list(stdscr, "Select First Commit", commit_strings)
        if selection1 is None:
            return
        
        # Select second commit
        selection2 = self._select_from_list(stdscr, "Select Second Commit (or Current)", commit_strings)
        if selection2 is None:
            return
        
        commit1_hash = commits[selection1].hash if selection1 < len(commits) else None
        commit2_hash = commits[selection2].hash if selection2 < len(commits) else None
        
        if commit1_hash is None:
            self._show_message(stdscr, "Diff", "Cannot compare two working states", True)
            return
        
        stdscr.clear()
        stdscr.addstr(1, 2, "Calculating diff...", curses.A_BOLD)
        stdscr.refresh()
        
        success, diff_text = self.manager.vcs.diff(commit1_hash, commit2_hash)
        
        if success:
            self._show_text_viewer(stdscr, "Diff", diff_text)
        else:
            self._show_message(stdscr, "Error", diff_text, True)
    
    def _vcs_stats(self, stdscr):
        """Show repository statistics"""
        stdscr.clear()
        stdscr.addstr(1, 2, "[#] Repository Statistics", curses.A_BOLD)
        stdscr.addstr(2, 2, "=" * 26)
        
        stats = self.manager.vcs.get_stats()
        
        y = 4
        stdscr.addstr(y, 2, "Repository Overview:", curses.A_BOLD)
        y += 1
        stdscr.addstr(y, 4, f"Total Commits: {stats['total_commits']}")
        y += 1
        stdscr.addstr(y, 4, f"Total Branches: {stats['total_branches']}")
        y += 1
        stdscr.addstr(y, 4, f"Total Tags: {stats['total_tags']}")
        y += 1
        stdscr.addstr(y, 4, f"Repository Size: {stats['repository_size']}")
        y += 2
        
        stdscr.addstr(y, 2, "Domain Activity:", curses.A_BOLD)
        y += 1
        stdscr.addstr(y, 4, f"Domains Added: {stats['total_domains_added']}")
        y += 1
        stdscr.addstr(y, 4, f"Domains Removed: {stats['total_domains_removed']}")
        y += 2
        
        if stats['authors']:
            stdscr.addstr(y, 2, "Contributors:", curses.A_BOLD)
            y += 1
            for author, count in stats['authors'].items():
                stdscr.addstr(y, 4, f"{author}: {count} commits")
                y += 1
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        self._wait_for_input(stdscr)
    
    def _show_text_viewer(self, stdscr, title: str, text: str):
        """Generic text viewer with scrolling"""
        lines = text.split('\n')
        current_line = 0
        
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, title, curses.A_BOLD)
            stdscr.addstr(2, 2, "=" * len(title))
            
            # Display lines
            display_lines = lines[current_line:current_line + curses.LINES - 6]
            for i, line in enumerate(display_lines):
                if i < curses.LINES - 6:
                    display_line = line[:curses.COLS - 4] if len(line) > curses.COLS - 4 else line
                    stdscr.addstr(4 + i, 2, display_line)
            
            stdscr.addstr(curses.LINES - 2, 2, f"Line {current_line + 1}/{len(lines)} | Up/Down: Scroll | PgUp/PgDn: Page | Q/ESC: Back")
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == ord('q') or key == ord('Q') or key == 27:
                break
            elif key == curses.KEY_UP and current_line > 0:
                current_line -= 1
            elif key == curses.KEY_DOWN and current_line < len(lines) - (curses.LINES - 6):
                current_line += 1
            elif key == curses.KEY_PPAGE:  # Page Up
                current_line = max(0, current_line - (curses.LINES - 6))
            elif key == curses.KEY_NPAGE:  # Page Down
                current_line = min(len(lines) - (curses.LINES - 6), current_line + (curses.LINES - 6))
                current_line = max(0, current_line)
