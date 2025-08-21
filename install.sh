#!/bin/bash

# VPS Manager Installation Script
# This script installs and configures the VPS Manager on Ubuntu 24.04

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
    exit 1
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root (use sudo)"
fi

log "Starting VPS Manager installation..."

# Update system packages
log "Updating system packages..."
apt update && apt upgrade -y

# Install required system packages
log "Installing required system packages..."
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx curl wget git

# Check if NGINX is installed and running
log "Checking NGINX installation..."
if ! systemctl is-active --quiet nginx; then
    log "Starting NGINX service..."
    systemctl start nginx
    systemctl enable nginx
fi

# Create manager directory
MANAGER_DIR="/home/$(logname)/manager"
log "Creating manager directory at $MANAGER_DIR..."
mkdir -p "$MANAGER_DIR"
mkdir -p "$MANAGER_DIR/templates"
mkdir -p "$MANAGER_DIR/backups"
mkdir -p "$MANAGER_DIR/custom-configs"

# Copy files to manager directory (only if not already there)
log "Copying manager files..."
if [ "$(pwd)" != "$MANAGER_DIR" ]; then
    cp vps-manager.py "$MANAGER_DIR/" 2>/dev/null || log "vps-manager.py already exists in target directory"
    cp default.conf "$MANAGER_DIR/templates/" 2>/dev/null || log "default.conf already exists in target directory"
    cp requirements.txt "$MANAGER_DIR/" 2>/dev/null || log "requirements.txt already exists in target directory"
else
    log "Already running from manager directory, skipping file copy"
fi

# Set proper permissions
chown -R $(logname):$(logname) "$MANAGER_DIR"
chmod +x "$MANAGER_DIR/vps-manager.py"

# Detect Python interpreter
log "Detecting Python interpreter..."
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    # Check if it's Python 3
    if python -c "import sys; exit(0 if sys.version_info[0] == 3 else 1)" 2>/dev/null; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    error "Python 3 not found. Please install Python 3."
fi

log "Using Python interpreter: $PYTHON_CMD"

# Fix line endings in vps-manager.py (convert Windows CRLF to Unix LF)
log "Fixing line endings..."
sed -i 's/\r$//' "$MANAGER_DIR/vps-manager.py"

# Update shebang to use detected Python
log "Updating shebang line..."
sed -i "1s|.*|#!/usr/bin/env $PYTHON_CMD|" "$MANAGER_DIR/vps-manager.py"

# Install Python dependencies
log "Installing Python dependencies..."
cd "$MANAGER_DIR"
$PYTHON_CMD -m pip install -r requirements.txt

# Create symbolic link for easy access
log "Creating symbolic link..."
ln -sf "$MANAGER_DIR/vps-manager.py" /usr/local/bin/vps-manager

# Create systemd service (optional)
log "Creating systemd service file..."
cat > /etc/systemd/system/vps-manager.service << EOF
[Unit]
Description=VPS Manager Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$MANAGER_DIR
ExecStart=/usr/bin/python3 $MANAGER_DIR/vps-manager.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Ensure sites-available and sites-enabled directories exist
log "Ensuring NGINX sites directories exist..."
mkdir -p /etc/nginx/sites-available
mkdir -p /etc/nginx/sites-enabled

# Check if sites-enabled is included in nginx.conf (but don't modify it)
if ! grep -q "sites-enabled" /etc/nginx/nginx.conf; then
    warn "sites-enabled directory is not included in nginx.conf"
    warn "You may need to manually add 'include /etc/nginx/sites-enabled/*;' to your nginx.conf"
    warn "This is typically found in the http block of /etc/nginx/nginx.conf"
fi

# Test NGINX configuration
log "Testing NGINX configuration..."
if nginx -t; then
    log "NGINX configuration test passed"
    systemctl reload nginx
else
    error "NGINX configuration test failed"
fi

# Create initial documentation
log "Creating documentation..."
cat > "$MANAGER_DIR/README.md" << 'EOF'
# VPS Manager

A comprehensive terminal-based manager for NGINX domains, SSL certificates, and configurations.

## Usage

### Start the Manager
```bash
sudo vps-manager
```

### Command Line Usage
```bash
# Start the interactive manager
sudo python3 /home/$(whoami)/manager/vps-manager.py

# Or use the symbolic link
sudo vps-manager
```

### Features

- **Domain Management**: Add, edit, delete, and list domains
- **SSL Certificates**: Automatic SSL certificate generation with certbot
- **Configuration Templates**: Use default or custom NGINX configurations
- **Backup & Restore**: Automatic backups of configurations
- **Logging**: Comprehensive logging system
- **Terminal UI**: Beautiful terminal-based interface

### Directory Structure

```
~/manager/
├── vps-manager.py          # Main application
├── domains.json            # Domain configurations
├── manager.log             # Application logs
├── templates/
│   └── default.conf        # Default NGINX template
├── backups/                # Configuration backups
└── custom-configs/         # Custom NGINX configurations
```

### Custom Configurations

To create custom NGINX configurations:

1. Create a `.conf` file in `~/manager/custom-configs/`
2. Use template variables in your configuration:
   - `$DOMAIN` - Domain name
   - `$PORT` - Backend port
   - `$SSL_CERT_PATH` - SSL certificate path
   - `$SSL_KEY_PATH` - SSL private key path

### Template Variables

Available variables for NGINX configurations:

- `$DOMAIN` - The domain name (e.g., example.com)
- `$PORT` - Backend application port (e.g., 3000)
- `$SSL_CERT_PATH` - Path to SSL certificate
- `$SSL_KEY_PATH` - Path to SSL private key

### Troubleshooting

- Check logs: `tail -f ~/manager/manager.log`
- Test NGINX config: `sudo nginx -t`
- Reload NGINX: `sudo systemctl reload nginx`
- Restart NGINX: `sudo systemctl restart nginx`

### Requirements

- Ubuntu 24.04 or compatible
- Python 3.8+
- NGINX
- Certbot
- Root privileges
EOF

# Set final permissions
chown $(logname):$(logname) "$MANAGER_DIR/README.md"

log "Installation completed successfully!"
log ""
log "${BLUE}Next steps:${NC}"
log "1. Run 'sudo vps-manager' to start the manager"
log "2. Add your first domain using the interactive interface"
log "3. Check the documentation at $MANAGER_DIR/README.md"
log ""
log "${GREEN}Installation directory: $MANAGER_DIR${NC}"
log "${GREEN}Command to start: sudo vps-manager${NC}"
log ""
log "Happy managing! 🚀"