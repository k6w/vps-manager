# VPS Manager - NGINX Domain & SSL Certificate Manager

A comprehensive terminal-based manager for Ubuntu 24.04 VPS that simplifies NGINX domain management and SSL certificate automation with Certbot integration.

## Features

### 🚀 **Core Functionality**
- **Interactive Terminal UI** - Beautiful curses-based interface
- **Domain Management** - Add, edit, delete, and list domains
- **SSL Automation** - Automatic Let's Encrypt certificate generation
- **Template System** - Flexible NGINX configuration templates
- **Backup & Restore** - Comprehensive configuration backups
- **Service Management** - NGINX reload, restart, and status monitoring
- **Log Viewer** - Real-time log monitoring and analysis

### 🛡️ **Security & Reliability**
- Modern SSL/TLS configurations
- Automatic certificate renewal
- Configuration validation
- Error handling and logging
- Safe backup and restore operations

### 🎨 **User Experience**
- Intuitive navigation with arrow keys
- Confirmation dialogs for destructive operations
- Progress indicators for long-running tasks
- Comprehensive error messages
- Real-time status updates

## Quick Start

### Prerequisites

- Ubuntu 24.04 VPS with root access
- Domain names pointing to your server's IP
- Ports 80 and 443 open in firewall

### Installation

1. **Download and run the installer:**
   ```bash
   curl -sSL https://raw.githubusercontent.com/k6w/vps-manager/main/install.sh | bash
   ```

2. **Or manual installation:**
   ```bash
   # Clone or download the files
   mkdir -p ~/manager
   cd ~/manager
   
   # Copy the files (vps-manager.py, default.conf, requirements.txt, install.sh)
   # Then run:
   chmod +x install.sh
   sudo ./install.sh
   ```

3. **Start the manager:**
   ```bash
   vps-manager
   ```

## Usage Guide

### Main Menu Navigation

```
╔══════════════════════════════════════╗
║           VPS Manager v1.0           ║
║        NGINX & SSL Manager           ║
╠══════════════════════════════════════╣
║  1. List Domains                     ║
║  2. Add Domain                       ║
║  3. Edit Domain                      ║
║  4. Delete Domain                    ║
║  5. NGINX Status                     ║
║  6. Backup Configurations            ║
║  7. Restore Backup                   ║
║  8. View Logs                        ║
║  9. Exit                             ║
╚══════════════════════════════════════╝
```

### Adding a New Domain

1. Select **"Add Domain"** from the main menu
2. Enter your domain name (e.g., `example.com`)
3. Specify the backend port (e.g., `3000` for Node.js apps)
4. Choose SSL configuration (recommended: Yes)
5. Select template (Default or Custom)
6. Confirm and wait for automatic setup

**The manager will automatically:**
- Generate NGINX configuration
- Create SSL certificate via Certbot
- Enable the site
- Test and reload NGINX

### Managing Existing Domains

- **List Domains**: View all configured domains with status
- **Edit Domain**: Modify domain settings (name, port, SSL)
- **Delete Domain**: Remove domain and clean up configurations

### NGINX Management

- **Status Monitoring**: Real-time NGINX service status
- **Configuration Testing**: Validate NGINX configs before applying
- **Service Control**: Reload, restart, or test NGINX
- **Error Detection**: Automatic configuration validation

### Backup & Restore

- **Automatic Backups**: Created before major changes
- **Manual Backups**: On-demand full system backup
- **Easy Restore**: Select and restore from available backups
- **Comprehensive Coverage**: Includes configs, certificates, and logs

## Configuration Templates

### Default Template Features

- **HTTP to HTTPS redirection**
- **Modern SSL/TLS configuration**
- **Security headers (HSTS, CSP, etc.)**
- **Gzip compression**
- **Static file optimization**
- **Proxy pass configuration**
- **Access and error logging**

### Custom Templates

Create custom NGINX configurations in `~/manager/custom-configs/`:

