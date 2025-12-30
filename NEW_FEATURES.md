# VPS Manager - New Features Guide

This document describes the newly added features to the VPS Manager.

## 🎉 New Features Summary

The VPS Manager has been enhanced with five major feature sets:

1. **Multi-Domain SSL Wildcards** - Wildcard certificate support
2. **Firewall Management (UFW)** - Complete firewall control
3. **Security Hardening** - Automated security scanning and hardening
4. **Logging & Alerting** - Comprehensive monitoring and notifications
5. **Docker Integration** - Seamless Docker container management

---

## 1. Multi-Domain SSL Wildcards

### Features
- Support for wildcard SSL certificates (`*.example.com`)
- DNS-01 challenge support for wildcard certificates
- Configurable DNS plugins (Cloudflare, Route53, etc.)
- Automatic subdomain management
- Certificate sharing across multiple subdomains

### Usage

#### Configure DNS Plugin (for Wildcard Certificates)
```bash
# Edit VPS Manager config
nano ~/manager/config.json
```

Add DNS plugin configuration:
```json
{
  "dns_plugin": "dns-cloudflare",
  "certbot_email": "admin@example.com"
}
```

#### Install DNS Plugin
```bash
# For Cloudflare
sudo apt install python3-certbot-dns-cloudflare

# Create credentials file
sudo nano /etc/letsencrypt/cloudflare.ini
```

Add your Cloudflare API credentials:
```ini
dns_cloudflare_email = your-email@example.com
dns_cloudflare_api_key = your-api-key
```

```bash
sudo chmod 600 /etc/letsencrypt/cloudflare.ini
```

#### Generate Wildcard Certificate
When adding a domain, use the wildcard format:
- Domain: `*.example.com`
- The system will automatically use DNS-01 challenge

### Technical Details
- Enhanced `Domain` class with `wildcard` attribute
- Modified `generate_ssl_certificate()` to support DNS challenges
- Automatic detection of wildcard domains
- Fallback to manual DNS challenge if plugin not configured

---

## 2. Firewall Management (UFW)

### Features
- Complete UFW firewall management from the UI
- View firewall status and rules
- Enable/disable firewall
- Allow/deny/limit ports
- IP-based access control
- Quick setup for web servers
- Rate limiting for brute-force protection

### Usage

#### Access Firewall Management
1. Main Menu → **"Firewall Management"**

#### Quick Setup for Web Server
Automatically configures:
- SSH (port 22) with rate limiting
- HTTP (port 80)
- HTTPS (port 443)

#### Allow a Port
```
Firewall Management → Allow Port
Enter port number: 3000
Protocol: tcp
Comment: Node.js App
```

#### Rate Limit SSH (Prevent Brute Force)
```
Firewall Management → Limit Port
Enter port: 22
Protocol: tcp
```

#### IP Whitelisting
```
Firewall Management → Allow from IP
Enter IP: 203.0.113.10
```

#### View All Rules
```
Firewall Management → List All Rules
```

### Module: `firewall.py`

**Classes:**
- `FirewallRule` - Represents a UFW rule
- `FirewallManager` - Manages all firewall operations

**Key Methods:**
- `enable()` / `disable()` - Control firewall state
- `allow_port()` / `deny_port()` / `limit_port()` - Port management
- `allow_from_ip()` / `deny_from_ip()` - IP-based rules
- `list_rules()` - Get all configured rules
- `quick_setup_web_server()` - One-click web server setup

---

## 3. Security Hardening

### Features
- Comprehensive security scanning
- SSL certificate expiration monitoring
- NGINX security headers validation
- SSH configuration audit
- System update checking
- Open port scanning
- Firewall status verification
- Security score calculation (0-100)
- Automated security header application
- Detailed security reports

### Usage

#### Run Security Scan
1. Main Menu → **"Security Scanner"**
2. Select **"Run Security Scan"**
3. Wait for scan to complete
4. View issues by severity

#### View Security Score
```
Security Scanner → View Security Score
```

Score interpretation:
- **90-100**: Excellent security posture
- **70-89**: Good, minor improvements needed
- **50-69**: Fair, several issues to address
- **0-49**: Poor, immediate action required

