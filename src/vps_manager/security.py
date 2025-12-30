"""
Security Hardening Module
Provides security scanning, vulnerability checking, and hardening recommendations
"""

import re
import json
import subprocess
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .utils import get_logger

logger = get_logger(__name__)


class SecurityIssue:
    """Represents a security issue found during scanning"""
    
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_HIGH = "HIGH"
    SEVERITY_MEDIUM = "MEDIUM"
    SEVERITY_LOW = "LOW"
    SEVERITY_INFO = "INFO"
    
    def __init__(self, title: str, description: str, severity: str, 
                 recommendation: str, category: str = "general"):
        self.title = title
        self.description = description
        self.severity = severity
        self.recommendation = recommendation
        self.category = category
        self.found_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "category": self.category,
            "found_at": self.found_at
        }


class SecurityScanner:
    """Security scanner for VPS configuration"""
    
    def __init__(self, manager):
        self.manager = manager
        self.issues: List[SecurityIssue] = []
    
    def scan_all(self) -> List[SecurityIssue]:
        """Run all security scans"""
        self.issues = []
        
        # Run individual scans
        self.scan_ssl_certificates()
        self.scan_nginx_security_headers()
        self.scan_ssh_configuration()
        self.scan_system_updates()
        self.scan_open_ports()
        self.scan_password_authentication()
        self.scan_firewall_status()
        self.scan_nginx_version()
        
        logger.info(f"Security scan completed. Found {len(self.issues)} issues.")
        return self.issues
    
    def scan_ssl_certificates(self):
        """Check SSL certificate expiration"""
        for domain in self.manager.domains:
            if domain.ssl:
                cert_path = Path(f"/etc/letsencrypt/live/{domain.name}/cert.pem")
                if cert_path.exists():
                    # Check certificate expiration
                    success, output = self.manager.run_command(
                        f"openssl x509 -enddate -noout -in {cert_path}"
                    )
                    
                    if success and "notAfter=" in output:
                        # Parse expiration date
                        date_str = output.split("notAfter=")[1].strip()
                        try:
                            exp_date = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                            days_until_exp = (exp_date - datetime.now()).days
                            
                            if days_until_exp < 0:
                                self.issues.append(SecurityIssue(
                                    title=f"Expired SSL Certificate: {domain.name}",
                                    description=f"SSL certificate has expired {abs(days_until_exp)} days ago",
                                    severity=SecurityIssue.SEVERITY_CRITICAL,
                                    recommendation="Renew the SSL certificate immediately using certbot",
                                    category="ssl"
                                ))
                            elif days_until_exp < 7:
                                self.issues.append(SecurityIssue(
                                    title=f"SSL Certificate Expiring Soon: {domain.name}",
                                    description=f"SSL certificate expires in {days_until_exp} days",
                                    severity=SecurityIssue.SEVERITY_HIGH,
                                    recommendation="Renew the SSL certificate soon",
                                    category="ssl"
                                ))
                            elif days_until_exp < 30:
                                self.issues.append(SecurityIssue(
                                    title=f"SSL Certificate Expiring: {domain.name}",
                                    description=f"SSL certificate expires in {days_until_exp} days",
                                    severity=SecurityIssue.SEVERITY_MEDIUM,
                                    recommendation="Plan to renew the SSL certificate",
                                    category="ssl"
                                ))
                        except Exception as e:
                            logger.error(f"Failed to parse certificate date for {domain.name}: {e}")
                else:
                    self.issues.append(SecurityIssue(
                        title=f"Missing SSL Certificate: {domain.name}",
                        description=f"Domain is configured for SSL but certificate not found",
                        severity=SecurityIssue.SEVERITY_HIGH,
                        recommendation="Generate SSL certificate using certbot",
                        category="ssl"
                    ))
    
    def scan_nginx_security_headers(self):
        """Check for security headers in NGINX configs"""
        required_headers = {
            "X-Frame-Options": "Protect against clickjacking",
            "X-Content-Type-Options": "Prevent MIME-sniffing",
            "X-XSS-Protection": "Enable XSS protection",
            "Strict-Transport-Security": "Enforce HTTPS",
            "Content-Security-Policy": "Prevent XSS and data injection"
        }
        
        for domain in self.manager.domains:
            config_file = Path(f"/etc/nginx/sites-available/{domain.name}")
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config_content = f.read()
                
                missing_headers = []
                for header, purpose in required_headers.items():
                    if header not in config_content:
                        missing_headers.append(f"{header} ({purpose})")
                
                if missing_headers:
                    self.issues.append(SecurityIssue(
                        title=f"Missing Security Headers: {domain.name}",
                        description=f"Missing headers: {', '.join([h.split(' ')[0] for h in missing_headers])}",
                        severity=SecurityIssue.SEVERITY_MEDIUM,
                        recommendation=f"Add security headers to NGINX configuration",
                        category="nginx"
                    ))
    
    def scan_ssh_configuration(self):
        """Check SSH configuration for security issues"""
        ssh_config_file = Path("/etc/ssh/sshd_config")
        if not ssh_config_file.exists():
            return
        
        try:
            with open(ssh_config_file, 'r') as f:
                config = f.read()
            
            # Check for root login
            if re.search(r'^\s*PermitRootLogin\s+yes', config, re.MULTILINE | re.IGNORECASE):
                self.issues.append(SecurityIssue(
                    title="SSH Root Login Enabled",
                    description="SSH allows root login which is a security risk",
                    severity=SecurityIssue.SEVERITY_HIGH,
                    recommendation="Set 'PermitRootLogin no' in /etc/ssh/sshd_config",
                    category="ssh"
                ))
            
            # Check for password authentication
            if re.search(r'^\s*PasswordAuthentication\s+yes', config, re.MULTILINE | re.IGNORECASE):
                self.issues.append(SecurityIssue(
                    title="SSH Password Authentication Enabled",
                    description="Password authentication is less secure than key-based auth",
                    severity=SecurityIssue.SEVERITY_MEDIUM,
                    recommendation="Use SSH keys and set 'PasswordAuthentication no'",
                    category="ssh"
                ))
            
            # Check for empty passwords
            if re.search(r'^\s*PermitEmptyPasswords\s+yes', config, re.MULTILINE | re.IGNORECASE):
                self.issues.append(SecurityIssue(
                    title="SSH Empty Passwords Allowed",
                    description="Empty passwords are allowed for SSH login",
                    severity=SecurityIssue.SEVERITY_CRITICAL,
                    recommendation="Set 'PermitEmptyPasswords no' in /etc/ssh/sshd_config",
                    category="ssh"
                ))
        
        except Exception as e:
            logger.error(f"Failed to scan SSH config: {e}")
    
    def scan_system_updates(self):
        """Check for available system updates"""
        success, output = self.manager.run_command("apt list --upgradable 2>/dev/null | grep -v 'Listing'")
        
        if success and output.strip():
            lines = output.strip().split('\n')
            update_count = len([l for l in lines if l.strip()])
            
            if update_count > 0:
                # Check for security updates
                success_sec, output_sec = self.manager.run_command(
                    "apt list --upgradable 2>/dev/null | grep -i security | wc -l"
                )
                
                security_updates = 0
                if success_sec and output_sec.strip().isdigit():
                    security_updates = int(output_sec.strip())
                
                if security_updates > 0:
                    self.issues.append(SecurityIssue(
                        title="Security Updates Available",
                        description=f"{security_updates} security updates available",
                        severity=SecurityIssue.SEVERITY_HIGH,
                        recommendation="Run: sudo apt update && sudo apt upgrade",
                        category="system"
                    ))
                
                if update_count > security_updates:
                    self.issues.append(SecurityIssue(
                        title="System Updates Available",
                        description=f"{update_count - security_updates} updates available",
                        severity=SecurityIssue.SEVERITY_LOW,
                        recommendation="Run: sudo apt update && sudo apt upgrade",
                        category="system"
                    ))
    
    def scan_open_ports(self):
        """Check for unexpected open ports"""
        success, output = self.manager.run_command("ss -tuln | grep LISTEN")
        
        if success:
            lines = output.split('\n')
            open_ports = []
            
            for line in lines:
                match = re.search(r':(\d+)\s', line)
                if match:
                    port = int(match.group(1))
                    open_ports.append(port)
            
            # Expected ports for web server
            expected_ports = {22, 80, 443}
            
            # Add backend ports from domains
            for domain in self.manager.domains:
                expected_ports.add(domain.port)
            
            unexpected = set(open_ports) - expected_ports
            
            # Filter out common system ports
            common_system_ports = {53, 123, 323}  # DNS, NTP, etc.
            unexpected = unexpected - common_system_ports
            
            if unexpected:
                self.issues.append(SecurityIssue(
                    title="Unexpected Open Ports",
                    description=f"Ports {', '.join(map(str, sorted(unexpected)))} are open",
                    severity=SecurityIssue.SEVERITY_MEDIUM,
                    recommendation="Review open ports and close unused ones with firewall",
                    category="network"
                ))
    
    def scan_password_authentication(self):
        """Check for weak password policies"""
        # Check if libpam-pwquality is installed
        success, output = self.manager.run_command("dpkg -l | grep libpam-pwquality")
        
        if not success or not output.strip():
            self.issues.append(SecurityIssue(
                title="Weak Password Policy",
                description="Password quality checking is not enforced",
                severity=SecurityIssue.SEVERITY_LOW,
                recommendation="Install libpam-pwquality: sudo apt install libpam-pwquality",
                category="system"
            ))
    
    def scan_firewall_status(self):
        """Check if firewall is enabled"""
        success, output = self.manager.run_command("ufw status")
        
        if not success:
            self.issues.append(SecurityIssue(
                title="Firewall Not Installed",
                description="UFW firewall is not installed",
                severity=SecurityIssue.SEVERITY_HIGH,
                recommendation="Install UFW: sudo apt install ufw",
                category="firewall"
            ))
        elif "Status: inactive" in output:
            self.issues.append(SecurityIssue(
                title="Firewall Disabled",
                description="UFW firewall is installed but not enabled",
                severity=SecurityIssue.SEVERITY_HIGH,
                recommendation="Enable firewall from the Firewall Management menu",
                category="firewall"
            ))
    
    def scan_nginx_version(self):
        """Check NGINX version for known vulnerabilities"""
        success, output = self.manager.run_command("nginx -v 2>&1")
        
        if success:
            match = re.search(r'nginx/([\d.]+)', output)
            if match:
                version = match.group(1)
                # This is a simple check - in production you'd check against CVE database
                major_minor = '.'.join(version.split('.')[:2])
                
                try:
                    version_num = float(major_minor)
                    if version_num < 1.18:
                        self.issues.append(SecurityIssue(
                            title="Outdated NGINX Version",
                            description=f"NGINX version {version} may have known vulnerabilities",
                            severity=SecurityIssue.SEVERITY_MEDIUM,
                            recommendation="Update NGINX: sudo apt update && sudo apt upgrade nginx",
                            category="nginx"
                        ))
                except ValueError:
                    pass
    
    def get_issues_by_severity(self) -> Dict[str, List[SecurityIssue]]:
        """Group issues by severity"""
        grouped = {
            SecurityIssue.SEVERITY_CRITICAL: [],
            SecurityIssue.SEVERITY_HIGH: [],
            SecurityIssue.SEVERITY_MEDIUM: [],
            SecurityIssue.SEVERITY_LOW: [],
            SecurityIssue.SEVERITY_INFO: []
        }
        
        for issue in self.issues:
            grouped[issue.severity].append(issue)
        
        return grouped
    
    def get_security_score(self) -> int:
        """Calculate security score (0-100)"""
        if not self.issues:
            return 100
        
        # Weight by severity
        weights = {
            SecurityIssue.SEVERITY_CRITICAL: 20,
            SecurityIssue.SEVERITY_HIGH: 10,
            SecurityIssue.SEVERITY_MEDIUM: 5,
            SecurityIssue.SEVERITY_LOW: 2,
            SecurityIssue.SEVERITY_INFO: 1
        }
        
        total_penalty = sum(weights.get(issue.severity, 1) for issue in self.issues)
        score = max(0, 100 - total_penalty)
        
        return score
    
    def generate_report(self) -> str:
        """Generate a text security report"""
        lines = []
        lines.append("=" * 60)
        lines.append("SECURITY SCAN REPORT")
        lines.append("=" * 60)
        lines.append(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Security Score: {self.get_security_score()}/100")
        lines.append(f"Total Issues: {len(self.issues)}")
        lines.append("")
        
        grouped = self.get_issues_by_severity()
        
        for severity in [SecurityIssue.SEVERITY_CRITICAL, SecurityIssue.SEVERITY_HIGH, 
                        SecurityIssue.SEVERITY_MEDIUM, SecurityIssue.SEVERITY_LOW,
                        SecurityIssue.SEVERITY_INFO]:
            issues = grouped[severity]
            if issues:
                lines.append(f"\n{severity} ({len(issues)})")
                lines.append("-" * 60)
                for i, issue in enumerate(issues, 1):
                    lines.append(f"{i}. {issue.title}")
                    lines.append(f"   {issue.description}")
                    lines.append(f"   -> {issue.recommendation}")
                    lines.append("")
        
        return "\n".join(lines)


class SecurityHardening:
    """Automated security hardening"""
    
    def __init__(self, manager):
        self.manager = manager
    
    def apply_nginx_security_headers(self, domain_name: str) -> Tuple[bool, str]:
        """Add security headers to NGINX config"""
        from pathlib import Path
        
        config_file = Path(f"/etc/nginx/sites-available/{domain_name}")
        if not config_file.exists():
            return False, "Configuration file not found"
        
        try:
            with open(config_file, 'r') as f:
                content = f.read()
            
            # Security headers to add
            headers = [
                "add_header X-Frame-Options 'SAMEORIGIN' always;",
                "add_header X-Content-Type-Options 'nosniff' always;",
                "add_header X-XSS-Protection '1; mode=block' always;",
                "add_header Referrer-Policy 'strict-origin-when-cross-origin' always;",
                "add_header Strict-Transport-Security 'max-age=31536000; includeSubDomains' always;"
            ]
            
            # Find the server block and add headers
            if "listen 443" in content:
                # Add after listen directive
                for header in headers:
                    if header not in content:
                        content = re.sub(
                            r'(listen 443[^\n]*\n)',
                            r'\1    ' + header + '\n',
                            content,
                            count=1
                        )
            
            with open(config_file, 'w') as f:
                f.write(content)
            
            # Test and reload NGINX
            success, msg = self.manager.test_and_reload_nginx()
            if success:
                logger.info(f"Applied security headers to {domain_name}")
                return True, "Security headers applied successfully"
            else:
                return False, f"NGINX test failed: {msg}"
        
        except Exception as e:
            logger.error(f"Failed to apply security headers: {e}")
            return False, str(e)
    
    def harden_ssh(self) -> Tuple[bool, str]:
        """Apply SSH hardening (requires manual verification)"""
        recommendations = [
            "Edit /etc/ssh/sshd_config and set:",
            "  PermitRootLogin no",
            "  PasswordAuthentication no",
            "  PermitEmptyPasswords no",
            "  PubkeyAuthentication yes",
            "Then run: sudo systemctl restart sshd"
        ]
        
        return True, "\n".join(recommendations)
