#!/usr/bin/env python3
"""
VPS NGINX Domain Manager
A comprehensive terminal-based manager for NGINX domains, SSL certificates, and configurations.

Author: VPS Manager
Version: 1.0.0
"""

import os
import sys
import json
import subprocess
import curses
import datetime
import shutil
import re
import tempfile
import socket
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Configuration
MANAGER_DIR = Path.home() / "manager"
NGINX_SITES_DIR = Path("/etc/nginx/sites-available")
NGINX_ENABLED_DIR = Path("/etc/nginx/sites-enabled")
BACKUP_DIR = MANAGER_DIR / "backups"
TEMPLATES_DIR = MANAGER_DIR / "templates"
DATA_FILE = MANAGER_DIR / "domains.json"
CONFIG_FILE = MANAGER_DIR / "config.json"
LOG_FILE = MANAGER_DIR / "manager.log"

class Logger:
    """Simple logging utility"""
    
    @staticmethod
    def log(message: str, level: str = "INFO"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        # Ensure log directory exists
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(LOG_FILE, "a") as f:
            f.write(log_entry)
    
    @staticmethod
    def info(message: str):
        Logger.log(message, "INFO")
    
    @staticmethod
    def error(message: str):
        Logger.log(message, "ERROR")
    
    @staticmethod
    def warning(message: str):
        Logger.log(message, "WARNING")

class Domain:
    """Domain configuration class"""
    
    def __init__(self, name: str, port: int, ssl: bool = True, custom_config: str = None):
        self.name = name
        self.port = port
        self.ssl = ssl
        self.custom_config = custom_config
        self.created_at = datetime.datetime.now().isoformat()
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "port": self.port,
            "ssl": self.ssl,
            "custom_config": self.custom_config,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        domain = cls(data["name"], data["port"], data["ssl"], data.get("custom_config"))
        domain.created_at = data.get("created_at", domain.created_at)
        domain.updated_at = data.get("updated_at", domain.updated_at)
        return domain

class VPSManager:
    """Main VPS Manager class"""
    
    def __init__(self):
        self.domains: List[Domain] = []
        self.config: Dict = {}
        self.setup_directories()
        self.load_config()
        self.load_domains()
    
    def setup_directories(self):
        """Create necessary directories"""
        directories = [MANAGER_DIR, BACKUP_DIR, TEMPLATES_DIR, MANAGER_DIR / "custom-configs"]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        Logger.info("Directories setup completed")
    
    def load_config(self):
        """Load configuration settings"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
                Logger.info("Configuration loaded successfully")
            except Exception as e:
                Logger.error(f"Failed to load config: {e}")
                self.config = {}
        else:
            self.config = {}
    
    def save_config(self):
        """Save configuration settings"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            Logger.info("Configuration saved successfully")
        except Exception as e:
            Logger.error(f"Failed to save config: {e}")
    
    def is_first_run(self) -> bool:
        """Check if this is the first run"""
        return not CONFIG_FILE.exists() or not self.config.get('setup_completed', False)
    
    def complete_setup(self):
        """Mark setup as completed"""
        self.config['setup_completed'] = True
        self.save_config()
    
    def load_domains(self):
        """Load domains from JSON file"""
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.domains = [Domain.from_dict(d) for d in data]
                Logger.info(f"Loaded {len(self.domains)} domains")
            except Exception as e:
                Logger.error(f"Failed to load domains: {e}")
                self.domains = []
    
    def save_domains(self):
        """Save domains to JSON file"""
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump([d.to_dict() for d in self.domains], f, indent=2)
            Logger.info("Domains saved successfully")
        except Exception as e:
            Logger.error(f"Failed to save domains: {e}")
    
    def run_command(self, command: str) -> Tuple[bool, str]:
        """Execute shell command and return success status and output"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            Logger.info(f"Command '{command}' executed with status: {result.returncode}")
            return success, output
        except Exception as e:
            Logger.error(f"Command execution failed: {e}")
            return False, str(e)
    
    def validate_domain(self, domain: str) -> bool:
        """Validate domain name format"""
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain)) and len(domain) <= 253
    
    def validate_port(self, port: int) -> bool:
        """Validate port number"""
        return 1 <= port <= 65535
    
    def check_port_available(self, port: int) -> bool:
        """Check if port is available on localhost"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                return result == 0  # Port is in use if connection succeeds
        except Exception:
            return False
    
    def domain_exists(self, domain_name: str) -> bool:
        """Check if domain already exists"""
        return any(d.name == domain_name for d in self.domains)
    
    def get_domain(self, domain_name: str) -> Optional[Domain]:
        """Get domain by name"""
        for domain in self.domains:
            if domain.name == domain_name:
                return domain
        return None
    
    def add_domain(self, name: str, port: int, ssl: bool = True, custom_config: str = None) -> Tuple[bool, str]:
        """Add a new domain"""
        try:
            # Validation
            if not self.validate_domain(name):
                return False, "Invalid domain name format"
            
            if not self.validate_port(port):
                return False, "Invalid port number (must be 1-65535)"
            
            if self.domain_exists(name):
                return False, "Domain already exists"
            
            # Check if port is in use
            if not self.check_port_available(port):
                Logger.warning(f"Port {port} appears to be not in use for domain {name}")
            
            # Create domain object
            domain = Domain(name, port, ssl, custom_config)
            
            # Generate NGINX configuration
            success, message = self.generate_nginx_config(domain)
            if not success:
                return False, f"Failed to generate NGINX config: {message}"
            
            # Generate SSL certificate if needed
            if ssl:
                success, message = self.generate_ssl_certificate(name)
                if not success:
                    return False, f"Failed to generate SSL certificate: {message}"
            
            # Enable site
            success, message = self.enable_site(name)
            if not success:
                return False, f"Failed to enable site: {message}"
            
            # Test and reload NGINX
            success, message = self.test_and_reload_nginx()
            if not success:
                return False, f"NGINX configuration test failed: {message}"
            
            # Add to domains list and save
            self.domains.append(domain)
            self.save_domains()
            
            Logger.info(f"Domain {name} added successfully")
            return True, f"Domain {name} added successfully"
            
        except Exception as e:
            Logger.error(f"Failed to add domain {name}: {e}")
            return False, str(e)
    
    def edit_domain(self, old_name: str, new_name: str = None, new_port: int = None, new_ssl: bool = None, new_custom_config: str = None) -> Tuple[bool, str]:
        """Edit an existing domain"""
        try:
            domain = self.get_domain(old_name)
            if not domain:
                return False, "Domain not found"
            
            # Backup current configuration
            self.backup_domain_config(old_name)
            
            # Update domain properties
            if new_name and new_name != old_name:
                if not self.validate_domain(new_name):
                    return False, "Invalid new domain name format"
                if self.domain_exists(new_name):
                    return False, "New domain name already exists"
                domain.name = new_name
            
            if new_port is not None:
                if not self.validate_port(new_port):
                    return False, "Invalid port number"
                domain.port = new_port
            
            if new_ssl is not None:
                domain.ssl = new_ssl
            
            if new_custom_config is not None:
                domain.custom_config = new_custom_config
            
            domain.updated_at = datetime.datetime.now().isoformat()
            
            # Remove old configuration if name changed
            if new_name and new_name != old_name:
                self.disable_site(old_name)
                self.remove_nginx_config(old_name)
            
            # Generate new configuration
            success, message = self.generate_nginx_config(domain)
            if not success:
                return False, f"Failed to generate NGINX config: {message}"
            
            # Handle SSL certificate
            if domain.ssl:
                success, message = self.generate_ssl_certificate(domain.name)
                if not success:
                    return False, f"Failed to generate SSL certificate: {message}"
            
            # Enable site
            success, message = self.enable_site(domain.name)
            if not success:
                return False, f"Failed to enable site: {message}"
            
            # Test and reload NGINX
            success, message = self.test_and_reload_nginx()
            if not success:
                return False, f"NGINX configuration test failed: {message}"
            
            self.save_domains()
            Logger.info(f"Domain {old_name} edited successfully")
            return True, f"Domain edited successfully"
            
        except Exception as e:
            Logger.error(f"Failed to edit domain {old_name}: {e}")
            return False, str(e)
    
    def delete_domain(self, name: str) -> Tuple[bool, str]:
        """Delete a domain"""
        try:
            domain = self.get_domain(name)
            if not domain:
                return False, "Domain not found"
            
            # Backup configuration before deletion
            self.backup_domain_config(name)
            
            # Disable and remove NGINX configuration
            self.disable_site(name)
            self.remove_nginx_config(name)
            
            # Remove SSL certificate (optional, keep for potential reuse)
            # self.remove_ssl_certificate(name)
            
            # Remove from domains list
            self.domains = [d for d in self.domains if d.name != name]
            self.save_domains()
            
            # Test and reload NGINX
            success, message = self.test_and_reload_nginx()
            if not success:
                Logger.warning(f"NGINX reload failed after deleting {name}: {message}")
            
            Logger.info(f"Domain {name} deleted successfully")
            return True, f"Domain {name} deleted successfully"
            
        except Exception as e:
            Logger.error(f"Failed to delete domain {name}: {e}")
            return False, str(e)
    
    def generate_nginx_config(self, domain: Domain) -> Tuple[bool, str]:
        """Generate NGINX configuration for a domain"""
        try:
            # Determine template to use
            if domain.custom_config:
                template_path = MANAGER_DIR / "custom-configs" / domain.custom_config
                if not template_path.exists():
                    template_path = TEMPLATES_DIR / "default.conf"
            else:
                template_path = TEMPLATES_DIR / "default.conf"
            
            # Read template
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Replace variables
            ssl_cert_path = f"/etc/letsencrypt/live/{domain.name}/fullchain.pem"
            ssl_key_path = f"/etc/letsencrypt/live/{domain.name}/privkey.pem"
            
            config_content = template_content.replace('$DOMAIN', domain.name)
            config_content = config_content.replace('$PORT', str(domain.port))
            config_content = config_content.replace('$SSL_CERT_PATH', ssl_cert_path)
            config_content = config_content.replace('$SSL_KEY_PATH', ssl_key_path)
            
            # If SSL is disabled, use only HTTP configuration
            if not domain.ssl:
                # Extract only HTTP server block
                lines = config_content.split('\n')
                http_config = []
                in_http_block = False
                brace_count = 0
                
                for line in lines:
                    if 'server {' in line and 'listen 80' in config_content[config_content.find(line):config_content.find(line)+200]:
                        in_http_block = True
                        brace_count = 0
                    
                    if in_http_block:
                        http_config.append(line)
                        brace_count += line.count('{')
                        brace_count -= line.count('}')
                        
                        if brace_count == 0 and '}' in line:
                            break
                
                config_content = '\n'.join(http_config)
            
            # Write configuration file
            config_file = NGINX_SITES_DIR / domain.name
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            Logger.info(f"NGINX configuration generated for {domain.name}")
            return True, "Configuration generated successfully"
            
        except Exception as e:
            Logger.error(f"Failed to generate NGINX config for {domain.name}: {e}")
            return False, str(e)
    
    def generate_ssl_certificate(self, domain_name: str) -> Tuple[bool, str]:
        """Generate SSL certificate using certbot"""
        try:
            # Check if certificate already exists
            cert_path = Path(f"/etc/letsencrypt/live/{domain_name}/fullchain.pem")
            if cert_path.exists():
                Logger.info(f"SSL certificate already exists for {domain_name}")
                return True, "Certificate already exists"
            
            # Generate certificate
            email = self.config.get('certbot_email', f'admin@{domain_name}')
            command = f"certbot --nginx -d {domain_name} --non-interactive --agree-tos --email {email}"
            success, output = self.run_command(command)
            
            if success:
                Logger.info(f"SSL certificate generated for {domain_name}")
                return True, "SSL certificate generated successfully"
            else:
                Logger.error(f"Failed to generate SSL certificate for {domain_name}: {output}")
                return False, output
                
        except Exception as e:
            Logger.error(f"SSL certificate generation failed for {domain_name}: {e}")
            return False, str(e)
    
    def enable_site(self, domain_name: str) -> Tuple[bool, str]:
        """Enable NGINX site"""
        try:
            source = NGINX_SITES_DIR / domain_name
            target = NGINX_ENABLED_DIR / domain_name
            
            if target.exists():
                target.unlink()
            
            target.symlink_to(source)
            Logger.info(f"Site {domain_name} enabled")
            return True, "Site enabled successfully"
            
        except Exception as e:
            Logger.error(f"Failed to enable site {domain_name}: {e}")
            return False, str(e)
    
    def disable_site(self, domain_name: str) -> Tuple[bool, str]:
        """Disable NGINX site"""
        try:
            target = NGINX_ENABLED_DIR / domain_name
            if target.exists():
                target.unlink()
                Logger.info(f"Site {domain_name} disabled")
            return True, "Site disabled successfully"
            
        except Exception as e:
            Logger.error(f"Failed to disable site {domain_name}: {e}")
            return False, str(e)
    
    def remove_nginx_config(self, domain_name: str) -> Tuple[bool, str]:
        """Remove NGINX configuration file"""
        try:
            config_file = NGINX_SITES_DIR / domain_name
            if config_file.exists():
                config_file.unlink()
                Logger.info(f"NGINX config removed for {domain_name}")
            return True, "Configuration removed successfully"
            
        except Exception as e:
            Logger.error(f"Failed to remove NGINX config for {domain_name}: {e}")
            return False, str(e)
    
    def test_and_reload_nginx(self) -> Tuple[bool, str]:
        """Test NGINX configuration and reload if valid"""
        try:
            # Test configuration
            success, output = self.run_command("nginx -t")
            if not success:
                return False, f"Configuration test failed: {output}"
            
            # Reload NGINX
            success, output = self.run_command("systemctl reload nginx")
            if success:
                Logger.info("NGINX reloaded successfully")
                return True, "NGINX reloaded successfully"
            else:
                return False, f"Failed to reload NGINX: {output}"
                
        except Exception as e:
            Logger.error(f"NGINX test/reload failed: {e}")
            return False, str(e)
    
    def backup_domain_config(self, domain_name: str):
        """Backup domain configuration"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            config_file = NGINX_SITES_DIR / domain_name
            
            if config_file.exists():
                backup_file = BACKUP_DIR / f"{domain_name}_{timestamp}.conf"
                shutil.copy2(config_file, backup_file)
                Logger.info(f"Configuration backed up for {domain_name}")
                
        except Exception as e:
            Logger.error(f"Failed to backup configuration for {domain_name}: {e}")
    
    def create_full_backup(self) -> Tuple[bool, str]:
        """Create full backup of all configurations"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = BACKUP_DIR / f"full_backup_{timestamp}"
            backup_dir.mkdir(exist_ok=True)
            
            # Backup domains.json
            if DATA_FILE.exists():
                shutil.copy2(DATA_FILE, backup_dir / "domains.json")
            
            # Backup all NGINX configurations
            nginx_backup_dir = backup_dir / "nginx_configs"
            nginx_backup_dir.mkdir(exist_ok=True)
            
            for domain in self.domains:
                config_file = NGINX_SITES_DIR / domain.name
                if config_file.exists():
                    shutil.copy2(config_file, nginx_backup_dir / f"{domain.name}.conf")
            
            # Backup custom configurations
            custom_configs_dir = MANAGER_DIR / "custom-configs"
            if custom_configs_dir.exists():
                shutil.copytree(custom_configs_dir, backup_dir / "custom-configs", dirs_exist_ok=True)
            
            Logger.info(f"Full backup created: {backup_dir}")
            return True, f"Full backup created successfully at {backup_dir}"
            
        except Exception as e:
            Logger.error(f"Failed to create full backup: {e}")
            return False, str(e)
    
    def list_backups(self) -> List[str]:
        """List available backups"""
        try:
            backups = []
            for item in BACKUP_DIR.iterdir():
                if item.is_dir() and item.name.startswith("full_backup_"):
                    backups.append(item.name)
            return sorted(backups, reverse=True)
        except Exception as e:
            Logger.error(f"Failed to list backups: {e}")
            return []
    
    def get_nginx_status(self) -> Tuple[bool, str]:
        """Get NGINX service status"""
        success, output = self.run_command("systemctl is-active nginx")
        return success, output.strip()
    
    def restart_nginx(self) -> Tuple[bool, str]:
        """Restart NGINX service"""
        return self.run_command("systemctl restart nginx")
    
    def get_nginx_status(self) -> Tuple[bool, str]:
        """Get NGINX service status"""
        success, output = self.run_command("systemctl is-active nginx")
        is_active = success and output.strip() == "active"
        return is_active, output.strip()
    
    def list_backups(self) -> List[str]:
        """List available backups"""
        backup_dir = MANAGER_DIR / "backups"
        if not backup_dir.exists():
            return []
        
        backups = []
        for backup_file in backup_dir.iterdir():
            if backup_file.is_file() and backup_file.suffix == '.tar.gz':
                backups.append(backup_file.name)
        
        return sorted(backups, reverse=True)  # Most recent first

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
            "Backup Configurations",
            "Restore Backup",
            "View Logs",
            "Settings",
            "Exit"
        ]
    
    def run(self):
        """Start the terminal UI"""
        # Check if this is the first run and show onboarding
        if self.manager.is_first_run():
            curses.wrapper(self._onboarding_flow)
        
        curses.wrapper(self._main_loop)
    
    def _main_loop(self, stdscr):
        """Main UI loop"""
        curses.curs_set(0)  # Hide cursor
        stdscr.keypad(True)  # Enable special keys
        
        while True:
            stdscr.clear()
            self._draw_header(stdscr)
            self._draw_menu(stdscr)
            self._draw_footer(stdscr)
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and self.current_selection > 0:
                self.current_selection -= 1
            elif key == curses.KEY_DOWN and self.current_selection < len(self.menu_items) - 1:
                self.current_selection += 1
            elif key == ord('\n') or key == ord(' '):
                if self.current_selection == len(self.menu_items) - 1:  # Exit
                    break
                else:
                    self._handle_menu_selection(stdscr)
    
    def _draw_header(self, stdscr):
        """Draw the header"""
        header = "VPS NGINX Domain Manager v1.0.0"
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
        stdscr.addstr(footer_y + 1, 2, "Use ↑/↓ to navigate, Enter/Space to select")
    
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
        elif selection == 5:  # Backup Configurations
            self._backup_configurations(stdscr)
        elif selection == 6:  # Restore Backup
            self._restore_backup(stdscr)
        elif selection == 7:  # View Logs
            self._view_logs(stdscr)
        elif selection == 8:  # Settings
            self._settings_menu(stdscr)
    
    def _get_input(self, stdscr, prompt: str, y: int, x: int, default: str = "") -> str:
        """Get user input with prompt"""
        curses.echo()
        curses.curs_set(1)
        stdscr.addstr(y, x, f"{prompt}: ")
        if default:
            stdscr.addstr(y, x + len(prompt) + 2, default)
        stdscr.refresh()
        
        # Get input
        input_str = stdscr.getstr(y, x + len(prompt) + 2, 50).decode('utf-8')
        
        curses.noecho()
        curses.curs_set(0)
        
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
        stdscr.getch()
    
    def _confirm_action(self, stdscr, message: str) -> bool:
        """Show confirmation dialog"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Confirmation")
        stdscr.addstr(2, 2, "=" * 12)
        stdscr.addstr(4, 2, message)
        stdscr.addstr(6, 2, "Are you sure? (y/N): ")
        stdscr.refresh()
        
        key = stdscr.getch()
        return key in [ord('y'), ord('Y')]
    
    def _select_from_list(self, stdscr, title: str, items: List[str], allow_cancel: bool = True) -> Optional[int]:
        """Select item from list"""
        if not items:
            self._show_message(stdscr, title, "No items available.")
            return None
        
        current_selection = 0
        
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
            
            stdscr.addstr(curses.LINES - 2, 2, "Use ↑/↓ to navigate, Enter to select")
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
        stdscr.getch()
    
    def _add_domain(self, stdscr):
        """Add a new domain"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Add New Domain")
        stdscr.addstr(2, 2, "=" * 15)
        
        try:
            # Get domain name
            domain_name = self._get_input(stdscr, "Domain name (e.g., example.com)", 4, 2)
            if not domain_name:
                self._show_message(stdscr, "Error", "Domain name is required.", True)
                return
            
            # Get port
            port_str = self._get_input(stdscr, "Backend port (e.g., 3000)", 5, 2)
            try:
                port = int(port_str)
            except ValueError:
                self._show_message(stdscr, "Error", "Invalid port number.", True)
                return
            
            # Get SSL preference (use configured default)
            default_ssl = 'y' if self.manager.config.get('default_ssl', True) else 'n'
            ssl_choice = self._get_input(stdscr, f"Enable SSL? ({'Y/n' if default_ssl == 'y' else 'y/N'})", 6, 2, default_ssl)
            ssl_enabled = ssl_choice.lower() in ['y', 'yes']
            
            # Get custom config preference
            custom_choice = self._get_input(stdscr, "Use custom config? (y/N)", 7, 2, "n")
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
            new_port_str = self._get_input(stdscr, f"Port ({domain.port})", 7, 2)
            new_ssl_str = self._get_input(stdscr, f"SSL ({'Yes' if domain.ssl else 'No'})", 8, 2)
            
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
            # Show progress
            stdscr.clear()
            stdscr.addstr(1, 2, "Deleting Domain...")
            stdscr.addstr(3, 2, "Please wait...")
            stdscr.refresh()
            
            # Delete domain
            success, message = self.manager.delete_domain(domain_name)
            
            if success:
                self._show_message(stdscr, "Success", message)
            else:
                self._show_message(stdscr, "Error", message, True)
    
    def _nginx_status(self, stdscr):
        """Show NGINX status and management options"""
        while True:
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
            
            stdscr.addstr(curses.LINES - 2, 2, "Select option (1-4) or press any other key to refresh: ")
            stdscr.refresh()
            
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
                    stdscr.addstr(4, 2, "✓ Configuration is valid", curses.A_BOLD)
                else:
                    stdscr.addstr(4, 2, "✗ Configuration has errors:", curses.A_BOLD)
                    lines = output.split('\n')
                    for i, line in enumerate(lines[:10]):  # Show first 10 lines
                        stdscr.addstr(6 + i, 2, line[:curses.COLS - 4])
                
                stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
                stdscr.getch()
            
            elif key == ord('4'):  # Back
                break
    
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
            nav_info = "↑/↓: Scroll, q: Quit, r: Refresh"
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
        stdscr.getch()
        
        # Collect email for Certbot
        stdscr.clear()
        stdscr.addstr(1, 2, "SSL Certificate Configuration")
        stdscr.addstr(2, 2, "=" * 29)
        stdscr.addstr(4, 2, "For SSL certificates, we need an email address for Let's Encrypt.")
        stdscr.addstr(5, 2, "This email will be used for certificate notifications.")
        stdscr.addstr(7, 2, "Leave empty to use domain-specific emails (admin@domain.com)")
        
        email = self._get_input(stdscr, "Email address", 9, 2)
        if email:
            self.manager.config['certbot_email'] = email
        
        # Ask about auto-backup
        stdscr.clear()
        stdscr.addstr(1, 2, "Backup Configuration")
        stdscr.addstr(2, 2, "=" * 20)
        stdscr.addstr(4, 2, "Would you like to enable automatic backups before making changes?")
        
        auto_backup = self._get_input(stdscr, "Enable auto-backup? (y/N)", 6, 2, "y")
        self.manager.config['auto_backup'] = auto_backup.lower() in ['y', 'yes']
        
        # Ask about default SSL
        stdscr.clear()
        stdscr.addstr(1, 2, "Default SSL Setting")
        stdscr.addstr(2, 2, "=" * 19)
        stdscr.addstr(4, 2, "Would you like SSL to be enabled by default for new domains?")
        
        default_ssl = self._get_input(stdscr, "Enable SSL by default? (Y/n)", 6, 2, "y")
        self.manager.config['default_ssl'] = default_ssl.lower() not in ['n', 'no']
        
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
        y_pos += 2
        
        stdscr.addstr(y_pos, 2, "Press any key to save configuration and continue...")
        stdscr.refresh()
        stdscr.getch()
        
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
        stdscr.getch()
    
    def _settings_menu(self, stdscr):
        """Settings management menu"""
        settings_options = [
            "Change Certbot Email",
            "Toggle Auto-backup",
            "Toggle Default SSL",
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
            
            stdscr.addstr(curses.LINES - 2, 2, "Use ↑/↓ to navigate, Enter to select")
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
                elif current_selection == 3:  # View Current Settings
                    self._view_current_settings(stdscr)
                elif current_selection == 4:  # Reset to Defaults
                    self._reset_settings(stdscr)
                elif current_selection == 5:  # Back
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
        stdscr.addstr(6, 2, "Leave empty to use domain-specific emails")
        
        new_email = self._get_input(stdscr, "New email address", 8, 2)
        
        if new_email:
            self.manager.config['certbot_email'] = new_email
            message = f"Email updated to: {new_email}"
        else:
            if 'certbot_email' in self.manager.config:
                del self.manager.config['certbot_email']
            message = "Email cleared - will use domain-specific emails"
        
        self.manager.save_config()
        self._show_message(stdscr, "Success", message)
    
    def _toggle_auto_backup(self, stdscr):
        """Toggle auto-backup setting"""
        current_setting = self.manager.config.get('auto_backup', False)
        new_setting = not current_setting
        self.manager.config['auto_backup'] = new_setting
        self.manager.save_config()
        
        status = "enabled" if new_setting else "disabled"
        self._show_message(stdscr, "Success", f"Auto-backup {status}")
    
    def _toggle_default_ssl(self, stdscr):
        """Toggle default SSL setting"""
        current_setting = self.manager.config.get('default_ssl', True)
        new_setting = not current_setting
        self.manager.config['default_ssl'] = new_setting
        self.manager.save_config()
        
        status = "enabled" if new_setting else "disabled"
        self._show_message(stdscr, "Success", f"Default SSL {status}")
    
    def _view_current_settings(self, stdscr):
        """View current settings"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Current Settings")
        stdscr.addstr(2, 2, "=" * 16)
        
        y_pos = 4
        email = self.manager.config.get('certbot_email', 'Domain-specific')
        stdscr.addstr(y_pos, 2, f"Certbot Email: {email}")
        y_pos += 1
        
        auto_backup = 'Yes' if self.manager.config.get('auto_backup', False) else 'No'
        stdscr.addstr(y_pos, 2, f"Auto-backup: {auto_backup}")
        y_pos += 1
        
        default_ssl = 'Yes' if self.manager.config.get('default_ssl', True) else 'No'
        stdscr.addstr(y_pos, 2, f"Default SSL: {default_ssl}")
        y_pos += 1
        
        setup_completed = 'Yes' if self.manager.config.get('setup_completed', False) else 'No'
        stdscr.addstr(y_pos, 2, f"Setup Completed: {setup_completed}")
        y_pos += 2
        
        stdscr.addstr(y_pos, 2, f"Config file: {CONFIG_FILE}")
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()
    
    def _reset_settings(self, stdscr):
        """Reset settings to defaults"""
        if self._confirm_action(stdscr, "Reset all settings to defaults?\n\nThis will clear your custom configuration."):
            self.manager.config = {'setup_completed': True}
            self.manager.save_config()
            self._show_message(stdscr, "Success", "Settings reset to defaults")

def main():
    """Main entry point"""
    try:
        # Check if running as root (required for nginx operations)
        if os.geteuid() != 0:
            print("This script must be run as root (sudo) to manage NGINX configurations.")
            sys.exit(1)
        
        manager = VPSManager()
        ui = TerminalUI(manager)
        ui.run()
        
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
        Logger.error(f"Application error: {e}")

if __name__ == "__main__":
    main()