#### Apply Security Headers to Domain
```
Security Scanner → Apply Security Headers (Domain)
Select domain → Confirm
```

Automatically adds:
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000`

#### Export Security Report
```
Security Scanner → Export Security Report
```

Report saved to: `~/manager/security_report_YYYYMMDD_HHMMSS.txt`

### Security Checks Performed

1. **SSL Certificate Expiration**
   - Checks all domain certificates
   - Alerts for certificates expiring within 30 days
   - Critical alerts for expired certificates

2. **NGINX Security Headers**
   - Validates presence of security headers
   - Checks each domain configuration
   - Recommends missing headers

3. **SSH Configuration**
   - Checks for root login enabled
   - Validates password authentication settings
   - Detects empty password permissions

4. **System Updates**
   - Scans for available updates
   - Highlights security updates
   - Recommends update commands

5. **Open Ports**
   - Lists all listening ports
   - Identifies unexpected open ports
   - Compares against expected services

6. **Firewall Status**
   - Checks if UFW is installed
   - Verifies firewall is enabled
   - Recommends firewall activation

### Module: `security.py`

**Classes:**
- `SecurityIssue` - Represents a security finding
- `SecurityScanner` - Performs security scans
- `SecurityHardening` - Applies security fixes

**Severity Levels:**
- `CRITICAL` - Immediate action required
- `HIGH` - Address soon
- `MEDIUM` - Should be fixed
- `LOW` - Minor improvement
- `INFO` - Informational

---

## 4. Logging & Alerting

### Features
- Comprehensive alert management
- Multiple notification channels (Email, Slack, Discord, Webhooks, Commands)
- SSL expiration monitoring
- NGINX status monitoring
- Disk space monitoring
- Customizable alert rules
- Alert acknowledgment system
- Automated monitoring checks

### Usage

#### View Active Alerts
1. Main Menu → **"Alerts & Monitoring"**
2. Select **"View Active Alerts"**
3. Navigate with ←/→ arrows
4. Press 'A' to acknowledge

#### Run Monitoring Checks
```
Alerts & Monitoring → Run All Checks Now
```

Checks performed:
- SSL certificate expiration
- NGINX service status
- Disk space usage

#### Configure Notifications

1. Edit configuration file:
```bash
nano ~/manager/alert_config.json
```

2. Configure channels:

**Email Notifications:**
```json
{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "from_email": "vps-manager@yourdomain.com",
    "to_emails": ["admin@yourdomain.com"],
    "use_tls": true
  }
}
```

**Slack Webhook:**
```json
{
  "webhook": {
    "enabled": true,
    "type": "slack",
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  }
}
```

**Discord Webhook:**
```json
{
  "webhook": {
    "enabled": true,
    "type": "discord",
    "webhook_url": "https://discord.com/api/webhooks/YOUR/WEBHOOK/URL"
  }
}
```

**Custom Command:**
```json
{
  "command": {
    "enabled": true,
    "command": "echo '{title}: {message}' | wall"
  }
}
```

#### Test Notification
```
Alerts & Monitoring → Test Notification
```

Sends a test alert through all configured channels.

### Alert Types

- `SSL_EXPIRING` - Certificate expiring soon
- `SSL_EXPIRED` - Certificate has expired
- `NGINX_DOWN` - NGINX service not running
- `BACKEND_DOWN` - Backend service unreachable
- `SECURITY_ISSUE` - Security scan found issues
- `DISK_SPACE` - Low disk space
- `HIGH_TRAFFIC` - Unusual traffic detected
- `SYSTEM_UPDATE` - Updates available

### Alert Levels

- `CRITICAL` - Immediate attention required
- `WARNING` - Should be addressed
- `INFO` - Informational only

### Module: `alerts.py`

**Classes:**
- `Alert` - Represents an alert
- `AlertManager` - Manages alerts
- `NotificationChannel` - Base class for notifications
- `EmailNotification` - Email notifications
- `WebhookNotification` - Slack/Discord/Generic webhooks
- `CommandNotification` - Execute commands

**Key Methods:**
- `create_alert()` - Create and send alert
- `acknowledge_alert()` - Mark alert as seen
- `run_all_checks()` - Execute monitoring checks
- `clear_old_alerts()` - Clean up old alerts

### Automated Monitoring

Set up cron job for automated monitoring:

```bash
# Edit crontab
crontab -e

