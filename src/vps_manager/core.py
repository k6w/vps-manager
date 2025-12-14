import json
import subprocess
import shutil
import re
import tempfile
import socket
import datetime
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .utils import (
    MANAGER_DIR, NGINX_SITES_DIR, NGINX_ENABLED_DIR, 
    BACKUP_DIR, TEMPLATES_DIR, DATA_FILE, CONFIG_FILE, 
    get_logger
)
from .config import ConfigManager

logger = get_logger(__name__)

VERSION = "2.0.0"
CONFIG_VERSION = "2.0.0"
UPDATE_URL = "https://github.com/k6w/vps-manager" # Package-based updates via pip/git
VERSION_URL = "https://raw.githubusercontent.com/k6w/vps-manager/main/VERSION"

class Domain:
    """Domain configuration class"""
    
    def __init__(self, name: str, port: int, ssl: bool = True, custom_config: str = None, 
                 wildcard: bool = False, backend_ip: str = None):
        self.name = name
        self.port = port
        self.ssl = ssl
        self.custom_config = custom_config
        self.wildcard = wildcard  # Support for wildcard SSL certificates
        self.backend_ip = backend_ip  # Custom backend IP (for Docker containers)
        self.created_at = datetime.datetime.now().isoformat()
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "port": self.port,
            "ssl": self.ssl,
            "custom_config": self.custom_config,
            "wildcard": self.wildcard,
            "backend_ip": self.backend_ip,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        domain = cls(
            data["name"], 
            data["port"], 
            data["ssl"], 
            data.get("custom_config"),
            data.get("wildcard", False),
            data.get("backend_ip")
        )
        domain.created_at = data.get("created_at", domain.created_at)
        domain.updated_at = data.get("updated_at", domain.updated_at)
        return domain

