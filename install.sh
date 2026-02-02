#!/bin/bash
set -e

# Detect if running with sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo bash install.sh)"
    exit 1
fi

# Detect the real user who invoked sudo
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    # Fallback to current user if not using sudo (unlikely due to EUID check)
    REAL_USER=$(whoami)
    REAL_HOME="$HOME"
fi

# Get the absolute installation directory
PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
WRAPPER_SCRIPT="$PROJECT_DIR/run_backend.sh"
ICON_PATH="$PROJECT_DIR/icon.png"

echo "Installing Universal Linux Hotspot for user: $REAL_USER"
echo "Location: $PROJECT_DIR"

# 1. Setup Python Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing dependencies..."
"$PYTHON_BIN" -m pip install --upgrade pip
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    "$PYTHON_BIN" -m pip install -r "$PROJECT_DIR/requirements.txt"
else
    # Default requirements if file missing
    "$PYTHON_BIN" -m pip install PyQt6 qrcode Pillow
fi

# 2. Setup Sudoers for Wrapper Script
SUDOERS_FILE="/etc/sudoers.d/hotspot_universal_$(basename "$PROJECT_DIR")"
# Sanitize filename (allow dots for /etc/sudoers.d/)
SUDOERS_FILE=$(echo "$SUDOERS_FILE" | sed 's/[^a-zA-Z0-9_./\-]//g')

echo "Configuring sudoers at $SUDOERS_FILE..."
echo "$REAL_USER ALL=(ALL) NOPASSWD: $WRAPPER_SCRIPT" > "$SUDOERS_FILE"
chmod 440 "$SUDOERS_FILE"

# 3. Setup Desktop Shortcut
APPS_DIR="$REAL_HOME/.local/share/applications"
AUTOSTART_DIR="$REAL_HOME/.config/autostart"
DESKTOP_FILE="$APPS_DIR/universal-hotspot.desktop"

mkdir -p "$APPS_DIR"
mkdir -p "$AUTOSTART_DIR"

echo "Creating desktop shortcut at $DESKTOP_FILE..."

cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=Universal Hotspot
Comment=Hardened Linux Hotspot Manager
Exec=$PYTHON_BIN $PROJECT_DIR/hotspot_gui.py
Icon=$ICON_PATH
Terminal=false
Categories=Network;Settings;
Keywords=Hotspot;Wifi;Access Point;
EOF

chown "$REAL_USER":"$REAL_USER" "$DESKTOP_FILE"
chmod +x "$DESKTOP_FILE"

# 4. Setup Autostart
cp "$DESKTOP_FILE" "$AUTOSTART_DIR/universal-hotspot.desktop"
echo "X-GNOME-Autostart-enabled=true" >> "$AUTOSTART_DIR/universal-hotspot.desktop"
chown "$REAL_USER":"$REAL_USER" "$AUTOSTART_DIR/universal-hotspot.desktop"

# 5. Fix permissions for project files
chown -R "$REAL_USER":"$REAL_USER" "$PROJECT_DIR"
chmod +x "$PROJECT_DIR/hotspot_backend.py"
chmod +x "$PROJECT_DIR/hotspot_gui.py"
chmod +x "$WRAPPER_SCRIPT"

echo "-----------------------------------------------"
echo "Installation Successful!"
echo "User: $REAL_USER"
echo "Binary: $PYTHON_BIN"
echo "Sudoers: $SUDOERS_FILE"
echo "-----------------------------------------------"
echo "You can now find 'Universal Hotspot' in your application menu."