# Add line to check every hour
0 * * * * /usr/bin/python3 -c "from vps_manager.core import VPSManager; m = VPSManager(); m.alerts.run_all_checks()"
```

---

## 5. Docker Integration

### Features
- Automatic Docker container discovery
- One-click NGINX configuration for containers
- Container management (start/stop/restart)
- Container logs viewing
- Port mapping detection
- IP address detection for containers
- Suggested configurations based on container labels
- Docker Compose service discovery

### Usage

#### List Running Containers
```
Main Menu → Docker Integration → List Running Containers
```

Shows:
- Container name
- Image
- Status
- Exposed ports

#### Auto-Configure Container

Automatically sets up NGINX reverse proxy for a container:

```
Docker Integration → Auto-Configure Container
1. Select container
2. Enter domain name (e.g., app.example.com)
3. Choose SSL (Y/n)
4. Configuration created automatically
```

The system will:
- Detect container IP address
- Detect exposed port
- Create NGINX configuration
- Generate SSL certificate (if requested)
- Enable the site

#### Scan & Suggest Configs

Scans all running containers with web ports and suggests configurations:

```
Docker Integration → Scan & Suggest Configs
```

Shows:
- Container name and image
- Detected ports
- Suggested domain names
- Configuration status

#### View Container Details
```
Docker Integration → Container Details
Select container
```

Displays:
- Container ID
- Image
- Status
- Port mappings
- IP address

#### View Container Logs
```
Docker Integration → Container Logs
Select container
```

Features:
- Real-time log viewing
- Scrollable output
- Refresh capability (press 'R')
- Last 100 lines displayed

#### Container Label Support

Add labels to your Docker containers for automatic detection:

```yaml
# docker-compose.yml
version: '3'
services:
  web:
    image: nginx:latest
    labels:
      - "vps.domain=myapp.example.com"
      - "traefik.port=80"
    ports:
      - "3000:80"
```

The VPS Manager will:
- Detect the `vps.domain` label
- Suggest the domain in configuration
- Auto-detect the port from labels or port mappings

### Module: `docker_manager.py`

**Classes:**
- `DockerContainer` - Represents a container
- `DockerManager` - Manages Docker operations

**Key Methods:**
- `list_containers()` - Get all containers
- `auto_configure_container()` - Setup NGINX for container
- `scan_and_suggest_configs()` - Scan and suggest configs
- `get_container_ip()` - Get container IP
- `get_container_logs()` - Fetch logs
- `start_container()` / `stop_container()` / `restart_container()` - Container control

### Docker Integration Example

**Scenario:** You have a Node.js app running in Docker

1. **Run your app in Docker:**
```bash
docker run -d --name myapp -p 3000:3000 node-app:latest
```

2. **Configure NGINX via VPS Manager:**
```
Main Menu → Docker Integration → Auto-Configure Container
- Select: myapp
- Domain: api.example.com
- SSL: Yes
```

3. **Done!** Your app is now accessible at `https://api.example.com`

---

## Configuration Files

### New Configuration Files Created

1. **`~/manager/alert_config.json`**
   - Notification channel configuration
   - Email, Slack, Discord, Command settings

2. **`~/manager/alerts.json`**
   - Stored alerts and acknowledgments
   - Alert history

3. **`~/manager/security_report_*.txt`**
   - Exported security scan reports
   - Timestamped for tracking

### Enhanced Domain Configuration

The `domains.json` now includes:

```json
{
  "name": "example.com",
  "port": 3000,
  "ssl": true,
  "custom_config": null,
  "wildcard": false,
  "backend_ip": "172.17.0.2",
  "created_at": "2025-12-11T10:30:00",
  "updated_at": "2025-12-11T10:30:00"
}
```