```nginx
# Example: API-specific template
server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    ssl_certificate $SSL_CERT_PATH;
    ssl_certificate_key $SSL_KEY_PATH;
    
    # API-specific settings
    client_max_body_size 100M;
    proxy_read_timeout 300s;
    
    location /api/ {
        proxy_pass http://127.0.0.1:$PORT/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Available Template Variables

- `$DOMAIN` - Domain name
- `$PORT` - Backend port
- `$SSL_CERT_PATH` - SSL certificate path
- `$SSL_KEY_PATH` - SSL private key path

## Directory Structure

```
~/manager/
├── vps-manager.py          # Main application
├── domains.json            # Domain configurations
├── requirements.txt        # Python dependencies
├── install.sh             # Installation script
├── templates/
│   └── default.conf        # Default NGINX template
├── custom-configs/
│   └── *.conf             # Custom templates
├── backups/
│   └── *.tar.gz           # Configuration backups
└── logs/
    └── manager.log         # Application logs
```

## Advanced Usage

### Command Line Options

```bash
# Start with specific configuration
vps-manager --config /path/to/config.json

# Enable debug mode
vps-manager --debug

# Run in batch mode (no UI)
vps-manager --batch --add-domain example.com --port 3000 --ssl
```

### Environment Variables

```bash
# Custom manager directory
export VPS_MANAGER_DIR="/opt/vps-manager"

# Custom NGINX directories
export NGINX_SITES_DIR="/etc/nginx/sites-available"
export NGINX_ENABLED_DIR="/etc/nginx/sites-enabled"
```

## Troubleshooting

### Common Issues

**1. Domain not accessible**
```bash
# Check DNS
nslookup your-domain.com

# Check NGINX status
sudo systemctl status nginx

# Test configuration
sudo nginx -t
```

**2. SSL certificate errors**
```bash
# Check Certbot logs
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Manual certificate generation
sudo certbot certonly --nginx -d your-domain.com
```

**3. Backend connection issues**
```bash
# Check if backend is running
sudo netstat -tlnp | grep :3000

# Test backend directly
curl http://localhost:3000
```

### Log Files

- **Manager Logs**: `~/manager/logs/manager.log`
- **NGINX Error**: `/var/log/nginx/error.log`
- **NGINX Access**: `/var/log/nginx/access.log`
- **Certbot**: `/var/log/letsencrypt/letsencrypt.log`
- **System**: `journalctl -u nginx`

### Recovery Commands

```bash
# Restore NGINX default configuration
sudo cp /etc/nginx/nginx.conf.backup /etc/nginx/nginx.conf

# Remove all manager configurations
sudo rm /etc/nginx/sites-enabled/managed-*
sudo systemctl reload nginx

# Reset manager data
rm ~/manager/domains.json
```

## Security Best Practices

### Server Security
- Keep Ubuntu updated: `sudo apt update && sudo apt upgrade`
- Configure UFW firewall: `sudo ufw enable`
- Use strong passwords and SSH keys
- Regular security audits

### SSL/TLS Security
- Automatic certificate renewal enabled
- Modern cipher suites only
- HSTS headers configured
- Perfect Forward Secrecy

### Application Security
- Run with minimal privileges
- Validate all inputs
- Secure backup storage
- Regular log monitoring

## Performance Optimization

### NGINX Tuning
```nginx
# Add to custom templates for high-traffic sites
worker_processes auto;
worker_connections 1024;

# Enable caching
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### System Optimization
```bash
# Increase file descriptor limits
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Optimize kernel parameters
echo "net.core.somaxconn = 65536" >> /etc/sysctl.conf
sudo sysctl -p
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup

```bash
# Clone repository
git clone https://github.com/k6w/vps-manager.git
cd vps-manager

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Run linting
flake8 vps-manager.py
```

## License

MIT License - see LICENSE file for details.

## Support

- **Documentation**: [DOCS.md](DOCS.md)
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: support@vps-manager.com

## Changelog

### v1.0.0 (2024-01-01)
- Initial release
- Core domain management functionality
- SSL certificate automation
- Backup and restore system
- Interactive terminal UI
- Comprehensive logging

---

**Made with ❤️ for VPS administrators who value simplicity and reliability.**