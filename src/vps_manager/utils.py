import logging
import os
from pathlib import Path

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

def setup_logging():
    """Setup logging configuration"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(LOG_FILE),
            # logging.StreamHandler() # Don't log to stream as it messes up TUI
        ]
    )

def get_logger(name: str):
    return logging.getLogger(name)
