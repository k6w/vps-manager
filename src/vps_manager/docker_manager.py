"""
Docker Integration Module
Provides Docker container discovery and automatic NGINX configuration
"""

import json
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from .utils import get_logger

logger = get_logger(__name__)


class DockerContainer:
    """Represents a Docker container"""
    
    def __init__(self, container_id: str, name: str, image: str, status: str,
                 ports: Dict[str, str] = None, labels: Dict[str, str] = None):
        self.container_id = container_id
        self.name = name
        self.image = image
        self.status = status
        self.ports = ports or {}
        self.labels = labels or {}
    
    def to_dict(self) -> Dict:
        return {
            "id": self.container_id,
            "name": self.name,
            "image": self.image,
            "status": self.status,
            "ports": self.ports,
            "labels": self.labels
        }
    
    def get_internal_port(self) -> Optional[int]:
        """Get the internal port from port mappings"""
        for internal, external in self.ports.items():
            if '/' in internal:
                port_str = internal.split('/')[0]
                try:
                    return int(port_str)
                except ValueError:
                    continue
        return None
    
    def get_external_port(self) -> Optional[int]:
        """Get the external port from port mappings"""
        for internal, external in self.ports.items():
            if external:
                # External could be "0.0.0.0:8080" or just "8080"
                port_str = external.split(':')[-1]
                try:
                    return int(port_str)
                except ValueError:
                    continue
        return None