class VPSManager:
    """Main VPS Manager class"""
    
    def __init__(self):
        self.domains: List[Domain] = []
        self.config: Dict = {}
        self.config_manager = ConfigManager()
        self.setup_directories()
        self.load_config()
        self.load_domains()
        
        # Initialize new modules (lazy loading to avoid circular imports)
        self._firewall_manager = None
        self._security_scanner = None
        self._alert_manager = None
        self._docker_manager = None
        self._version_control = None
    
    def is_first_run(self) -> bool:
        """Check if this is the first run"""
        return self.config_manager.is_first_run()
    
    def mark_first_run_complete(self):
        """Mark first run as complete"""
        self.config_manager.mark_first_run_complete()
    
    def get_missing_config_options(self) -> list:
        """Get list of features that need configuration"""
        return self.config_manager.get_missing_config_options()
    
    def needs_selective_onboarding(self) -> bool:
        """Check if selective onboarding is needed"""
        return self.config_manager.needs_selective_onboarding()
    
    @property
    def firewall(self):
        """Get firewall manager instance"""
        if self._firewall_manager is None:
            from .firewall import FirewallManager
            self._firewall_manager = FirewallManager(self)
        return self._firewall_manager
    
    @property
    def security(self):
        """Get security scanner instance"""
        if self._security_scanner is None:
            from .security import SecurityScanner
            self._security_scanner = SecurityScanner(self)
        return self._security_scanner
    
    @property
    def alerts(self):
        """Get alert manager instance"""
        if self._alert_manager is None:
            from .alerts import AlertManager
            self._alert_manager = AlertManager(self)
        return self._alert_manager
    
    @property
    def docker(self):
        """Get Docker manager instance"""
        if self._docker_manager is None:
            from .docker_manager import DockerManager
            self._docker_manager = DockerManager(self)
        return self._docker_manager
    
    @property
    def vcs(self):
        """Get version control system instance"""
        if self._version_control is None:
            from .version_control import VersionControl
            self._version_control = VersionControl(self)
        return self._version_control
    
    def setup_directories(self):
        """Create necessary directories"""
        directories = [MANAGER_DIR, BACKUP_DIR, TEMPLATES_DIR, MANAGER_DIR / "custom-configs"]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        logger.info("Directories setup completed")
    
    def load_config(self):
        """Load configuration settings"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
                logger.info("Configuration loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self.config = {}
        else:
            self.config = {}
    
    def save_config(self):
        """Save configuration settings"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def is_first_run(self) -> bool:
        """Check if this is the first run"""
        return not CONFIG_FILE.exists() or not self.config.get('setup_completed', False)
    
    def complete_setup(self):
        """Mark setup as completed"""
        self.config['setup_completed'] = True
        self.config['config_version'] = CONFIG_VERSION
        self.save_config()
    
    def load_domains(self):
        """Load domains from JSON file"""
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.domains = [Domain.from_dict(d) for d in data]
                logger.info(f"Loaded {len(self.domains)} domains")
            except Exception as e:
                logger.error(f"Failed to load domains: {e}")
                self.domains = []
        
        # Import existing nginx configurations if domains list is empty
        if len(self.domains) == 0:
            imported = self.import_existing_domains()
            if imported > 0:
                logger.info(f"Imported {imported} existing domains from nginx")
                self.save_domains()
    
    def import_existing_domains(self) -> int:
        """Import existing nginx domain configurations"""
        imported_count = 0
        try:
            if not NGINX_SITES_DIR.exists():
                return 0
            
            for config_file in NGINX_SITES_DIR.iterdir():
                if config_file.is_file() and config_file.name not in ['default', 'default.conf']:
                    domain_name = config_file.name
                    
                    # Skip if already in our list
                    if self.domain_exists(domain_name):
                        continue
                    
                    # Try to extract port from nginx config
                    port = 80
                    ssl = False
                    try:
                        with open(config_file, 'r') as f:
                            content = f.read()
                            
                            # Look for proxy_pass with port
                            port_match = re.search(r'proxy_pass\s+https?://[^:]+:(\d+)', content)
                            if port_match:
                                port = int(port_match.group(1))
                            
                            # Check for SSL configuration
                            ssl = 'ssl_certificate' in content or 'listen 443' in content
                    except Exception as e:
                        logger.warning(f"Could not parse {config_file}: {e}")
                    
                    # Create domain object
                    domain = Domain(domain_name, port, ssl)
                    self.domains.append(domain)
                    imported_count += 1
                    logger.info(f"Imported domain: {domain_name} (port {port}, SSL: {ssl})")
            
            return imported_count
        except Exception as e:
            logger.error(f"Failed to import existing domains: {e}")
            return imported_count
    
    def save_domains(self):
        """Save domains to JSON file"""
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump([d.to_dict() for d in self.domains], f, indent=2)
            logger.info("Domains saved successfully")
        except Exception as e:
            logger.error(f"Failed to save domains: {e}")
    
    def run_command(self, command: str) -> Tuple[bool, str]:
        """Execute shell command and return success status and output"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            logger.info(f"Command '{command}' executed with status: {result.returncode}")
            return success, output
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return False, str(e)
    
    def validate_domain(self, domain: str) -> bool:
        """Validate domain name format including full subdomain support"""
        if not domain or len(domain) > 253:
            return False
        
        if domain.lower() == 'localhost':
            return True
        
        parts = domain.split('.')
        if len(parts) < 1:
            return False
        
        for part in parts:
            if not part:
                return False
            if len(part) > 63:
                return False
            if part.startswith('-') or part.endswith('-'):
                return False
            if not re.match(r'^[a-zA-Z0-9-]+$', part):
                return False
        
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
            services = [
                'https://ipv4.icanhazip.com',
                'https://api.ipify.org',
                'https://checkip.amazonaws.com'
            ]
            
            for service in services:
                try:
                    with urllib.request.urlopen(service, timeout=5) as response:
                        ip = response.read().decode('utf-8').strip()
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                            logger.info(f"External IP detected: {ip}")
                            return ip
                except Exception as e:
                    logger.warning(f"Failed to get IP from {service}: {e}")
                    continue
            
            success, output = self.run_command("hostname -I | awk '{print $1}'")
            if success and output.strip():
                ip = output.strip()
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                    logger.info(f"Local IP detected: {ip}")
                    return ip
            
            logger.warning("Could not determine external IP, falling back to 127.0.0.1")
            return "127.0.0.1"
            
        except Exception as e:
            logger.error(f"Error getting external IP: {e}")
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
            if not self.validate_domain(name):
                return False, "Invalid domain name format"
            
            if not self.validate_port(port):
                return False, "Invalid port number (must be 1-65535)"
            
            if self.domain_exists(name):
                return False, "Domain already exists"
            
            if not self.check_port_available(port):
                logger.warning(f"Port {port} appears to be not in use for domain {name}")
            
            domain = Domain(name, port, ssl, custom_config)
            
            temp_http_only = ssl
            success, message = self.generate_nginx_config(domain, temp_http_only)
            if not success:
                return False, f"Failed to generate NGINX config: {message}"
            
            success, message = self.enable_site(name)
            if not success:
                return False, f"Failed to enable site: {message}"
            
            success, message = self.test_and_reload_nginx()
            if not success:
                return False, f"NGINX configuration test failed: {message}"
            
            if ssl:
                success, message = self.generate_ssl_certificate(name)
                if not success:
                    return False, f"Failed to generate SSL certificate: {message}"
                
                success, message = self.generate_nginx_config(domain, temp_http_only=False)
                if not success:
                    return False, f"Failed to generate HTTPS NGINX config: {message}"
                
                success, message = self.test_and_reload_nginx()
                if not success:
                    return False, f"NGINX HTTPS configuration test failed: {message}"
            
            self.domains.append(domain)
            self.save_domains()
            
            logger.info(f"Domain {name} added successfully")
            return True, f"Domain {name} added successfully"
            
        except Exception as e:
            logger.error(f"Failed to add domain {name}: {e}")
            return False, str(e)
    
    def edit_domain(self, old_name: str, new_name: str = None, new_port: int = None, new_ssl: bool = None, new_custom_config: str = None) -> Tuple[bool, str]:
        """Edit an existing domain"""
        try:
            domain = self.get_domain(old_name)
            if not domain:
                return False, "Domain not found"
            
            self.backup_domain_config(old_name)
            
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
            
            if new_name and new_name != old_name:
                self.disable_site(old_name)
                self.remove_nginx_config(old_name)
            
            temp_http_only = domain.ssl
            success, message = self.generate_nginx_config(domain, temp_http_only)
            if not success:
                return False, f"Failed to generate NGINX config: {message}"
            
            success, message = self.enable_site(domain.name)
            if not success:
                return False, f"Failed to enable site: {message}"
            
            success, message = self.test_and_reload_nginx()
            if not success:
                return False, f"NGINX configuration test failed: {message}"
            
            if domain.ssl:
                success, message = self.generate_ssl_certificate(domain.name)
                if not success:
                    return False, f"Failed to generate SSL certificate: {message}"
                
                success, message = self.generate_nginx_config(domain, temp_http_only=False)
                if not success:
                    return False, f"Failed to generate HTTPS NGINX config: {message}"
                
                success, message = self.test_and_reload_nginx()
                if not success:
                    return False, f"NGINX HTTPS configuration test failed: {message}"
            
            self.save_domains()
            logger.info(f"Domain {old_name} edited successfully")
            return True, f"Domain edited successfully"
            
        except Exception as e:
            logger.error(f"Failed to edit domain {old_name}: {e}")
            return False, str(e)
    
    def delete_domain(self, name: str) -> Tuple[bool, str]:
        """Delete a domain"""
        try:
            domain = self.get_domain(name)
            if not domain:
                return False, "Domain not found"
            
            self.backup_domain_config(name)
            
            success, message = self.disable_site(name)
            if not success:
                logger.warning(f"Failed to disable site {name}: {message}")
            
            success, message = self.remove_nginx_config(name)
            if not success:
                logger.warning(f"Failed to remove NGINX config for {name}: {message}")
            
            success, message = self.test_and_reload_nginx()
            if not success:
                logger.error(f"NGINX configuration test failed after removing {name}: {message}")
                return False, f"NGINX configuration test failed: {message}"
            
            self.domains = [d for d in self.domains if d.name != name]
            self.save_domains()
            
            logger.info(f"Domain {name} deleted successfully")
            return True, f"Domain {name} deleted successfully"
            
        except Exception as e:
            logger.error(f"Failed to delete domain {name}: {e}")
            return False, str(e)
    
    def generate_nginx_config(self, domain: Domain, temp_http_only: bool = False) -> Tuple[bool, str]:
        """Generate NGINX configuration for a domain"""
        try:
            if domain.custom_config:
                template_path = MANAGER_DIR / "custom-configs" / domain.custom_config
                if not template_path.exists():
                    template_path = TEMPLATES_DIR / "default.conf"
            else:
                template_path = TEMPLATES_DIR / "default.conf"
            
            if not template_path.exists():
                 # Fallback if template doesn't exist
                 return False, f"Template not found: {template_path}"

            with open(template_path, 'r') as f:
                template_content = f.read()
            
            ssl_cert_path = f"/etc/letsencrypt/live/{domain.name}/fullchain.pem"
            ssl_key_path = f"/etc/letsencrypt/live/{domain.name}/privkey.pem"
            
            backend_ip = self.get_external_ip() or "127.0.0.1"
            
            config_content = template_content.replace('$DOMAIN', domain.name)
            config_content = config_content.replace('$PORT', str(domain.port))
            config_content = config_content.replace('$SSL_CERT_PATH', ssl_cert_path)
            config_content = config_content.replace('$SSL_KEY_PATH', ssl_key_path)
            config_content = config_content.replace('$BACKEND_IP', backend_ip)
            
            if not domain.ssl or temp_http_only:
                lines = config_content.split('\n')
                http_config = []
                in_http_block = False
                brace_count = 0
                last_server_start = -1
                
                for i, line in enumerate(lines):
                    if 'server {' in line:
                        last_server_start = i
                
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
            
            config_file = NGINX_SITES_DIR / domain.name
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            config_type = "HTTP-only" if (not domain.ssl or temp_http_only) else "HTTPS"
            logger.info(f"NGINX {config_type} configuration generated for {domain.name}")
            return True, f"{config_type} configuration generated successfully"
            
        except Exception as e:
            logger.error(f"Failed to generate NGINX config for {domain.name}: {e}")
            return False, str(e)
    
    def generate_ssl_certificate(self, domain_name: str, wildcard: bool = False) -> Tuple[bool, str]:
        """Generate SSL certificate using certbot"""
        try:
            # For wildcard, check the base domain certificate
            check_domain = domain_name.replace('*.', '') if wildcard else domain_name
            cert_path = Path(f"/etc/letsencrypt/live/{check_domain}/fullchain.pem")
            
            if cert_path.exists():
                logger.info(f"SSL certificate already exists for {check_domain}")
                return True, "Certificate already exists"
            
            email = self.config.get('certbot_email', f'admin@{check_domain}')
            
            if wildcard:
                # Wildcard certificates require DNS-01 challenge
                # Note: This requires DNS plugin configuration
                base_domain = domain_name.replace('*.', '')
                logger.info(f"Generating wildcard certificate for *.{base_domain}")
                
                # Try to detect DNS provider from config
                dns_plugin = self.config.get('dns_plugin', 'dns-cloudflare')
                
                command = f"certbot certonly --{dns_plugin} -d {base_domain} -d *.{base_domain} --non-interactive --agree-tos --email {email}"
                
                success, output = self.run_command(command)
                
                if not success and "dns-cloudflare" in command:
                    # Fallback: suggest manual DNS challenge
                    return False, (
                        "Wildcard certificates require DNS verification. "
                        "Please configure DNS plugin (e.g., dns-cloudflare) in settings, "
                        "or use manual DNS challenge: "
                        f"certbot certonly --manual --preferred-challenges dns -d {base_domain} -d *.{base_domain}"
                    )
            else:
                # Standard HTTP-01 challenge
                command = f"certbot --nginx -d {domain_name} --non-interactive --agree-tos --email {email}"
                success, output = self.run_command(command)
            
            if success:
                logger.info(f"SSL certificate generated for {domain_name}")
                return True, "SSL certificate generated successfully"
            else:
                logger.error(f"Failed to generate SSL certificate for {domain_name}: {output}")
                return False, output
                
        except Exception as e:
            logger.error(f"SSL certificate generation failed for {domain_name}: {e}")
            return False, str(e)
    
    def enable_site(self, domain_name: str) -> Tuple[bool, str]:
        """Enable NGINX site"""
        try:
            source = NGINX_SITES_DIR / domain_name
            target = NGINX_ENABLED_DIR / domain_name
            
            if not source.exists():
                logger.error(f"Source configuration file does not exist: {source}")
                return False, f"Configuration file {source} not found"
            
            NGINX_ENABLED_DIR.mkdir(parents=True, exist_ok=True)
            
            if target.exists() or target.is_symlink():
                target.unlink()
            
            target.symlink_to(source)
            
            if target.exists() and target.is_symlink():
                logger.info(f"Site {domain_name} enabled successfully")
                return True, "Site enabled successfully"
            else:
                logger.error(f"Failed to verify symbolic link for {domain_name}")
                return False, "Failed to create symbolic link"
            
        except Exception as e:
            logger.error(f"Failed to enable site {domain_name}: {e}")
            return False, str(e)
    
    def disable_site(self, domain_name: str) -> Tuple[bool, str]:
        """Disable NGINX site"""
        try:
            target = NGINX_ENABLED_DIR / domain_name
            if target.exists():
                target.unlink()
                logger.info(f"Site {domain_name} disabled")
            return True, "Site disabled successfully"
            
        except Exception as e:
            logger.error(f"Failed to disable site {domain_name}: {e}")
            return False, str(e)
    
    def remove_nginx_config(self, domain_name: str) -> Tuple[bool, str]:
        """Remove NGINX configuration file"""
        try:
            config_file = NGINX_SITES_DIR / domain_name
            if config_file.exists():
                config_file.unlink()
                logger.info(f"NGINX config removed for {domain_name}")
            return True, "Configuration removed successfully"
            
        except Exception as e:
            logger.error(f"Failed to remove NGINX config for {domain_name}: {e}")
            return False, str(e)
    
    def test_and_reload_nginx(self) -> Tuple[bool, str]:
        """Test NGINX configuration and reload if valid"""
        try:
            success, output = self.run_command("nginx -t")
            if not success:
                return False, f"Configuration test failed: {output}"
            
            success, output = self.run_command("systemctl reload nginx")
            if success:
                logger.info("NGINX reloaded successfully")
                return True, "NGINX reloaded successfully"
            else:
                return False, f"Failed to reload NGINX: {output}"
                
        except Exception as e:
            logger.error(f"NGINX test/reload failed: {e}")
            return False, str(e)
    
    def backup_domain_config(self, domain_name: str):
        """Backup domain configuration"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            config_file = NGINX_SITES_DIR / domain_name
            
            if config_file.exists():
                backup_file = BACKUP_DIR / f"{domain_name}_{timestamp}.conf"
                shutil.copy2(config_file, backup_file)
                logger.info(f"Configuration backed up for {domain_name}")
                
        except Exception as e:
            logger.error(f"Failed to backup configuration for {domain_name}: {e}")
    
    def create_domain_backup(self, domain_name: str) -> Tuple[bool, str]:
        """Create backup for a specific domain before making changes"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"domain_{domain_name}_{timestamp}"
            backup_path = BACKUP_DIR / f"{backup_name}.tar.gz"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_backup_dir = Path(temp_dir) / backup_name
                temp_backup_dir.mkdir()
                
                domain = self.get_domain(domain_name)
                if domain:
                    domain_config_file = temp_backup_dir / "domain.json"
                    with open(domain_config_file, 'w') as f:
                        json.dump(domain.to_dict(), f, indent=2)
                
                nginx_config = NGINX_SITES_DIR / domain_name
                if nginx_config.exists():
                    shutil.copy2(nginx_config, temp_backup_dir / f"{domain_name}.conf")
                
                ssl_dir = Path(f"/etc/letsencrypt/live/{domain_name}")
                if ssl_dir.exists():
                    ssl_backup_dir = temp_backup_dir / "ssl"
                    ssl_backup_dir.mkdir()
                    try:
                        shutil.copytree(ssl_dir, ssl_backup_dir / domain_name, dirs_exist_ok=True)
                    except PermissionError:
                        logger.warning(f"Could not backup SSL certificates for {domain_name} (permission denied)")
                
                shutil.make_archive(str(backup_path.with_suffix('')), 'gztar', temp_dir, backup_name)
            
            logger.info(f"Domain backup created: {backup_path}")
            return True, f"Backup created successfully: {backup_path.name}"
            
        except Exception as e:
            logger.error(f"Failed to create domain backup for {domain_name}: {e}")
            return False, str(e)
    
    def create_full_backup(self) -> Tuple[bool, str]:
        """Create full backup of all configurations"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = BACKUP_DIR / f"full_backup_{timestamp}"
            backup_dir.mkdir(exist_ok=True)
            
            if DATA_FILE.exists():
                shutil.copy2(DATA_FILE, backup_dir / "domains.json")
            
            nginx_backup_dir = backup_dir / "nginx_configs"
            nginx_backup_dir.mkdir(exist_ok=True)
            
            for domain in self.domains:
                config_file = NGINX_SITES_DIR / domain.name
                if config_file.exists():
                    shutil.copy2(config_file, nginx_backup_dir / f"{domain.name}.conf")
            
            custom_configs_dir = MANAGER_DIR / "custom-configs"
            if custom_configs_dir.exists():
                shutil.copytree(custom_configs_dir, backup_dir / "custom-configs", dirs_exist_ok=True)
            
            logger.info(f"Full backup created: {backup_dir}")
            return True, f"Full backup created successfully at {backup_dir}"
            
        except Exception as e:
            logger.error(f"Failed to create full backup: {e}")
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
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def get_nginx_status(self) -> Tuple[bool, str]:
        """Get NGINX service status"""
        success, output = self.run_command("systemctl is-active nginx")
        is_active = success and output.strip() == "active"
        return is_active, output.strip()
    
    def restart_nginx(self) -> Tuple[bool, str]:
        """Restart NGINX service"""
        return self.run_command("systemctl restart nginx")
    
    def uninstall_manager(self, delete_ssl: bool = False, delete_domains: bool = False) -> Tuple[bool, str]:
        """Uninstall VPS Manager completely"""
        try:
            logger.info("Starting VPS Manager uninstall process")
            
            service_file = Path("/etc/systemd/system/vps-manager.service")
            if service_file.exists():
                logger.info("Stopping and disabling systemd service")
                self.run_command("systemctl stop vps-manager")
                self.run_command("systemctl disable vps-manager")
                service_file.unlink()
                self.run_command("systemctl daemon-reload")
            
            symlink_path = Path("/usr/local/bin/vps-manager")
            if symlink_path.exists():
                logger.info("Removing symbolic link")
                symlink_path.unlink()
            
            if delete_ssl:
                logger.info("Removing SSL certificates")
                for domain in self.domains:
                    if domain.ssl:
                        cert_path = f"/etc/letsencrypt/live/{domain.name}"
                        if Path(cert_path).exists():
                            success, output = self.run_command(f"certbot delete --cert-name {domain.name} --non-interactive")
                            if success:
                                logger.info(f"Removed SSL certificate for {domain.name}")
                            else:
                                logger.warning(f"Failed to remove SSL certificate for {domain.name}: {output}")
            
            if delete_domains:
                logger.info("Removing domain configurations")
                for domain in self.domains:
                    site_file = NGINX_SITES_DIR / domain.name
                    enabled_file = NGINX_ENABLED_DIR / domain.name
                    
                    if enabled_file.exists():
                        enabled_file.unlink()
                        logger.info(f"Removed enabled site for {domain.name}")
                    
                    if site_file.exists():
                        site_file.unlink()
                        logger.info(f"Removed site configuration for {domain.name}")
                
                success, output = self.run_command("nginx -t")
                if success:
                    self.run_command("systemctl reload nginx")
                    logger.info("NGINX reloaded successfully")
                else:
                    logger.warning(f"NGINX configuration test failed: {output}")
            
            if MANAGER_DIR.exists():
                logger.info(f"Removing manager directory: {MANAGER_DIR}")
                shutil.rmtree(MANAGER_DIR)
            
            logger.info("VPS Manager uninstall completed successfully")
            return True, "VPS Manager has been uninstalled successfully."
            
        except Exception as e:
            error_msg = f"Failed to uninstall VPS Manager: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def check_for_updates(self) -> Tuple[bool, str, str]:
        """Check if updates are available"""
        if VERSION_URL is None:
            logger.info("Update functionality is disabled - no update repository configured")
            return False, VERSION, VERSION
            
        try:
            with urllib.request.urlopen(VERSION_URL, timeout=10) as response:
                latest_version = response.read().decode('utf-8').strip()
                
            current_version = VERSION
            has_update = self._compare_versions(current_version, latest_version) < 0
            
            return has_update, current_version, latest_version
            
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return False, VERSION, VERSION
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings"""
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
        
        if self._compare_versions(current_config_version, '1.1.0') < 0:
            if 'auto_update' not in self.config:
                missing_options.append('auto_update')
        
        return missing_options
    
    def needs_selective_onboarding(self) -> bool:
        """Check if selective onboarding is needed for new config options"""
        return len(self.get_missing_config_options()) > 0