New fields:
- `wildcard` - Whether this is a wildcard certificate domain
- `backend_ip` - Custom backend IP (for Docker containers)

---

## Best Practices

### Security
1. Run security scans weekly
2. Enable firewall before exposing server to internet
3. Use rate limiting on SSH (port 22)
4. Apply security headers to all domains
5. Monitor SSL certificate expiration

### Firewall
1. Start with deny-all incoming policy
2. Only allow necessary ports
3. Use rate limiting for SSH
4. Document rules with comments
5. Regular audit of firewall rules

### Alerts
1. Configure at least one notification channel
2. Set up automated monitoring checks
3. Acknowledge alerts promptly
4. Clear old alerts monthly
5. Test notifications after setup

### Docker
1. Use container labels for automatic detection
2. Monitor container logs regularly
3. Keep containers updated
4. Use specific tags instead of `:latest`
5. Document container port mappings

---

## Troubleshooting

### Firewall Issues

**Problem:** Can't access server after enabling firewall

**Solution:**
```bash
# From server console (not SSH)
sudo ufw allow 22
sudo ufw reload
```

**Problem:** Web server ports blocked

**Solution:**
```bash
sudo ufw allow 80
sudo ufw allow 443
sudo ufw reload
```

### Security Scanner Issues

**Problem:** False positives in scan

**Solution:**
- Review the recommendation
- If expected, acknowledge and document
- Configure exceptions if needed

### Alert Issues

**Problem:** Email notifications not working

**Solution:**
1. Check SMTP credentials in `alert_config.json`
2. For Gmail, use App Password, not account password
3. Test with: Alerts → Test Notification

**Problem:** Too many alerts

**Solution:**
1. Acknowledge resolved alerts
2. Clear old alerts: Alerts → Clear Old Alerts
3. Adjust monitoring thresholds in code

### Docker Issues

**Problem:** Can't detect Docker containers

**Solution:**
```bash
# Check Docker is running
sudo systemctl status docker

# Check permissions
sudo usermod -aG docker $USER
newgrp docker
```

**Problem:** Auto-configure fails

**Solution:**
1. Ensure container is running
2. Check container exposes ports
3. Manually specify port if detection fails
4. Verify domain DNS points to server

---

## Command Line Usage

### Run Security Scan
```python
from vps_manager.core import VPSManager
manager = VPSManager()
issues = manager.security.scan_all()
print(f"Found {len(issues)} issues")
```

### Check Firewall Status
```python
from vps_manager.core import VPSManager
manager = VPSManager()
is_active, status = manager.firewall.get_status()
print(f"Firewall: {status}")
```

### Create Alert
```python
from vps_manager.core import VPSManager
from vps_manager.alerts import AlertType, AlertLevel

manager = VPSManager()
manager.alerts.create_alert(
    AlertType.SECURITY_ISSUE,
    AlertLevel.WARNING,
    "Test Alert",
    "This is a test alert",
    {"key": "value"}
)
```

### List Docker Containers
```python
from vps_manager.core import VPSManager
manager = VPSManager()
success, containers = manager.docker.list_containers()
for container in containers:
    print(f"{container.name}: {container.status}")
```

---

## API Documentation

### VPSManager Properties

```python
manager = VPSManager()

# Access feature managers
manager.firewall  # FirewallManager instance
manager.security  # SecurityScanner instance
manager.alerts    # AlertManager instance
manager.docker    # DockerManager instance
```

### FirewallManager API

```python
firewall = manager.firewall

# Status
firewall.is_installed()  # -> (bool, str)
firewall.get_status()    # -> (bool, str, bool)

# Control
firewall.enable()   # -> (bool, str)
firewall.disable()  # -> (bool, str)
firewall.reload()   # -> (bool, str)

# Rules
firewall.allow_port(8080, "tcp")     # -> (bool, str)
firewall.deny_port(8080, "tcp")      # -> (bool, str)
firewall.limit_port(22, "tcp")       # -> (bool, str)
firewall.delete_rule(rule_number)    # -> (bool, str)

# IP Management
firewall.allow_from_ip("1.2.3.4")    # -> (bool, str)
firewall.deny_from_ip("1.2.3.4")     # -> (bool, str)

# Quick Setup
firewall.quick_setup_web_server()    # -> (bool, str)
```