class DockerManager:
    """Manages Docker integration"""
    
    def __init__(self, manager):
        self.manager = manager
    
    def is_installed(self) -> Tuple[bool, str]:
        """Check if Docker is installed"""
        success, output = self.manager.run_command("which docker")
        if success and output.strip():
            # Check if Docker daemon is running
            success, output = self.manager.run_command("docker info >/dev/null 2>&1")
            if success:
                return True, "Docker is installed and running"
            return False, "Docker is installed but not running"
        return False, "Docker is not installed"
    
    def get_version(self) -> Tuple[bool, str]:
        """Get Docker version"""
        success, output = self.manager.run_command("docker --version")
        if success:
            return True, output.strip()
        return False, "Could not determine Docker version"
    
    def list_containers(self, all_containers: bool = False) -> Tuple[bool, List[DockerContainer]]:
        """List Docker containers"""
        flag = "-a" if all_containers else ""
        success, output = self.manager.run_command(
            f"docker ps {flag} --format '{{{{json .}}}}'"
        )
        
        if not success:
            logger.error(f"Failed to list containers: {output}")
            return False, []
        
        containers = []
        for line in output.strip().split('\n'):
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # Parse ports
                ports = {}
                ports_str = data.get('Ports', '')
                if ports_str:
                    # Parse port mappings like "0.0.0.0:8080->80/tcp"
                    for port_map in ports_str.split(', '):
                        if '->' in port_map:
                            external, internal = port_map.split('->')
                            ports[internal.strip()] = external.strip()
                
                # Get labels
                labels = {}
                labels_str = data.get('Labels', '')
                if labels_str:
                    for label in labels_str.split(','):
                        if '=' in label:
                            key, value = label.split('=', 1)
                            labels[key.strip()] = value.strip()
                
                container = DockerContainer(
                    container_id=data.get('ID', ''),
                    name=data.get('Names', '').lstrip('/'),
                    image=data.get('Image', ''),
                    status=data.get('Status', ''),
                    ports=ports,
                    labels=labels
                )
                containers.append(container)
            
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse container JSON: {e}")
                continue
        
        return True, containers
    
    def get_container_by_name(self, name: str) -> Optional[DockerContainer]:
        """Get container by name"""
        success, containers = self.list_containers(all_containers=True)
        if success:
            for container in containers:
                if container.name == name:
                    return container
        return None
    
    def get_container_ip(self, container_name: str) -> Optional[str]:
        """Get container IP address"""
        success, output = self.manager.run_command(
            f"docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {container_name}"
        )
        
        if success and output.strip():
            return output.strip()
        return None
    
    def get_container_port(self, container_name: str) -> Optional[int]:
        """Get container exposed port"""
        container = self.get_container_by_name(container_name)
        if container:
            # Try to get internal port first
            port = container.get_internal_port()
            if port:
                return port
            
            # Try external port
            port = container.get_external_port()
            if port:
                return port
        
        return None
    
    def inspect_container(self, container_name: str) -> Tuple[bool, Dict]:
        """Get detailed container information"""
        success, output = self.manager.run_command(f"docker inspect {container_name}")
        
        if success:
            try:
                data = json.loads(output)
                if data and isinstance(data, list):
                    return True, data[0]
                return True, data
            except json.JSONDecodeError:
                return False, {}
        
        return False, {}
    
    def get_containers_with_web_ports(self) -> List[DockerContainer]:
        """Get containers that expose common web ports"""
        success, containers = self.list_containers()
        if not success:
            return []
        
        web_ports = {80, 443, 8000, 8080, 8888, 3000, 3001, 4000, 5000}
        web_containers = []
        
        for container in containers:
            internal_port = container.get_internal_port()
            external_port = container.get_external_port()
            
            if internal_port in web_ports or external_port in web_ports:
                web_containers.append(container)
        
        return web_containers
    
    def auto_configure_container(self, container_name: str, domain: str, 
                                ssl: bool = True) -> Tuple[bool, str]:
        """Automatically configure NGINX for a Docker container"""
        container = self.get_container_by_name(container_name)
        if not container:
            return False, f"Container '{container_name}' not found"
        
        if container.status.lower() != "running":
            return False, f"Container '{container_name}' is not running"
        
        # Get container IP and port
        container_ip = self.get_container_ip(container_name)
        if not container_ip:
            container_ip = "127.0.0.1"
        
        port = self.get_container_port(container_name)
        if not port:
            # Try to detect from labels
            if 'traefik.port' in container.labels:
                try:
                    port = int(container.labels['traefik.port'])
                except ValueError:
                    pass
            
            if not port:
                return False, "Could not determine container port. Please specify manually."
        
        # Check if domain already exists
        if self.manager.domain_exists(domain):
            return False, f"Domain '{domain}' already configured"
        
        # Add domain with Docker container as backend
        logger.info(f"Auto-configuring {domain} -> {container_name} ({container_ip}:{port})")
        success, message = self.manager.add_domain(domain, port, ssl)
        
        if success:
            return True, f"Configured {domain} for container {container_name} on port {port}"
        
        return False, message
    
    def scan_and_suggest_configs(self) -> List[Dict]:
        """Scan containers and suggest NGINX configurations"""
        suggestions = []
        
        web_containers = self.get_containers_with_web_ports()
        
        for container in web_containers:
            # Check if container has domain label
            domain_label = container.labels.get('vps.domain') or container.labels.get('traefik.frontend.rule')
            
            if domain_label:
                # Parse domain from Traefik rule if needed
                if domain_label.startswith('Host:'):
                    domain_label = domain_label.replace('Host:', '').strip()
            
            port = container.get_external_port() or container.get_internal_port()
            container_ip = self.get_container_ip(container.name) or "127.0.0.1"
            
            suggestion = {
                "container_name": container.name,
                "container_id": container.container_id[:12],
                "image": container.image,
                "suggested_domain": domain_label or f"{container.name}.example.com",
                "port": port,
                "ip": container_ip,
                "status": container.status,
                "already_configured": domain_label and self.manager.domain_exists(domain_label)
            }
            
            suggestions.append(suggestion)
        
        return suggestions
    
    def start_container(self, container_name: str) -> Tuple[bool, str]:
        """Start a Docker container"""
        success, output = self.manager.run_command(f"docker start {container_name}")
        
        if success:
            logger.info(f"Started container {container_name}")
            return True, f"Container {container_name} started successfully"
        
        return False, f"Failed to start container: {output}"
    
    def stop_container(self, container_name: str) -> Tuple[bool, str]:
        """Stop a Docker container"""
        success, output = self.manager.run_command(f"docker stop {container_name}")
        
        if success:
            logger.info(f"Stopped container {container_name}")
            return True, f"Container {container_name} stopped successfully"
        
        return False, f"Failed to stop container: {output}"
    
    def restart_container(self, container_name: str) -> Tuple[bool, str]:
        """Restart a Docker container"""
        success, output = self.manager.run_command(f"docker restart {container_name}")
        
        if success:
            logger.info(f"Restarted container {container_name}")
            return True, f"Container {container_name} restarted successfully"
        
        return False, f"Failed to restart container: {output}"
    
    def get_container_logs(self, container_name: str, lines: int = 50) -> Tuple[bool, str]:
        """Get container logs"""
        success, output = self.manager.run_command(f"docker logs --tail {lines} {container_name}")
        
        if success:
            return True, output
        
        return False, f"Failed to get logs: {output}"
    
    def get_compose_services(self) -> Tuple[bool, List[str]]:
        """Get Docker Compose services"""
        success, output = self.manager.run_command("docker-compose ps --services 2>/dev/null")
        
        if success and output.strip():
            services = output.strip().split('\n')
            return True, services
        
        return False, []
