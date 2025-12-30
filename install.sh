#!/bin/bash

# VPS Manager Installation Script
# This script installs VPS Manager and its dependencies

set -e

echo "VPS Manager Installation Script"
echo "================================"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "This script should not be run as root. Please run as a regular user with sudo access."
   exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install system packages
install_system_package() {
    local package=$1
    if command_exists apt; then
        sudo apt update
        sudo apt install -y "$package"
    elif command_exists yum; then
        sudo yum install -y "$package"
    elif command_exists dnf; then
        sudo dnf install -y "$package"
    else
        echo "Unsupported package manager. Please install $package manually."
        return 1
    fi
}

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv vps-manager-env
source vps-manager-env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install the package in development mode
echo "Installing VPS Manager..."
pip install -e .

# Check system dependencies
echo "Checking system dependencies..."

# Check NGINX
if ! command_exists nginx; then
    echo "NGINX not found. Installing..."
    install_system_package nginx
    sudo systemctl enable nginx
    sudo systemctl start nginx
else
    echo "✓ NGINX is installed"
fi

# Check Certbot
if ! command_exists certbot; then
    echo "Certbot not found. Installing..."
    install_system_package certbot
    if command_exists apt; then
        install_system_package python3-certbot-nginx
    fi
else
    echo "✓ Certbot is installed"
fi

# Check UFW
if ! command_exists ufw; then
    echo "UFW not found. Installing..."
    install_system_package ufw
else
    echo "✓ UFW is installed"
fi

# Check Docker (optional)
if ! command_exists docker; then
    echo "Docker not found. Installing (optional)..."
    install_system_package docker.io
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
    echo "✓ Docker installed. You may need to log out and back in for group changes to take effect."
else
    echo "✓ Docker is installed"
fi

# Run tests
echo "Running setup tests..."
if python test_setup.py; then
    echo "✓ All tests passed!"
else
    echo "✗ Some tests failed. Please check the output above."
    exit 1
fi

# Create activation script
cat > activate_vps_manager.sh << 'EOF'
#!/bin/bash
# Activation script for VPS Manager environment
source vps-manager-env/bin/activate
echo "VPS Manager environment activated."
echo "Run 'vps-manager' to start the application."
EOF

chmod +x activate_vps_manager.sh

# Check if installation was successful
if command -v vps-manager &> /dev/null; then
    echo ""
    echo "✓ VPS Manager installed successfully!"
    echo ""
    echo "To activate the environment and run VPS Manager:"
    echo "  source activate_vps_manager.sh"
    echo "  vps-manager"
    echo ""
    echo "Or run directly:"
    echo "  source vps-manager-env/bin/activate && vps-manager"
    echo ""
    echo "For help:"
    echo "  vps-manager --help"
    echo ""
    echo "To check your environment:"
    echo "  vps-manager --check"
else
    echo "✗ Installation failed. Please check the output above."
    exit 1
fi

echo ""
echo "Installation complete! Run 'vps-manager' to start."