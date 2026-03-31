#!/bin/bash
# Installation script for dbus-wattcycle-ble on Venus OS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/data/dbus-wattcycle-ble"
SERVICE_DIR="/service/dbus-wattcycle-ble"

echo "==================================="
echo "dbus-wattcycle-ble Installation"
echo "==================================="
echo ""

# Function to print error and exit
error_exit() {
    echo "ERROR: $1"
    exit 1
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    error_exit "Python 3 is not installed"
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

# Check Python version is 3.11+
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "WARNING: Python 3.11+ is recommended. Found Python $PYTHON_VERSION"
    echo "The wattcycle_ble library requires Python 3.11+"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if pip is available
echo "Checking pip..."
if ! command -v pip3 &> /dev/null; then
    error_exit "pip3 is not installed. Install with: apt-get install python3-pip"
fi

# Check Bluetooth support
echo "Checking Bluetooth support..."
if [ ! -d /sys/class/bluetooth ]; then
    echo "WARNING: No Bluetooth interface detected"
    echo "This service requires Bluetooth to communicate with Wattcycle batteries"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "Bluetooth interface found"
fi

# Stop existing service if running
echo ""
echo "Checking for existing service..."
if [ -d "$SERVICE_DIR" ]; then
    echo "Stopping existing service..."
    sv stop "$SERVICE_DIR" 2>/dev/null || true
    rm -f "$SERVICE_DIR"
fi

# Create installation directory
echo ""
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Copy files
echo "Copying files..."
cp -r "$SCRIPT_DIR/dbus_wattcycle_ble" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/config.yml" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install -r "$INSTALL_DIR/requirements.txt" || {
    echo "Failed to install dependencies. Trying with --break-system-packages..."
    pip3 install --break-system-packages -r "$INSTALL_DIR/requirements.txt"
}

# Check configuration
echo ""
echo "Checking configuration..."
if [ ! -f "$INSTALL_DIR/config.yml" ]; then
    error_exit "config.yml not found in installation directory"
fi

# Prompt for MAC address if not set
MAC_ADDRESS=$(grep "mac_address:" "$INSTALL_DIR/config.yml" | awk '{print $2}' | tr -d '"')

if [ -z "$MAC_ADDRESS" ] || [ "$MAC_ADDRESS" = "C0:D6:3C:57:EF:2F" ]; then
    echo ""
    echo "You need to configure your battery's MAC address."
    echo "You can find it by running: pip3 show wattcycle-ble && wattcycle-ble scan"
    echo ""
    read -p "Enter your battery's MAC address (leave blank to skip): " USER_MAC
    if [ -n "$USER_MAC" ]; then
        sed -i "s/mac_address: \".*\"/mac_address: \"$USER_MAC\"/" "$INSTALL_DIR/config.yml"
        echo "MAC address updated in config.yml"
    else
        echo "WARNING: You must update the MAC address in $INSTALL_DIR/config.yml before starting the service"
    fi
fi

# Create service directory and symlink
echo ""
echo "Installing service..."
mkdir -p "$SERVICE_DIR"
ln -sf "$SCRIPT_DIR/service/run" "$SERVICE_DIR/run"

# Start service
echo "Starting service..."
sv start "$SERVICE_DIR" || {
    echo "Failed to start service. Checking logs..."
    if [ -f "/var/log/dbus-wattcycle-ble/main/current" ]; then
        echo "Service logs:"
        tail -20 "/var/log/dbus-wattcycle-ble/main/current"
    fi
    error_exit "Failed to start service"
}

# Wait a moment and check service status
sleep 2
if sv status "$SERVICE_DIR" | grep -q "up"; then
    echo ""
    echo "==================================="
    echo "Installation successful!"
    echo "==================================="
    echo ""
    echo "Service status:"
    sv status "$SERVICE_DIR"
    echo ""
    echo "Configuration file: $INSTALL_DIR/config.yml"
    echo "Service directory: $SERVICE_DIR"
    echo ""
    echo "To view logs:"
    echo "  tail -f /var/log/dbus-wattcycle-ble/main/current"
    echo ""
    echo "To restart the service:"
    echo "  sv restart $SERVICE_DIR"
    echo ""
    echo "The battery should appear in your Venus GUI within 1-2 minutes."
    echo "Go to Settings -> Devices to verify."
    echo ""
else
    echo ""
    echo "==================================="
    echo "Installation completed with warnings"
    echo "==================================="
    echo ""
    echo "Service may not be running. Check logs:"
    echo "  tail -f /var/log/dbus-wattcycle-ble/main/current"
    echo ""
    echo "Service status:"
    sv status "$SERVICE_DIR"
fi