### SecurityScanner API

```python
security = manager.security

# Scanning
issues = security.scan_all()                  # -> List[SecurityIssue]
security.scan_ssl_certificates()              # Scan SSL certs
security.scan_nginx_security_headers()        # Check headers
security.scan_ssh_configuration()             # Audit SSH

# Analysis
score = security.get_security_score()         # -> int (0-100)
grouped = security.get_issues_by_severity()   # -> Dict
report = security.generate_report()           # -> str
```

### AlertManager API

```python
alerts = manager.alerts

# Creating Alerts
alert = alerts.create_alert(
    alert_type,  # AlertType enum
    level,       # AlertLevel enum
    title,       # str
    message,     # str
    details      # Dict (optional)
)

# Managing Alerts
alerts.acknowledge_alert(alert)
alerts.get_unacknowledged_alerts()  # -> List[Alert]
alerts.get_alerts_by_level(level)   # -> List[Alert]
alerts.clear_old_alerts(days=30)

# Monitoring
alerts.check_ssl_expiration()
alerts.check_nginx_status()
alerts.check_disk_space()
alerts.run_all_checks()
```

### DockerManager API

```python
docker = manager.docker

# Container Discovery
is_installed, msg = docker.is_installed()
success, containers = docker.list_containers()
container = docker.get_container_by_name("myapp")

# Container Info
ip = docker.get_container_ip("myapp")
port = docker.get_container_port("myapp")
success, info = docker.inspect_container("myapp")

# Auto Configuration
success, msg = docker.auto_configure_container(
    container_name,
    domain,
    ssl=True
)

# Suggestions
suggestions = docker.scan_and_suggest_configs()

# Container Control
docker.start_container("myapp")
docker.stop_container("myapp")
docker.restart_container("myapp")

# Logs
success, logs = docker.get_container_logs("myapp", lines=100)
```

---

## Performance Considerations

### Security Scanner
- Full scan takes 10-30 seconds
- Safe to run hourly
- Minimal system impact

### Alert Monitoring
- Checks complete in 5-10 seconds
- Recommend running every 15-60 minutes
- Consider cron job for automation

### Docker Integration
- Container listing is instant
- No performance impact on containers
- NGINX proxying adds <1ms latency

---

## Future Enhancements

Potential additions in future versions:

1. **Firewall Management**
   - Geographic IP blocking
   - Automatic threat detection
   - Integration with fail2ban

2. **Security Hardening**
   - CVE database integration
   - Automated patching
   - Compliance checking (PCI-DSS, HIPAA)

3. **Alerting**
   - Machine learning anomaly detection
   - Custom alert rules via UI
   - Alert suppression windows

4. **Docker Integration**
   - Kubernetes support
   - Docker Swarm integration
   - Container health checks
   - Automatic scaling recommendations

---

## Support and Contribution

### Reporting Issues
- GitHub Issues: [github.com/k6w/vps-manager](https://github.com/k6w/vps-manager)
- Include: VPS Manager version, OS version, error messages, steps to reproduce

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Development Setup
```bash
git clone https://github.com/k6w/vps-manager.git
cd vps-manager
pip install -e .[dev]
```

---

## Changelog

### Version 2.0.0 (Current)

**New Features:**
- Multi-domain SSL wildcard support
- Complete UFW firewall management
- Security scanning and hardening
- Comprehensive alerting system
- Docker container integration

**Improvements:**
- Enhanced Domain class with wildcard and backend_ip support
- Lazy-loaded feature modules for better performance
- Improved error handling across all modules
- Better UI organization with new menu items

**Bug Fixes:**
- Various stability improvements
- Better error messages

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

- UFW (Uncomplicated Firewall) - Canonical Ltd.
- Let's Encrypt / Certbot - Internet Security Research Group
- Docker Inc. - Container platform
- NGINX - Open source web server

---

**Made with ❤️ for VPS administrators who value comprehensive management tools.**
