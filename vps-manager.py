#!/usr/bin/env python3
"""
VPS NGINX Domain Manager
A comprehensive terminal-based manager for NGINX domains, SSL certificates, and configurations.

Author: k6w
Version: 1.2.0
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
import signal
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import urllib.request

# Version and Update Configuration
VERSION = "1.2.3"
CONFIG_VERSION = "1.2.3"  # Increment when new config options are added
UPDATE_URL = "https://raw.githubusercontent.com/k6w/vps-manager/main/vps-manager.py"
VERSION_URL = "https://raw.githubusercontent.com/k6w/vps-manager/main/VERSION"

# Configuration
# Use the actual user's home directory, not root's home when running with sudo
if os.environ.get('SUDO_USER'):
    MANAGER_DIR = Path(f"/home/{os.environ['SUDO_USER']}") / "manager"
else:
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
        self.config['config_version'] = CONFIG_VERSION  # Set current config version
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
        """Validate domain name format including full subdomain support"""
        if not domain or len(domain) > 253:
            return False
        
        # Allow localhost for development
        if domain.lower() == 'localhost':
            return True
        
        # Split domain into parts
        parts = domain.split('.')
        
        # Must have at least 2 parts for a valid domain (e.g., example.com)
        # But allow single part for development (e.g., localhost, internal names)
        if len(parts) < 1:
            return False
        
        # Validate each part
        for part in parts:
            if not part:  # Empty part (consecutive dots)
                return False
            if len(part) > 63:  # Each label max 63 chars
                return False
            if part.startswith('-') or part.endswith('-'):  # Can't start/end with hyphen
                return False
            if not re.match(r'^[a-zA-Z0-9-]+$', part):  # Only alphanumeric and hyphens
                return False
        
        # Additional validation for full domain format
        # Supports multi-level subdomains like api.v1.subdomain.example.com
        full_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(full_pattern, domain))
    
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
    
    def get_external_ip(self) -> str:
        """Get the external IP address of the VPS"""
        try:
            # Try multiple services to get external IP
            services = [
                'https://ipv4.icanhazip.com',
                'https://api.ipify.org',
                'https://checkip.amazonaws.com'
            ]
            
            for service in services:
                try:
                    import urllib.request
                    with urllib.request.urlopen(service, timeout=5) as response:
                        ip = response.read().decode('utf-8').strip()
                        # Validate IP format
                        import re
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                            Logger.info(f"External IP detected: {ip}")
                            return ip
                except Exception as e:
                    Logger.warning(f"Failed to get IP from {service}: {e}")
                    continue
            
            # Fallback: try to get IP from network interface
            success, output = self.run_command("hostname -I | awk '{print $1}'")
            if success and output.strip():
                ip = output.strip()
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                    Logger.info(f"Local IP detected: {ip}")
                    return ip
            
            Logger.warning("Could not determine external IP, falling back to 127.0.0.1")
            return "127.0.0.1"
            
        except Exception as e:
            Logger.error(f"Error getting external IP: {e}")
            return "127.0.0.1"
    
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
            
            # Generate initial NGINX configuration (HTTP-only if SSL is needed)
            temp_http_only = ssl  # Use HTTP-only config initially if SSL is requested
            success, message = self.generate_nginx_config(domain, temp_http_only)
            if not success:
                return False, f"Failed to generate NGINX config: {message}"
            
            # Enable site
            success, message = self.enable_site(name)
            if not success:
                return False, f"Failed to enable site: {message}"
            
            # Test and reload NGINX first to make the configuration active
            success, message = self.test_and_reload_nginx()
            if not success:
                return False, f"NGINX configuration test failed: {message}"
            
            # Generate SSL certificate and update config to HTTPS if needed
            if ssl:
                success, message = self.generate_ssl_certificate(name)
                if not success:
                    return False, f"Failed to generate SSL certificate: {message}"
                
                # Regenerate NGINX config with full HTTPS configuration
                success, message = self.generate_nginx_config(domain, temp_http_only=False)
                if not success:
                    return False, f"Failed to generate HTTPS NGINX config: {message}"
                
                # Test and reload NGINX again with HTTPS config
                success, message = self.test_and_reload_nginx()
                if not success:
                    return False, f"NGINX HTTPS configuration test failed: {message}"
            
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
            
            # Generate initial NGINX configuration (HTTP-only if SSL is needed)
            temp_http_only = domain.ssl  # Use HTTP-only config initially if SSL is requested
            success, message = self.generate_nginx_config(domain, temp_http_only)
            if not success:
                return False, f"Failed to generate NGINX config: {message}"
            
            # Enable site
            success, message = self.enable_site(domain.name)
            if not success:
                return False, f"Failed to enable site: {message}"
            
            # Test and reload NGINX first to make the configuration active
            success, message = self.test_and_reload_nginx()
            if not success:
                return False, f"NGINX configuration test failed: {message}"
            
            # Handle SSL certificate generation and update config to HTTPS if needed
            if domain.ssl:
                success, message = self.generate_ssl_certificate(domain.name)
                if not success:
                    return False, f"Failed to generate SSL certificate: {message}"
                
                # Regenerate NGINX config with full HTTPS configuration
                success, message = self.generate_nginx_config(domain, temp_http_only=False)
                if not success:
                    return False, f"Failed to generate HTTPS NGINX config: {message}"
                
                # Test and reload NGINX again with HTTPS config
                success, message = self.test_and_reload_nginx()
                if not success:
                    return False, f"NGINX HTTPS configuration test failed: {message}"
            
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
    
    def generate_nginx_config(self, domain: Domain, temp_http_only: bool = False) -> Tuple[bool, str]:
        """Generate NGINX configuration for a domain
        
        Args:
            domain: Domain object
            temp_http_only: If True, generate HTTP-only config even for SSL domains (for initial setup)
        """
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
            
            # Get backend IP (use external VPS IP instead of 127.0.0.1 for Docker compatibility)
            backend_ip = self.get_external_ip() or "127.0.0.1"
            
            config_content = template_content.replace('$DOMAIN', domain.name)
            config_content = config_content.replace('$PORT', str(domain.port))
            config_content = config_content.replace('$SSL_CERT_PATH', ssl_cert_path)
            config_content = config_content.replace('$SSL_KEY_PATH', ssl_key_path)
            config_content = config_content.replace('$BACKEND_IP', backend_ip)
            
            # If SSL is disabled OR we need temp HTTP-only config, use only HTTP configuration
            if not domain.ssl or temp_http_only:
                # Extract only HTTP server block (the last one in the template)
                lines = config_content.split('\n')
                http_config = []
                in_http_block = False
                brace_count = 0
                last_server_start = -1
                
                # Find the last server block (HTTP-only block)
                for i, line in enumerate(lines):
                    if 'server {' in line:
                        last_server_start = i
                
                # Extract from the last server block
                if last_server_start >= 0:
                    for i in range(last_server_start, len(lines)):
                        line = lines[i]
                        if 'server {' in line:
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
            
            config_type = "HTTP-only" if (not domain.ssl or temp_http_only) else "HTTPS"
            Logger.info(f"NGINX {config_type} configuration generated for {domain.name}")
            return True, f"{config_type} configuration generated successfully"
            
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
            
            # Check if source configuration exists
            if not source.exists():
                Logger.error(f"Source configuration file does not exist: {source}")
                return False, f"Configuration file {source} not found"
            
            # Ensure sites-enabled directory exists
            NGINX_ENABLED_DIR.mkdir(parents=True, exist_ok=True)
            
            # Remove existing symlink if it exists
            if target.exists() or target.is_symlink():
                target.unlink()
            
            # Create the symbolic link
            target.symlink_to(source)
            
            # Verify the link was created successfully
            if target.exists() and target.is_symlink():
                Logger.info(f"Site {domain_name} enabled successfully")
                return True, "Site enabled successfully"
            else:
                Logger.error(f"Failed to verify symbolic link for {domain_name}")
                return False, "Failed to create symbolic link"
            
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
    
    def create_domain_backup(self, domain_name: str) -> Tuple[bool, str]:
        """Create backup for a specific domain before making changes"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"domain_{domain_name}_{timestamp}"
            backup_path = BACKUP_DIR / f"{backup_name}.tar.gz"
            
            # Create temporary directory for backup
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_backup_dir = Path(temp_dir) / backup_name
                temp_backup_dir.mkdir()
                
                # Backup domain configuration from domains.json
                domain = self.get_domain(domain_name)
                if domain:
                    domain_config_file = temp_backup_dir / "domain.json"
                    with open(domain_config_file, 'w') as f:
                        json.dump(domain.to_dict(), f, indent=2)
                
                # Backup NGINX configuration
                nginx_config = NGINX_SITES_DIR / domain_name
                if nginx_config.exists():
                    shutil.copy2(nginx_config, temp_backup_dir / f"{domain_name}.conf")
                
                # Backup SSL certificates if they exist
                ssl_dir = Path(f"/etc/letsencrypt/live/{domain_name}")
                if ssl_dir.exists():
                    ssl_backup_dir = temp_backup_dir / "ssl"
                    ssl_backup_dir.mkdir()
                    try:
                        shutil.copytree(ssl_dir, ssl_backup_dir / domain_name, dirs_exist_ok=True)
                    except PermissionError:
                        Logger.warning(f"Could not backup SSL certificates for {domain_name} (permission denied)")
                
                # Create tar.gz archive
                shutil.make_archive(str(backup_path.with_suffix('')), 'gztar', temp_dir, backup_name)
            
            Logger.info(f"Domain backup created: {backup_path}")
            return True, f"Backup created successfully: {backup_path.name}"
            
        except Exception as e:
            Logger.error(f"Failed to create domain backup for {domain_name}: {e}")
            return False, str(e)
    
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
    
    def uninstall_manager(self, delete_ssl: bool = False, delete_domains: bool = False) -> Tuple[bool, str]:
        """Uninstall VPS Manager completely"""
        try:
            Logger.info("Starting VPS Manager uninstall process")
            
            # Stop and disable systemd service if it exists
            service_file = Path("/etc/systemd/system/vps-manager.service")
            if service_file.exists():
                Logger.info("Stopping and disabling systemd service")
                self.run_command("systemctl stop vps-manager")
                self.run_command("systemctl disable vps-manager")
                service_file.unlink()
                self.run_command("systemctl daemon-reload")
            
            # Remove symbolic link
            symlink_path = Path("/usr/local/bin/vps-manager")
            if symlink_path.exists():
                Logger.info("Removing symbolic link")
                symlink_path.unlink()
            
            # Handle SSL certificates if requested
            if delete_ssl:
                Logger.info("Removing SSL certificates")
                for domain in self.domains:
                    if domain.ssl:
                        cert_path = f"/etc/letsencrypt/live/{domain.name}"
                        if Path(cert_path).exists():
                            success, output = self.run_command(f"certbot delete --cert-name {domain.name} --non-interactive")
                            if success:
                                Logger.info(f"Removed SSL certificate for {domain.name}")
                            else:
                                Logger.warning(f"Failed to remove SSL certificate for {domain.name}: {output}")
            
            # Handle domain configurations if requested
            if delete_domains:
                Logger.info("Removing domain configurations")
                for domain in self.domains:
                    # Remove NGINX site configuration
                    site_file = NGINX_SITES_DIR / domain.name
                    enabled_file = NGINX_ENABLED_DIR / domain.name
                    
                    if enabled_file.exists():
                        enabled_file.unlink()
                        Logger.info(f"Removed enabled site for {domain.name}")
                    
                    if site_file.exists():
                        site_file.unlink()
                        Logger.info(f"Removed site configuration for {domain.name}")
                
                # Reload NGINX after removing configurations
                success, output = self.run_command("nginx -t")
                if success:
                    self.run_command("systemctl reload nginx")
                    Logger.info("NGINX reloaded successfully")
                else:
                    Logger.warning(f"NGINX configuration test failed: {output}")
            
            # Remove manager directory and all its contents
            if MANAGER_DIR.exists():
                Logger.info(f"Removing manager directory: {MANAGER_DIR}")
                shutil.rmtree(MANAGER_DIR)
            
            Logger.info("VPS Manager uninstall completed successfully")
            return True, "VPS Manager has been uninstalled successfully."
            
        except Exception as e:
            error_msg = f"Failed to uninstall VPS Manager: {e}"
            Logger.error(error_msg)
            return False, error_msg
    
    def check_for_updates(self) -> Tuple[bool, str, str]:
        """Check if updates are available
        Returns: (has_update, current_version, latest_version)
        """
        try:
            with urllib.request.urlopen(VERSION_URL, timeout=10) as response:
                latest_version = response.read().decode('utf-8').strip()
                
            current_version = VERSION
            has_update = self._compare_versions(current_version, latest_version) < 0
            
            return has_update, current_version, latest_version
            
        except Exception as e:
            Logger.error(f"Failed to check for updates: {e}")
            return False, VERSION, VERSION
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings
        Returns: -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        def version_tuple(v):
            return tuple(map(int, (v.split("."))))
        
        try:
            v1_tuple = version_tuple(v1)
            v2_tuple = version_tuple(v2)
            
            if v1_tuple < v2_tuple:
                return -1
            elif v1_tuple > v2_tuple:
                return 1
            else:
                return 0
        except ValueError:
            return 0
    
    def download_update(self) -> Tuple[bool, str]:
        """Download and install updates
        Returns: (success, message)
        """
        try:
            # Create backup of current version
            current_script = Path(__file__)
            backup_path = current_script.parent / f"vps-manager.py.backup.{VERSION}"
            shutil.copy2(current_script, backup_path)
            Logger.info(f"Created backup at {backup_path}")
            
            # Download new version
            with urllib.request.urlopen(UPDATE_URL, timeout=30) as response:
                new_content = response.read().decode('utf-8')
            
            # Write new version
            with open(current_script, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            Logger.info("Update downloaded and installed successfully")
            return True, "Update installed successfully. Please restart the application."
            
        except Exception as e:
            Logger.error(f"Failed to download update: {e}")
            return False, f"Failed to download update: {e}"
    
    def bump_version(self, bump_type: str = "patch") -> Tuple[bool, str]:
        """Automatically bump version number
        Args:
            bump_type: 'major', 'minor', or 'patch'
        Returns: (success, new_version)
        """
        try:
            current_version = VERSION
            major, minor, patch = map(int, current_version.split('.'))
            
            if bump_type == "major":
                major += 1
                minor = 0
                patch = 0
            elif bump_type == "minor":
                minor += 1
                patch = 0
            elif bump_type == "patch":
                patch += 1
            else:
                return False, f"Invalid bump type: {bump_type}"
            
            new_version = f"{major}.{minor}.{patch}"
            
            # Update VERSION constant in the script
            success = self._update_version_in_file(new_version)
            if not success:
                return False, "Failed to update version in script"
            
            # Update VERSION file
            version_file = Path(__file__).parent / "VERSION"
            with open(version_file, 'w') as f:
                f.write(new_version)
            
            Logger.info(f"Version bumped from {current_version} to {new_version}")
            return True, new_version
            
        except Exception as e:
            Logger.error(f"Failed to bump version: {e}")
            return False, f"Failed to bump version: {e}"
    
    def _update_version_in_file(self, new_version: str) -> bool:
        """Update the VERSION constant in the script file"""
        try:
            script_path = Path(__file__)
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace VERSION constant
            import re
            pattern = r'VERSION = "[0-9]+\.[0-9]+\.[0-9]+"'
            replacement = f'VERSION = "{new_version}"'
            new_content = re.sub(pattern, replacement, content)
            
            if new_content == content:
                return False  # No replacement made
            
            # Create backup before modifying
            backup_path = script_path.parent / f"vps-manager.py.backup.{VERSION}"
            shutil.copy2(script_path, backup_path)
            
            # Write updated content
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True
            
        except Exception as e:
            Logger.error(f"Failed to update version in file: {e}")
            return False
    
    def validate_version_consistency(self) -> Tuple[bool, str]:
        """Check if VERSION constant matches VERSION file
        Returns: (is_consistent, message)
        """
        try:
            version_file = Path(__file__).parent / "VERSION"
            if not version_file.exists():
                return False, "VERSION file does not exist"
            
            with open(version_file, 'r') as f:
                file_version = f.read().strip()
            
            script_version = VERSION
            
            if file_version == script_version:
                return True, f"Version consistency OK: {script_version}"
            else:
                return False, f"Version mismatch - Script: {script_version}, File: {file_version}"
                
        except Exception as e:
            Logger.error(f"Failed to validate version consistency: {e}")
            return False, f"Failed to validate version consistency: {e}"
    
    def is_valid_version(self, version: str) -> bool:
        """Check if version string follows semantic versioning (x.y.z)"""
        try:
            parts = version.split('.')
            if len(parts) != 3:
                return False
            
            for part in parts:
                if not part.isdigit() or int(part) < 0:
                    return False
            
            return True
        except:
            return False
    
    def sync_version_file(self) -> Tuple[bool, str]:
        """Sync VERSION file with script VERSION constant"""
        try:
            version_file = Path(__file__).parent / "VERSION"
            with open(version_file, 'w') as f:
                f.write(VERSION)
            
            Logger.info(f"VERSION file synced with script version: {VERSION}")
            return True, f"VERSION file updated to {VERSION}"
            
        except Exception as e:
            Logger.error(f"Failed to sync VERSION file: {e}")
            return False, f"Failed to sync VERSION file: {e}"
    
    def auto_update_check(self) -> bool:
        """Check if auto-update is enabled in config"""
        return self.config.get('auto_update', False)
    
    def get_config_version(self) -> str:
        """Get the config version from saved configuration"""
        return self.config.get('config_version', '1.0.0')
    
    def update_config_version(self):
        """Update config version to current version"""
        self.config['config_version'] = CONFIG_VERSION
        self.save_config()
    

    

    
    def get_missing_config_options(self) -> List[str]:
        """Get list of config options that are missing or new"""
        current_config_version = self.get_config_version()
        missing_options = []
        
        # Define config options by version
        config_options_by_version = {
            '1.0.0': ['certbot_email', 'auto_backup', 'default_ssl', 'setup_completed'],
            '1.1.0': ['auto_update']  # New in version 1.1.0
        }
        
        # Check which options are missing based on version progression
        if self._compare_versions(current_config_version, '1.1.0') < 0:
            if 'auto_update' not in self.config:
                missing_options.append('auto_update')
        
        return missing_options
    
    def needs_selective_onboarding(self) -> bool:
        """Check if selective onboarding is needed for new config options"""
        return len(self.get_missing_config_options()) > 0
    
    def run_selective_onboarding(self, ui_instance):
        """Run selective onboarding for missing config options"""
        missing_options = self.get_missing_config_options()
        if not missing_options:
            return
        
        # Run the selective onboarding UI
        import curses
        curses.wrapper(ui_instance._selective_onboarding_flow, missing_options)
        
        # Update config version after selective onboarding
        self.update_config_version()

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
        stdscr.addstr(footer_y + 1, 2, "↑/↓: Navigate | Enter/Space: Select | ESC/Ctrl+C/Ctrl+X/Q: Exit")
    
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
        
        # Flush input buffer to prevent key release detection
        stdscr.nodelay(True)
        while stdscr.getch() != -1:
            pass
        stdscr.nodelay(False)
        
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
        stdscr.getch()
        
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
        stdscr.getch()
    
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
                elif current_selection == 3:  # Toggle Auto-update
                    self._toggle_auto_update(stdscr)
                elif current_selection == 4:  # Check for Updates
                    self._manual_update_check(stdscr)
                elif current_selection == 5:  # View Current Settings
                    self._view_current_settings(stdscr)
                elif current_selection == 6:  # Reset to Defaults
                    self._reset_settings(stdscr)
                elif current_selection == 7:  # Back
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
        if new_email is None:  # User cancelled
            return
        
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
        
        # Show detailed status message
        stdscr.clear()
        stdscr.addstr(1, 2, "Auto-backup Setting")
        stdscr.addstr(2, 2, "=" * 18)
        stdscr.addstr(4, 2, f"Auto-backup has been {status}.", curses.A_BOLD)
        
        if new_setting:
            stdscr.addstr(6, 2, "Automatic backups will now be created before making changes.")
        else:
            stdscr.addstr(6, 2, "Automatic backups are now disabled.")
            stdscr.addstr(7, 2, "You can still create manual backups from the main menu.")
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()
    
    def _toggle_default_ssl(self, stdscr):
        """Toggle default SSL setting"""
        current_setting = self.manager.config.get('default_ssl', True)
        new_setting = not current_setting
        self.manager.config['default_ssl'] = new_setting
        self.manager.save_config()
        
        status = "enabled" if new_setting else "disabled"
        
        # Show detailed status message
        stdscr.clear()
        stdscr.addstr(1, 2, "Default SSL Setting")
        stdscr.addstr(2, 2, "=" * 19)
        stdscr.addstr(4, 2, f"Default SSL has been {status}.", curses.A_BOLD)
        
        if new_setting:
            stdscr.addstr(6, 2, "SSL will now be enabled by default for new domains.")
            stdscr.addstr(7, 2, "SSL certificates will be automatically generated.")
        else:
            stdscr.addstr(6, 2, "SSL is now disabled by default for new domains.")
            stdscr.addstr(7, 2, "You can still enable SSL manually when adding domains.")
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        stdscr.refresh()
        
        # Flush input buffer to prevent key release detection
        stdscr.nodelay(True)
        while stdscr.getch() != -1:
            pass
        stdscr.nodelay(False)
        
        stdscr.getch()
    
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
        
        auto_update = 'Yes' if self.manager.config.get('auto_update', True) else 'No'
        stdscr.addstr(y_pos, 2, f"Auto-update: {auto_update}")
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
    
    def _toggle_auto_update(self, stdscr):
        """Toggle auto-update setting"""
        current_setting = self.manager.config.get('auto_update', False)
        new_setting = not current_setting
        self.manager.config['auto_update'] = new_setting
        self.manager.save_config()
        
        status = "enabled" if new_setting else "disabled"
        
        # Show detailed status message
        stdscr.clear()
        stdscr.addstr(1, 2, "Auto-update Setting")
        stdscr.addstr(2, 2, "=" * 19)
        stdscr.addstr(4, 2, f"Auto-update has been {status}.", curses.A_BOLD)
        
        if new_setting:
            stdscr.addstr(6, 2, "The script will now check for updates automatically.")
            stdscr.addstr(7, 2, "Updates will be downloaded and applied when available.")
        else:
            stdscr.addstr(6, 2, "Automatic updates are now disabled.")
            stdscr.addstr(7, 2, "You can still check for updates manually from the main menu.")
        
        stdscr.addstr(curses.LINES - 2, 2, "Press any key to continue...")
        stdscr.refresh()
        
        # Flush input buffer to prevent key release detection
        stdscr.nodelay(True)
        while stdscr.getch() != -1:
            pass
        stdscr.nodelay(False)
        
        stdscr.getch()
    
    def _manual_update_check(self, stdscr):
        """Manually check for updates"""
        stdscr.clear()
        stdscr.addstr(1, 2, "Checking for Updates")
        stdscr.addstr(2, 2, "=" * 20)
        stdscr.addstr(4, 2, "Checking for available updates...")
        stdscr.refresh()
        
        try:
            has_update, current_version, latest_version = self.manager.check_for_updates()
            
            stdscr.clear()
            stdscr.addstr(1, 2, "Update Check Results")
            stdscr.addstr(2, 2, "=" * 20)
            stdscr.addstr(4, 2, f"Current version: v{current_version}")
            stdscr.addstr(5, 2, f"Latest version:  v{latest_version}")
            
            if has_update:
                stdscr.addstr(7, 2, "Update available!", curses.A_BOLD)
                stdscr.addstr(9, 2, "Would you like to download and install the update?")
                stdscr.addstr(10, 2, "Press 'y' to update, any other key to cancel")
                stdscr.refresh()
                
                key = stdscr.getch()
                if key == ord('y') or key == ord('Y'):
                    stdscr.clear()
                    stdscr.addstr(1, 2, "Downloading Update")
                    stdscr.addstr(2, 2, "=" * 18)
                    stdscr.addstr(4, 2, "Downloading and installing update...")
                    stdscr.refresh()
                    
                    success, message = self.manager.download_update()
                    if success:
                        self._show_message(stdscr, "Success", f"{message}\n\nPlease restart the application.")
                    else:
                        self._show_message(stdscr, "Error", f"Update failed: {message}")
                else:
                    self._show_message(stdscr, "Cancelled", "Update cancelled")
            else:
                stdscr.addstr(7, 2, "You are running the latest version!", curses.A_BOLD)
                stdscr.addstr(9, 2, "Press any key to continue...")
                stdscr.refresh()
                stdscr.getch()
                
        except Exception as e:
            self._show_message(stdscr, "Error", f"Failed to check for updates: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\nShutting down gracefully...")
    sys.exit(0)



def run_uninstall():
    """Run the uninstall process with user prompts"""
    print("\n" + "=" * 50)
    print("VPS Manager Uninstall")
    print("=" * 50)
    print("\nThis will completely remove VPS Manager from your system.")
    print("\nThe following will be removed:")
    print("• VPS Manager application files")
    print("• Systemd service")
    print("• Symbolic links")
    print("• Configuration files and logs")
    
    # Confirm uninstall
    try:
        confirm = input("\nDo you want to proceed with the uninstall? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("Uninstall cancelled.")
            return
        
        # Initialize manager to access domains and uninstall method
        manager = VPSManager()
        
        # Check if there are any domains configured
        delete_ssl = False
        delete_domains = False
        
        if manager.domains:
            print(f"\nFound {len(manager.domains)} configured domain(s):")
            for domain in manager.domains:
                ssl_status = "(SSL enabled)" if domain.ssl else "(SSL disabled)"
                print(f"  • {domain.name} {ssl_status}")
            
            # Ask about SSL certificates
            ssl_domains = [d for d in manager.domains if d.ssl]
            if ssl_domains:
                print(f"\nFound {len(ssl_domains)} domain(s) with SSL certificates.")
                ssl_choice = input("Do you want to delete SSL certificates? (y/N): ").strip().lower()
                delete_ssl = ssl_choice in ['y', 'yes']
                
                if delete_ssl:
                    print("⚠️  SSL certificates will be permanently deleted!")
                else:
                    print("SSL certificates will be preserved.")
            
            # Ask about domain configurations
            print(f"\nFound {len(manager.domains)} NGINX domain configuration(s).")
            domain_choice = input("Do you want to delete domain configurations? (y/N): ").strip().lower()
            delete_domains = domain_choice in ['y', 'yes']
            
            if delete_domains:
                print("⚠️  Domain configurations will be permanently deleted!")
            else:
                print("Domain configurations will be preserved.")
        
        # Final confirmation
        print("\n" + "-" * 50)
        print("UNINSTALL SUMMARY:")
        print(f"• Remove VPS Manager: YES")
        print(f"• Delete SSL certificates: {'YES' if delete_ssl else 'NO'}")
        print(f"• Delete domain configurations: {'YES' if delete_domains else 'NO'}")
        print("-" * 50)
        
        final_confirm = input("\nProceed with uninstall? (y/N): ").strip().lower()
        if final_confirm not in ['y', 'yes']:
            print("Uninstall cancelled.")
            return
        
        # Perform uninstall
        print("\nUninstalling VPS Manager...")
        success, message = manager.uninstall_manager(delete_ssl, delete_domains)
        
        if success:
            print(f"\n✅ {message}")
            if not delete_ssl and ssl_domains:
                print("\n📋 Note: SSL certificates were preserved and can be managed manually with certbot.")
            if not delete_domains and manager.domains:
                print("📋 Note: Domain configurations were preserved in /etc/nginx/sites-available/.")
            print("\nThank you for using VPS Manager!")
        else:
            print(f"\n❌ {message}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nUninstall cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ An error occurred during uninstall: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='VPS NGINX Domain Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                    # Start interactive manager
  %(prog)s --uninstall        # Uninstall VPS Manager
'''
    )
    parser.add_argument('--uninstall', action='store_true',
                       help='Uninstall VPS Manager completely')

    
    args = parser.parse_args()
    
    # Handle uninstall
    if args.uninstall:
        run_uninstall()
        return
    

    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Check if running as root/administrator (required for nginx operations)
        # Skip this check on Windows for development/testing
        if os.name != 'nt':  # Not Windows
            if hasattr(os, 'geteuid') and os.geteuid() != 0:
                print("This script must be run as root (sudo) to manage NGINX configurations.")
                sys.exit(1)
        
        manager = VPSManager()
        
        # Check for updates if auto-update is enabled
        if manager.auto_update_check() and not manager.is_first_run():
            try:
                has_update, current_version, latest_version = manager.check_for_updates()
                if has_update:
                    print(f"\nUpdate available: v{current_version} -> v{latest_version}")
                    response = input("Would you like to download and install the update? (y/N): ")
                    if response.lower() in ['y', 'yes']:
                        success, message = manager.download_update()
                        print(f"\n{message}")
                        if success:
                            print("Please restart the application to use the new version.")
                            sys.exit(0)
                    else:
                        print("Update skipped. You can update later from the settings menu.")
            except Exception as e:
                Logger.error(f"Auto-update check failed: {e}")
        
        ui = TerminalUI(manager)
        
        # Check for selective onboarding (new config options after updates)
        if not manager.is_first_run() and manager.needs_selective_onboarding():
            manager.run_selective_onboarding(ui)
        
        ui.run()
        
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
        Logger.error(f"Application error: {e}")

if __name__ == "__main__":
    main()