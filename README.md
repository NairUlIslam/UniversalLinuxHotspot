# 📡 Universal Linux Hotspot

A **powerful, portable, and user-friendly** Wi-Fi hotspot application for Linux. Transform any Linux machine into a wireless access point with a beautiful system tray GUI, smart interface detection, and comprehensive safety features.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![Platform](https://img.shields.io/badge/platform-Linux-orange.svg)

---

## ✨ Features

### 🎨 **Beautiful System Tray GUI**
- Modern, dark-mode compatible interface
- Real-time data transfer speed monitoring
- One-click hotspot toggle
- QR code generation for easy device connection
- Desktop notifications for status updates

### 🧠 **Smart Interface Detection**
The application intelligently identifies and labels all your network interfaces:

| Icon | Interface Type | Description |
|------|---------------|-------------|
| 📶 | Built-in Wi-Fi | Internal laptop/desktop Wi-Fi card |
| 🔌 | USB Wi-Fi Adapter | External USB wireless adapter |
| 🔗 | Ethernet | Wired network connection |
| 📱 | Mobile Broadband | 4G/LTE USB modems (wwan) |
| 📱 | Phone Tethering | USB tethered Android/iPhone |
| 🔒 | VPN Tunnel | WireGuard, OpenVPN, etc. |
| 🌉 | Bridge | Network bridge interfaces |

### 🎯 **Dual Interface Selection**
Explicitly choose:
- **Hotspot Interface**: Which Wi-Fi adapter broadcasts the hotspot
- **Internet Source**: Where to route client traffic (Ethernet, mobile, VPN, etc.)

### 🛡️ **Comprehensive Safety Features**
- **Single-adapter lockout protection**: Prevents accidental disconnection
- **RF-kill detection**: Alerts for hardware/software Wi-Fi blocks
- **Monitor mode detection**: Warns when interfaces are in monitor mode
- **AP mode validation**: Checks if adapter supports Access Point mode
- **5GHz band verification**: Per-interface frequency support checking

### ⚡ **Quick Settings (System Tray)**
Right-click the tray icon for instant access to:
- VPN routing toggle
- Hotspot interface selection
- Internet source selection
- Dark mode toggle

### 🔐 **Security & Access Control**
- WPA2 encryption with password protection
- Hidden network (stealth) mode
- MAC address filtering (allowlist/blocklist)
- Custom DNS server configuration

### ⏱️ **Convenience Features**
- Auto-off timer (1-120 minutes)
- Automatic startup on login
- Connected devices viewer
- Persistent settings

---

## 📋 Requirements

### System Requirements
- **Linux** with NetworkManager
- **Python 3.8+**
- **Wi-Fi adapter** with AP (Access Point) mode support

### Dependencies (Auto-installed)
- `PyQt6` - GUI framework
- `qrcode` - QR code generation
- `Pillow` - Image processing

### System Tools (Usually pre-installed)
- `nmcli` - NetworkManager CLI
- `iw` - Wireless interface configuration
- `iptables` - Firewall/NAT rules
- `rfkill` - RF switch management

---

## 🚀 Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/NairUlIslam/UniversalLinuxHotspot.git
cd UniversalLinuxHotspot
sudo bash install.sh
```

The installer will:
1. Create a Python virtual environment
2. Install all dependencies
3. Configure passwordless sudo for the hotspot backend
4. Create desktop shortcuts and autostart entries

### Manual Installation

```bash
git clone https://github.com/NairUlIslam/UniversalLinuxHotspot.git
cd UniversalLinuxHotspot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run (requires sudo for network operations)
./venv/bin/python hotspot_gui.py
```

---

## 🖥️ Usage

### Starting the Application

After installation, you can:
- **Application Menu**: Search for "Universal Hotspot"
- **Command Line**: `./venv/bin/python hotspot_gui.py`

### Basic Workflow

1. **Right-click** the system tray icon
2. Click **"Start Hotspot"**
3. Share the QR code or credentials with devices
4. Click **"Stop Hotspot"** when done

### Settings Configuration

Access **Settings** from the tray menu to configure:

| Setting | Description |
|---------|-------------|
| **Network Name (SSID)** | The name of your hotspot network |
| **Password** | WPA2 password (min 8 characters) |
| **Hotspot Interface** | Which Wi-Fi creates the hotspot |
| **Internet Source** | Where clients get internet from |
| **Frequency Band** | 2.4 GHz (range) or 5 GHz (speed) |
| **Hidden Network** | Hide SSID from public scanning |
| **Custom DNS** | Override default DNS (e.g., 1.1.1.1) |
| **Auto-off Timer** | Automatically stop after X minutes |
| **VPN Routing** | Route client traffic through VPN |

---

## 🔧 Interface Selection Guide

### Understanding Your Interfaces

The app shows detailed labels for each interface:

```
📶 Built-in Wi-Fi [AP, 5GHz] 🌐 → HomeNetwork (wlp3s0)
│       │           │    │   │        │         │
│       │           │    │   │        │         └── Device name
│       │           │    │   │        └── Connected network
│       │           │    │   └── Currently providing internet
│       │           │    └── Supports 5GHz band
│       │           └── Supports Access Point mode
│       └── Interface type
└── Icon indicating type
```

### Common Scenarios

#### Scenario 1: Laptop with Ethernet + Built-in Wi-Fi
**Optimal Setup** ✅
- Internet Source: 🔗 Ethernet
- Hotspot Interface: 📶 Built-in Wi-Fi

#### Scenario 2: Laptop with USB Wi-Fi Adapter
**Optimal Setup** ✅
- Internet Source: 📶 Built-in Wi-Fi (for regular connection)
- Hotspot Interface: 🔌 USB Wi-Fi Adapter

#### Scenario 3: Single Wi-Fi Only (No Ethernet)
**⚠️ Risky** - Starting hotspot will disconnect you!
- The app will **block** this by default
- Use `--force-single-interface` flag to override (advanced users)

#### Scenario 4: Mobile Broadband / Phone Tethering
**Works great** ✅
- Internet Source: 📱 Mobile Broadband / Phone Tethering
- Hotspot Interface: 📶 Any Wi-Fi with AP support

---

## 🛡️ Edge Cases & Troubleshooting

### Hardware Issues

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Wi-Fi hardware switch OFF** | RF-kill detected | Toggle physical switch on laptop |
| **Wi-Fi software blocked** | RF-kill detected | Run: `sudo rfkill unblock wifi` |
| **No AP mode support** | iw capability check | Use a different USB Wi-Fi adapter |
| **Interface in monitor mode** | iw mode check | Run: `sudo iw dev <iface> set type managed` |
| **Interface DOWN** | ip link check | Check driver or hardware connection |
| **5GHz selected but unsupported** | Per-interface check | Switch to 2.4 GHz band |

### Network Issues

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Connected but no IP** | IP address check | Check DHCP or static IP configuration |
| **No internet source** | Route check | Connect Ethernet or other internet source |
| **VPN not routing** | Tunnel detection | Enable "Route via VPN" in settings |
| **Clients can't get IP** | DHCP check | Restart hotspot or check NetworkManager |

### Safety Blocks

| Block | Reason | Override |
|-------|--------|----------|
| **Single adapter + WiFi internet** | Would disconnect you completely | `--force-single-interface` flag |
| **No AP support** | Hardware limitation | Use compatible adapter |
| **Monitor mode** | Cannot run AP in monitor mode | Set interface to managed mode |

---

## 📁 Project Structure

```
UniversalLinuxHotspot/
├── hotspot_gui.py      # Main GUI application (system tray)
├── hotspot_backend.py  # Backend (runs as root for network ops)
├── run_backend.sh      # Wrapper script for sudo execution
├── install.sh          # Installation script
├── requirements.txt    # Python dependencies
├── icon.png            # Application icon
└── README.md           # This file
```

---

## ⚙️ Command Line Options

The backend supports various command-line options:

```bash
# Start hotspot with defaults
sudo ./venv/bin/python hotspot_backend.py

# Custom SSID and password
sudo ./venv/bin/python hotspot_backend.py -s "MyHotspot" -p "password123"

# Use specific interface
sudo ./venv/bin/python hotspot_backend.py -i wlan1

# 5GHz band
sudo ./venv/bin/python hotspot_backend.py -b a

# Hidden network
sudo ./venv/bin/python hotspot_backend.py --hidden

# Exclude VPN from routing
sudo ./venv/bin/python hotspot_backend.py --exclude-vpn

# Force single interface (dangerous!)
sudo ./venv/bin/python hotspot_backend.py --force-single-interface

# Auto-off timer (minutes)
sudo ./venv/bin/python hotspot_backend.py -t 30

# Stop hotspot
sudo ./venv/bin/python hotspot_backend.py --stop

# MAC filtering
sudo ./venv/bin/python hotspot_backend.py --block-mac "AA:BB:CC:DD:EE:FF"
sudo ./venv/bin/python hotspot_backend.py --allow-mac "AA:BB:CC:DD:EE:FF"
```

---

## 🔒 Security Considerations

### Sudo Configuration
The installer creates a sudoers entry that allows passwordless execution of **only** the `run_backend.sh` wrapper script. This is necessary because:
- Network operations require root privileges
- `nmcli` hotspot creation needs elevated access
- `iptables` rules for NAT require root

The entry is created at: `/etc/sudoers.d/hotspot_universal_UniversalLinuxHotspot`

### Password Security
- Passwords are stored locally in `~/.config/hotspot_gui_config.json`
- The config file permissions should be set to user-only readable
- WPA2-PSK encryption is used for the hotspot

---

## 🐛 Known Limitations

1. **NetworkManager Required**: The application depends on NetworkManager and `nmcli`
2. **One Hotspot at a Time**: Cannot run multiple hotspots simultaneously
3. **No WPA3 Support**: Currently limited to WPA2-PSK
4. **IPv4 Only**: IPv6 is not configured for hotspot clients
5. **Channel Selection**: Automatic channel selection by NetworkManager

---

## 📊 Status Files

The application uses temporary files for IPC:

| File | Purpose |
|------|---------|
| `/tmp/hotspot_backend.pid` | Backend process ID (for status checks) |
| `/tmp/hotspot_status.json` | Status messages for GUI notifications |
| `/tmp/hotspot_qr.png` | Generated QR code image |
| `~/.config/hotspot_gui_config.json` | User settings and preferences |

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

### Development Setup

```bash
git clone https://github.com/NairUlIslam/UniversalLinuxHotspot.git
cd UniversalLinuxHotspot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run in development mode
./venv/bin/python hotspot_gui.py
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- NetworkManager team for the excellent `nmcli` tool
- PyQt6 for the cross-platform GUI framework
- All contributors and users of this project

---

## 📞 Support

If you encounter any issues:
1. Check the [Troubleshooting](#-edge-cases--troubleshooting) section
2. Open an issue on GitHub with:
   - Your Linux distribution and version
   - Output of `nmcli device status`
   - Output of `iw list | grep -A 10 "Supported interface modes"`
   - Any error messages displayed

---

**Made with ❤️ for the Linux community**
