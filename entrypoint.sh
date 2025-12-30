#!/bin/bash

# This script runs when the container starts

echo "Starting VPS Manager container setup..."

# Define the manager directory
MANAGER_DIR="/root/manager"

# Ensure we are in the right directory
cd "$MANAGER_DIR"

# Install the VPS Manager package
if [ -f "setup.py" ]; then
    echo "Installing VPS Manager package..."
    pip3 install -e . --break-system-packages
fi

# Ensure NGINX directories exist
mkdir -p /etc/nginx/sites-available
mkdir -p /etc/nginx/sites-enabled

# Start NGINX in the background
echo "Starting NGINX..."
nginx

# Keep the container running with a shell
echo "Container setup complete. You can now run 'vps-manager'"
/bin/bash
