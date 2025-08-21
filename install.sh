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

# Move files to manager directory (only if not already there)
log "Moving manager files..."
if [ "$(pwd)" != "$MANAGER_DIR" ]; then
    # Move main files
    if [ -f "vps-manager.py" ] && [ ! -f "$MANAGER_DIR/vps-manager.py" ]; then
        mv vps-manager.py "$MANAGER_DIR/"
        log "Moved vps-manager.py to $MANAGER_DIR"
    elif [ -f "vps-manager.py" ]; then
        log "vps-manager.py already exists in target directory, removing source"
        rm -f vps-manager.py
    fi
    
    if [ -f "default.conf" ] && [ ! -f "$MANAGER_DIR/templates/default.conf" ]; then
        mv default.conf "$MANAGER_DIR/templates/"
        log "Moved default.conf to $MANAGER_DIR/templates"
    elif [ -f "default.conf" ]; then
        log "default.conf already exists in target directory, removing source"
        rm -f default.conf
    fi
    
    if [ -f "requirements.txt" ] && [ ! -f "$MANAGER_DIR/requirements.txt" ]; then
        mv requirements.txt "$MANAGER_DIR/"
        log "Moved requirements.txt to $MANAGER_DIR"
    elif [ -f "requirements.txt" ]; then
        log "requirements.txt already exists in target directory, removing source"
        rm -f requirements.txt
    fi
    
    # Move install.sh itself to manager directory
    if [ -f "install.sh" ] && [ ! -f "$MANAGER_DIR/install.sh" ]; then
        mv install.sh "$MANAGER_DIR/"
        log "Moved install.sh to $MANAGER_DIR"
    fi
else
    log "Already running from manager directory, skipping file move"
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

# Create and setup virtual environment
log "Creating Python virtual environment..."
cd "$MANAGER_DIR"
$PYTHON_CMD -m venv venv

# Install Python dependencies in virtual environment
log "Installing Python dependencies in virtual environment..."
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Update vps-manager.py to use virtual environment Python
log "Updating vps-manager.py to use virtual environment..."
sed -i "1s|.*|#!$MANAGER_DIR/venv/bin/python3|" "$MANAGER_DIR/vps-manager.py"

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
ExecStart=$MANAGER_DIR/venv/bin/python3 $MANAGER_DIR/vps-manager.py
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
# Start the interactive manager (using virtual environment)
sudo /home/$(whoami)/manager/vps-manager.py

# Or use the symbolic link
sudo vps-manager

# Manual activation of virtual environment (if needed)
cd /home/$(whoami)/manager
source venv/bin/activate
python3 vps-manager.py
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
├── requirements.txt        # Python dependencies
├── venv/                   # Python virtual environment
│   ├── bin/
│   ├── lib/
│   └── ...
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