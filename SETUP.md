# VPS NGINX Domain Manager v2.0 - Setup Guide

## Quick Start

### Installation

1. **Clone or download the repository**
```bash
git clone https://github.com/k6w/vps-manager.git
cd vps-manager
```

2. **Install Python dependencies**
```bash
# On Linux/macOS
pip install -r requirements.txt

# On Windows (also install windows-curses)
pip install -r requirements.txt
pip install windows-curses
```

3. **Install the package (optional)**
```bash
pip install -e .
```

### Running VPS Manager

**With UI (Recommended):**
```bash
python -m vps_manager.main
```

**Check environment:**
```bash
python -m vps_manager.main --check
```

**Batch mode (add domain without UI):**
```bash
python -m vps_manager.main --batch --add-domain example.com --port 3000 --ssl
```

## First-Run Setup

When you run VPS Manager for the first time, it will automatically launch a setup wizard that will:

1. **Check Dependencies** - Verify and offer to install:
   - NGINX Web Server
   - Certbot (Let's Encrypt)
   - UFW Firewall
   - Docker

2. **Configure Features** - Set up:
   - Alert Notifications (Email, Slack, Discord, Webhooks)
   - Firewall Management (UFW rules)
   - Security Scanner (vulnerability checks)
   - Docker Integration (auto-discovery)
   - Version Control (Git-like system)

3. **Save Configuration** - All settings are saved to:
   - `~/.vps-manager/config.json`

## Feature Configuration

### Email Notifications

During setup, you'll be asked for:
- **SMTP Server**: `smtp.gmail.com` (for Gmail)
- **SMTP Port**: `587` (default)
- **Username**: Your email address
- **Password**: App-specific password (recommended)
- **From Email**: Email address to send from
- **To Emails**: Comma-separated list of recipients

**Gmail Setup:**
1. Enable 2FA on your Google account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the app password instead of your regular password

### Slack Notifications

1. Create a Slack App: https://api.slack.com/apps
2. Add "Incoming Webhooks" feature
3. Generate a webhook URL
4. Enter the URL during setup

### Discord Notifications

1. Go to your Discord server settings
2. Integrations > Webhooks > New Webhook
3. Copy the webhook URL
4. Enter the URL during setup

### Firewall Configuration

The setup wizard can automatically configure UFW with web server rules:
- Allow SSH (port 22)
- Allow HTTP (port 80)
- Allow HTTPS (port 443)

You can customize rules later in the Firewall Management menu.

## Manual Configuration

You can always reconfigure settings through the UI:
1. Launch VPS Manager
2. Select "Settings" from the main menu
3. Choose the feature to configure

## Testing Your Setup

Run the test script to verify everything is working:

```bash
python test_setup.py
```

This will check:
- All modules can be imported
- Configuration system works
- Manager initializes correctly
- No emojis in the codebase (symbols only)

## Directory Structure

VPS Manager creates these directories:
```
~/.vps-manager/
├── config.json          # Application configuration
├── data.json            # Domain configurations
├── backups/             # Configuration backups
├── logs/                # Application logs
├── vcs/                 # Version control repository
│   ├── commits/         # Commit data
│   ├── branches/        # Branch data
│   └── snapshots/       # Configuration snapshots
└── templates/           # NGINX templates
```

## Dependencies

### Required (Linux/VPS Server):
- Python 3.6+
- NGINX
- Certbot
- UFW (Uncomplicated Firewall)
- Docker (optional, for container integration)

### Python Packages:
All listed in `requirements.txt`:
- No external dependencies required for core functionality
- `rich` (optional, for colored terminal output)
- `windows-curses` (Windows only, for UI)

## Troubleshooting

### "No module named '_curses'" on Windows

Install windows-curses:
```bash
pip install windows-curses
```

### "Permission denied" errors

Run commands with sudo on Linux:
```bash
sudo python -m vps_manager.main
```

### Configuration not saving

Check directory permissions:
```bash
ls -la ~/.vps-manager/
```

### Dependencies not installing

The setup wizard can install dependencies, or manually:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx ufw docker.io

# Enable and start services
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl enable docker
sudo systemctl start docker
```

## Features Overview

### Version Control System
- Git-like interface for configuration management
- Commit, branch, tag, and restore configurations
- View diffs and history
- Automatic backup creation

### Firewall Management
- UFW integration
- Allow/deny/limit rules
- Port and IP-based rules
- Quick setup presets

### Security Scanner
- SSL certificate checks
- NGINX security headers
- SSH configuration audit
- Port scan detection
- Firewall status check

### Alerts & Monitoring
- Multiple notification channels
- Domain status monitoring
- SSL expiration alerts
- Resource usage tracking
- Custom alert rules

### Docker Integration
- Auto-discover running containers
- Generate NGINX configs for containers
- Container management (start/stop/restart)
- View container logs

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/k6w/vps-manager/issues
- Documentation: See DOCS.md and NEW_FEATURES.md

## License

See LICENSE file for details.
