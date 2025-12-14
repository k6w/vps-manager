"""
Firewall Management Module - UFW Integration
Provides management for UFW (Uncomplicated Firewall) rules
"""

import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from .utils import get_logger

logger = get_logger(__name__)


class FirewallRule:
    """Represents a UFW firewall rule"""
    
    def __init__(self, number: int, action: str, from_addr: str, to_addr: str, 
                 port: str = None, protocol: str = None, comment: str = None):
        self.number = number
        self.action = action  # ALLOW, DENY, REJECT, LIMIT
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.port = port
        self.protocol = protocol
        self.comment = comment
    
    def to_dict(self) -> Dict:
        return {
            "number": self.number,
            "action": self.action,
            "from": self.from_addr,
            "to": self.to_addr,
            "port": self.port,
            "protocol": self.protocol,
            "comment": self.comment
        }
    
    def __str__(self) -> str:
        port_str = f":{self.port}/{self.protocol}" if self.port else ""
        return f"[{self.number}] {self.action} from {self.from_addr} to {self.to_addr}{port_str}"


class FirewallManager:
    """Manages UFW firewall rules"""
    
    def __init__(self, manager):
        self.manager = manager
    
    def is_installed(self) -> Tuple[bool, str]:
        """Check if UFW is installed"""
        success, output = self.manager.run_command("which ufw")
        if success and output.strip():
            return True, "UFW is installed"
        return False, "UFW is not installed"
    
    def get_status(self) -> Tuple[bool, str, bool]:
        """Get UFW status - returns (success, output, is_active)"""
        success, output = self.manager.run_command("ufw status")
        if not success:
            return False, output, False
        
        is_active = "Status: active" in output
        return True, output, is_active
    
    def enable(self) -> Tuple[bool, str]:
        """Enable UFW firewall"""
        success, output = self.manager.run_command("ufw --force enable")
        if success:
            logger.info("UFW enabled successfully")
            return True, "Firewall enabled successfully"
        logger.error(f"Failed to enable UFW: {output}")
        return False, f"Failed to enable firewall: {output}"
    
    def disable(self) -> Tuple[bool, str]:
        """Disable UFW firewall"""
        success, output = self.manager.run_command("ufw --force disable")
        if success:
            logger.info("UFW disabled successfully")
            return True, "Firewall disabled successfully"
        logger.error(f"Failed to disable UFW: {output}")
        return False, f"Failed to disable firewall: {output}"
    
    def reload(self) -> Tuple[bool, str]:
        """Reload UFW rules"""
        success, output = self.manager.run_command("ufw reload")
        if success:
            logger.info("UFW reloaded successfully")
            return True, "Firewall reloaded successfully"
        return False, f"Failed to reload firewall: {output}"
    
    def list_rules(self) -> Tuple[bool, List[FirewallRule]]:
        """List all firewall rules"""
        success, output = self.manager.run_command("ufw status numbered")
        if not success:
            logger.error(f"Failed to list rules: {output}")
            return False, []
        
        rules = []
        lines = output.split('\n')
        
        for line in lines:
            # Parse numbered rules like: [ 1] 22/tcp ALLOW IN Anywhere
            match = re.match(r'\[\s*(\d+)\]\s+(.+?)\s+(ALLOW|DENY|REJECT|LIMIT)\s+(IN|OUT)\s+(.+?)(?:\s+\((.+?)\))?$', line)
            if match:
                number = int(match.group(1))
                to_part = match.group(2).strip()
                action = match.group(3)
                direction = match.group(4)
                from_part = match.group(5).strip()
                comment = match.group(6) if match.group(6) else None
                
                # Parse port and protocol from to_part
                port_match = re.match(r'(\d+)/(tcp|udp)', to_part)
                port = port_match.group(1) if port_match else None
                protocol = port_match.group(2) if port_match else None
                
                rule = FirewallRule(
                    number=number,
                    action=action,
                    from_addr=from_part,
                    to_addr=to_part,
                    port=port,
                    protocol=protocol,
                    comment=comment
                )
                rules.append(rule)
        
        return True, rules
    
    def allow_port(self, port: int, protocol: str = "tcp", comment: str = None) -> Tuple[bool, str]:
        """Allow a specific port"""
        comment_str = f" comment '{comment}'" if comment else ""
        command = f"ufw allow {port}/{protocol}{comment_str}"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info(f"Allowed port {port}/{protocol}")
            return True, f"Port {port}/{protocol} allowed successfully"
        
        logger.error(f"Failed to allow port {port}/{protocol}: {output}")
        return False, f"Failed to allow port: {output}"
    
    def deny_port(self, port: int, protocol: str = "tcp", comment: str = None) -> Tuple[bool, str]:
        """Deny a specific port"""
        comment_str = f" comment '{comment}'" if comment else ""
        command = f"ufw deny {port}/{protocol}{comment_str}"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info(f"Denied port {port}/{protocol}")
            return True, f"Port {port}/{protocol} denied successfully"
        
        logger.error(f"Failed to deny port {port}/{protocol}: {output}")
        return False, f"Failed to deny port: {output}"
    
    def limit_port(self, port: int, protocol: str = "tcp", comment: str = None) -> Tuple[bool, str]:
        """Rate limit a specific port (for SSH protection)"""
        comment_str = f" comment '{comment}'" if comment else ""
        command = f"ufw limit {port}/{protocol}{comment_str}"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info(f"Limited port {port}/{protocol}")
            return True, f"Port {port}/{protocol} rate limited successfully"
        
        logger.error(f"Failed to limit port {port}/{protocol}: {output}")
        return False, f"Failed to limit port: {output}"
    
    def delete_rule(self, rule_number: int) -> Tuple[bool, str]:
        """Delete a rule by number"""
        command = f"ufw --force delete {rule_number}"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info(f"Deleted rule {rule_number}")
            return True, f"Rule {rule_number} deleted successfully"
        
        logger.error(f"Failed to delete rule {rule_number}: {output}")
        return False, f"Failed to delete rule: {output}"
    
    def allow_from_ip(self, ip: str, port: int = None, protocol: str = "tcp") -> Tuple[bool, str]:
        """Allow traffic from specific IP"""
        port_str = f" to any port {port} proto {protocol}" if port else ""
        command = f"ufw allow from {ip}{port_str}"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info(f"Allowed access from IP {ip}")
            return True, f"Access from {ip} allowed successfully"
        
        return False, f"Failed to allow IP: {output}"
    
    def deny_from_ip(self, ip: str) -> Tuple[bool, str]:
        """Deny traffic from specific IP"""
        command = f"ufw deny from {ip}"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info(f"Denied access from IP {ip}")
            return True, f"Access from {ip} denied successfully"
        
        return False, f"Failed to deny IP: {output}"
    
    def reset(self) -> Tuple[bool, str]:
        """Reset all firewall rules"""
        command = "ufw --force reset"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info("UFW rules reset")
            return True, "Firewall rules reset successfully"
        
        return False, f"Failed to reset firewall: {output}"
    
    def get_default_policies(self) -> Dict[str, str]:
        """Get default policies for incoming/outgoing traffic"""
        success, output = self.manager.run_command("ufw status verbose")
        
        policies = {
            "incoming": "unknown",
            "outgoing": "unknown",
            "routed": "unknown"
        }
        
        if success:
            for line in output.split('\n'):
                if "Default:" in line:
                    if "deny (incoming)" in line.lower():
                        policies["incoming"] = "deny"
                    elif "allow (incoming)" in line.lower():
                        policies["incoming"] = "allow"
                    
                    if "deny (outgoing)" in line.lower():
                        policies["outgoing"] = "deny"
                    elif "allow (outgoing)" in line.lower():
                        policies["outgoing"] = "allow"
                    
                    if "deny (routed)" in line.lower():
                        policies["routed"] = "deny"
                    elif "allow (routed)" in line.lower():
                        policies["routed"] = "allow"
        
        return policies
    
    def set_default_incoming(self, policy: str) -> Tuple[bool, str]:
        """Set default incoming policy (allow/deny)"""
        command = f"ufw default {policy} incoming"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info(f"Set default incoming policy to {policy}")
            return True, f"Default incoming policy set to {policy}"
        
        return False, f"Failed to set policy: {output}"
    
    def set_default_outgoing(self, policy: str) -> Tuple[bool, str]:
        """Set default outgoing policy (allow/deny)"""
        command = f"ufw default {policy} outgoing"
        success, output = self.manager.run_command(command)
        
        if success:
            logger.info(f"Set default outgoing policy to {policy}")
            return True, f"Default outgoing policy set to {policy}"
        
        return False, f"Failed to set policy: {output}"
    
    def quick_setup_web_server(self) -> Tuple[bool, str]:
        """Quick setup for web server (allow 22, 80, 443)"""
        results = []
        
        # Allow SSH
        success, msg = self.limit_port(22, "tcp", "SSH")
        results.append(("SSH (22)", success))
        
        # Allow HTTP
        success, msg = self.allow_port(80, "tcp", "HTTP")
        results.append(("HTTP (80)", success))
        
        # Allow HTTPS
        success, msg = self.allow_port(443, "tcp", "HTTPS")
        results.append(("HTTPS (443)", success))
        
        all_success = all(r[1] for r in results)
        
        if all_success:
            self.enable()
            return True, "Web server firewall configured successfully (ports 22, 80, 443)"
        else:
            failed = [r[0] for r in results if not r[1]]
            return False, f"Failed to configure ports: {', '.join(failed)}"
