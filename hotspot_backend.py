import subprocess
import sys
import time
import signal
import re
import argparse
import os

# Configuration defaults
DEFAULT_HOTSPOT_NAME = "MintHotspot"
DEFAULT_PASSWORD = "password123" 
CONNECTION_NAME = "temp_hotspot_con"
PID_FILE = "/tmp/hotspot_backend.pid"

# State tracking
HOTSPOT_IFACE = None
CURRENT_UPSTREAM_IFACE = None
MAC_MODE = "block" # or "allow"
MAC_LIST = []
EXCLUDE_VPN = False

def run_command(command, check=True):
    try:
        result = subprocess.run(
            command,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if check:
            print(f"\n[!] Error executing command: {' '.join(command)}")
            print(f"[!] System Response: {e.stderr}")
            sys.exit(1)
        return None

def ensure_wifi_active(iface):
    print("Checking Wi-Fi radio status...")
    run_command(['nmcli', 'radio', 'wifi', 'on'], check=False)
    for _ in range(5):
        output = run_command(['nmcli', '-t', '-f', 'DEVICE,STATE', 'device'])
        if any(f"{iface}:disconnected" in line for line in output.split('\n')) or \
           any(f"{iface}:connected" in line for line in output.split('\n')):
            return
        time.sleep(1)
    print(f"Warning: Interface {iface} is still not fully ready, but proceeding...")

def get_wifi_interfaces():
    run_command(['nmcli', 'device', 'refresh'], check=False)
    output = run_command(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'device'])
    wifi_devices = []
    if output:
        for line in output.split('\n'):
            # Look for wifi devices, but exclude P2P
            if ':wifi:' in line and not ':wifi-p2p:' in line:
                parts = line.split(':')
                dev = parts[0]
                if not dev.startswith("p2p-"):
                    wifi_devices.append(dev)
    return wifi_devices

def check_ap_mode_support(iface):
    """Check if interface supports AP (Access Point) mode using iw."""
    try:
        output = subprocess.run(['iw', 'list'], capture_output=True, text=True, timeout=5)
        if output.returncode != 0:
            return True, "Could not verify AP support (iw command failed)"
        
        # Parse iw list output to find interface capabilities
        in_supported_modes = False
        for line in output.stdout.splitlines():
            if 'Supported interface modes:' in line:
                in_supported_modes = True
                continue
            if in_supported_modes:
                if line.strip().startswith('*'):
                    if 'AP' in line:
                        return True, None
                else:
                    in_supported_modes = False
        
        return False, f"Interface {iface} does not support AP (Access Point) mode"
    except Exception as e:
        return True, f"Could not verify AP support: {e}"

def check_5ghz_support():
    """Check if any WiFi card supports 5GHz band."""
    try:
        output = subprocess.run(['iw', 'list'], capture_output=True, text=True, timeout=5)
        if output.returncode != 0:
            return True, "Could not verify 5GHz support"
        
        # Look for 5 GHz frequencies (5180 MHz and above)
        if '5180' in output.stdout or '5240' in output.stdout or '5745' in output.stdout:
            return True, None
        return False, "Your Wi-Fi adapter does not support 5GHz band. Use 2.4GHz instead."
    except Exception as e:
        return True, f"Could not verify 5GHz support: {e}"

def check_rfkill_status(iface):
    """Check if WiFi is blocked by hardware or software RF kill switch."""
    try:
        # Check rfkill status
        result = subprocess.run(['rfkill', 'list', 'wifi'], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return True, None  # Can't check, assume OK
        
        output = result.stdout.lower()
        if 'hard blocked: yes' in output:
            return False, "Wi-Fi is HARDWARE BLOCKED. Check physical Wi-Fi switch on your laptop."
        if 'soft blocked: yes' in output:
            return False, "Wi-Fi is SOFTWARE BLOCKED. Run: sudo rfkill unblock wifi"
        return True, None
    except Exception as e:
        return True, None  # Can't check, proceed

def check_interface_state(iface):
    """Check interface operational state."""
    try:
        # Check if interface is UP
        result = subprocess.run(['ip', 'link', 'show', iface], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, f"Interface {iface} not found in system"
        
        if 'state DOWN' in result.stdout:
            return False, f"Interface {iface} is DOWN. It may be disabled or have driver issues."
        if 'NO-CARRIER' in result.stdout and 'state UP' not in result.stdout:
            return True, f"Interface {iface} has no carrier (normal for WiFi before connection)"
        return True, None
    except Exception as e:
        return True, None

STATUS_FILE = "/tmp/hotspot_status.json"

def write_status(status, message, is_error=False):
    """Write status to file for GUI to read and display notifications."""
    import json
    try:
        data = {
            "timestamp": time.time(),
            "status": status,
            "message": message,
            "is_error": is_error
        }
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

def check_interface_busy(iface):
    """Check if the interface is currently connected to a WiFi network."""
    try:
        output = run_command(['nmcli', '-t', '-f', 'DEVICE,STATE,CONNECTION', 'device'], check=False)
        if output:
            for line in output.splitlines():
                parts = line.split(':')
                if len(parts) >= 3 and parts[0] == iface:
                    state = parts[1]
                    connection = parts[2] if len(parts) > 2 else ""
                    if state == "connected" and connection and connection != CONNECTION_NAME:
                        return True, connection
        return False, None
    except:
        return False, None

def preflight_checks(interface=None, ssid=None, password=None, exclude_vpn=False, force_single_interface=False, band='bg'):
    """
    Comprehensive pre-flight validation before starting hotspot.
    Returns (success: bool, error_message: str, warnings: list)
    """
    errors = []
    warnings = []
    
    # 1. Check if NetworkManager is running
    try:
        result = subprocess.run(['systemctl', 'is-active', 'NetworkManager'], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            errors.append("NetworkManager is not running. Start it with: sudo systemctl start NetworkManager")
    except Exception as e:
        warnings.append(f"Could not verify NetworkManager status: {e}")
    
    # 2. Check RF kill status FIRST (hardware/software blocks)
    rfkill_ok, rfkill_error = check_rfkill_status(None)
    if not rfkill_ok:
        errors.append(rfkill_error)
        return False, "\n".join(errors), warnings
    
    # 3. Check for Wi-Fi interfaces
    wifi_interfaces = get_wifi_interfaces()
    if not wifi_interfaces:
        errors.append("No Wi-Fi interfaces found. Ensure your Wi-Fi adapter is connected and recognized.")
        return False, "\n".join(errors), warnings
    
    # 4. Determine which interface to use
    target_iface = interface
    if not target_iface:
        upstream = get_upstream_interface(exclude_vpn)
        # Smart selection: prefer interface NOT providing internet
        for dev in wifi_interfaces:
            if dev != upstream:
                target_iface = dev
                break
        if not target_iface:
            target_iface = wifi_interfaces[0]
    
    # 5. Check if interface exists
    if target_iface not in wifi_interfaces:
        errors.append(f"Interface '{target_iface}' not found. Available: {', '.join(wifi_interfaces)}")
        return False, "\n".join(errors), warnings
    
    # 6. Check interface operational state
    iface_ok, iface_error = check_interface_state(target_iface)
    if not iface_ok:
        errors.append(iface_error)
    elif iface_error:
        warnings.append(iface_error)
    
    # 7. Check AP mode support
    ap_supported, ap_error = check_ap_mode_support(target_iface)
    if not ap_supported:
        errors.append(ap_error)
    elif ap_error:
        warnings.append(ap_error)
    
    # 6. Check if interface is busy (connected to WiFi)
    is_busy, connection_name = check_interface_busy(target_iface)
    upstream = get_upstream_interface(exclude_vpn)
    
    # Check if we have an alternative internet source (Ethernet)
    has_ethernet_internet = False
    if upstream and not upstream.startswith(('wl', 'wlan')):
        # Upstream is Ethernet or similar (not WiFi)
        has_ethernet_internet = True
    
    if is_busy:
        if target_iface == upstream:
            # This WiFi interface is providing internet
            if len(wifi_interfaces) == 1 and not has_ethernet_internet:
                # CRITICAL: Single WiFi, no Ethernet = will lose all internet
                if force_single_interface:
                    warnings.append(
                        f"FORCED: Your only Wi-Fi interface ({target_iface}) will disconnect from '{connection_name}'. "
                        f"You will lose internet connectivity. Proceed with caution."
                    )
                else:
                    errors.append(
                        f"BLOCKED: Your only Wi-Fi interface ({target_iface}) is currently providing your internet connection via '{connection_name}'. "
                        f"Starting a hotspot will disconnect you completely with no way to recover remotely.\n"
                        f"Solutions:\n"
                        f"  1. Connect to the internet via Ethernet cable first\n"
                        f"  2. Add a second USB Wi-Fi adapter for the hotspot\n"
                        f"  3. Use --force-single-interface flag if you understand the risk"
                    )
            elif len(wifi_interfaces) == 1 and has_ethernet_internet:
                # Single WiFi but Ethernet is available - just warn
                warnings.append(
                    f"Your Wi-Fi ({target_iface}) will disconnect from '{connection_name}'. "
                    f"Internet will continue via Ethernet ({upstream})."
                )
            else:
                warnings.append(
                    f"Interface {target_iface} is connected to '{connection_name}'. It will be disconnected to start the hotspot."
                )
        else:
            warnings.append(
                f"Interface {target_iface} is connected to '{connection_name}'. It will be disconnected to start the hotspot."
            )
    
    # 9. Check for internet connectivity
    if not upstream:
        warnings.append(
            "No active internet connection detected. Hotspot clients will not have internet access unless you connect later."
        )
    
    # 10. Check 5GHz band support if selected
    if band == 'a':  # 5GHz
        ghz5_ok, ghz5_error = check_5ghz_support()
        if not ghz5_ok:
            errors.append(ghz5_error)
    
    # 8. Validate SSID
    if ssid:
        if len(ssid) < 1 or len(ssid) > 32:
            errors.append("SSID must be between 1 and 32 characters.")
        if any(ord(c) > 127 for c in ssid):
            warnings.append("SSID contains non-ASCII characters. Some devices may not display it correctly.")
    
    # 9. Validate password
    if password:
        if len(password) < 8:
            errors.append("Password must be at least 8 characters for WPA2 security.")
        elif len(password) > 63:
            errors.append("Password must not exceed 63 characters.")
    
    # 10. Check for conflicting hotspot processes
    try:
        result = subprocess.run(['pgrep', '-f', 'hotspot_backend.py'], capture_output=True, text=True)
        if result.stdout.strip():
            pids = [p for p in result.stdout.strip().split('\n') if p and int(p) != os.getpid()]
            if pids:
                warnings.append(f"Another hotspot backend may be running (PIDs: {', '.join(pids)}). It will be terminated.")
    except:
        pass
    
    # 11. Check for existing hotspot connection
    try:
        output = run_command(['nmcli', '-t', '-f', 'NAME', 'con', 'show'], check=False)
        if output and CONNECTION_NAME in output:
            pass  # Will be cleaned up, not an error
    except:
        pass
    
    if errors:
        return False, "\n".join(errors), warnings
    
    return True, None, warnings



def get_upstream_interface(exclude_vpn=False):
    """
    Finds the interface providing internet using kernel routing decision.
    """
    try:
        # standard mode: trust the kernel (includes VPN if active)
        if not exclude_vpn:
            output = run_command(['ip', 'route', 'get', '1.1.1.1'], check=False)
            # Output: 1.1.1.1 via 192.168.1.1 dev enp3s0 src ...
            if output:
                match = re.search(r'dev\s+(\S+)', output)
                if match:
                    return match.group(1)
            # Fallback for standard mode - still don't filter VPN
            output = run_command(['ip', '-4', 'route', 'show', 'default'], check=False)
            if output:
                for line in output.splitlines():
                    match = re.search(r'dev\s+(\S+)', line)
                    if match:
                        return match.group(1)
            return None
        
        # exclude_vpn mode: Manually hunt for physical default route
        output = run_command(['ip', '-4', 'route', 'show', 'default'], check=False)
        candidates = []
        if output:
            for line in output.splitlines():
                match = re.search(r'dev\s+(\S+)', line)
                if match: candidates.append(match.group(1))
        
        vpn_prefixes = ('tun', 'tap', 'wg', 'ppp')
        filtered = [dev for dev in candidates if not dev.startswith(vpn_prefixes)]
        
        if filtered: return filtered[0]
        if candidates: return candidates[0]
            
    except: pass
    return None

def get_smart_interface(exclude_vpn=False):
    """Selects the best available Wi-Fi interface, avoiding the upstream source."""
    wifi_devs = get_wifi_interfaces()
    if not wifi_devs: return None
    
    upstream = get_upstream_interface(exclude_vpn)
    print(f"Detected Upstream (Internet) Interface: {upstream}")
    
    candidates = []
    # prioritizing disconnected devices to avoid conflict
    for dev in wifi_devs:
        if dev != upstream:
            candidates.append(dev)
            
    if candidates:
        print(f"Smart Select: Chose {candidates[0]} (avoided {upstream})")
        return candidates[0]
    
    print(f"Warning: Only available Wi-Fi interface is the upstream source ({upstream}). Connection might drop.")
    return wifi_devs[0]

def count_connected_clients(iface):
    try:
        output = run_command(['iw', 'dev', iface, 'station', 'dump'], check=False)
        if output: return output.count("Station")
        return 0
    except: return 0

def update_firewall(hotspot_iface, upstream_iface):
    print(f"-> Routing update: Internet from {upstream_iface} -> Hotspot on {hotspot_iface}")

    run_command(['sysctl', '-w', 'net.ipv4.ip_forward=1'], check=False)
    run_command(['iptables', '-t', 'nat', '-F', 'POSTROUTING'], check=False)
    run_command(['iptables', '-F', 'FORWARD'], check=False)
    
    run_command([
        'iptables', '-t', 'nat', '-I', 'POSTROUTING', 
        '-o', upstream_iface, '-j', 'MASQUERADE'
    ], check=False)

    # Force Policy to ACCEPT (Fixes Docker/Firewalld interference)
    run_command(['iptables', '-P', 'FORWARD', 'ACCEPT'], check=False)

    run_command([
        'iptables', '-I', 'FORWARD', '1', 
        '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN', 
        '-j', 'TCPMSS', '--clamp-mss-to-pmtu'
    ], check=False)

    # Insert at TOP to override other rules
    run_command(['iptables', '-I', 'FORWARD', '1', '-m', 'state', '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'], check=False)
    run_command(['iptables', '-I', 'FORWARD', '1', '-i', upstream_iface, '-o', hotspot_iface, '-j', 'ACCEPT'], check=False)
    
    if MAC_MODE == "allow":
        run_command(['iptables', '-A', 'FORWARD', '-i', hotspot_iface, '-j', 'DROP'], check=False)
        for mac in MAC_LIST:
            run_command([
                'iptables', '-I', 'FORWARD', '1', 
                '-i', hotspot_iface, '-o', upstream_iface, 
                '-m', 'mac', '--mac-source', mac, '-j', 'ACCEPT'
            ], check=False)
        
    elif MAC_MODE == "block":
        # Allow main flow (inserted at 1, so before drops if any)
        run_command(['iptables', '-I', 'FORWARD', '1', '-i', hotspot_iface, '-o', upstream_iface, '-j', 'ACCEPT'], check=False)
        for mac in MAC_LIST:
            run_command([
                'iptables', '-I', 'FORWARD', '1', 
                '-i', hotspot_iface, '-o', upstream_iface, 
                '-m', 'mac', '--mac-source', mac, '-j', 'DROP'
            ], check=False)

def cleanup(signal_received=None, frame=None):
    print("\n\nStopping hotspot...")
    
    # 1. Clean Firewall (Aggressive)
    # We messed with FORWARD, so flush it or delete our rules. Flushing is safer for "Stop" state.
    # But flushing FORWARD might kill Docker/Other rules? 
    # Better: explicitly delete the rules we added. But simpler for user fixes: Flush specific rules.
    # Actually, let's just reverse the insertions.
    
    # Simple Reset:
    run_command(['iptables', '-t', 'nat', '-F', 'POSTROUTING'], check=False)
    # Flush FORWARD is risky if user has other stuff... 
    # But sticking to "Original File" simplicity: The original file didn't spam FORWARD insertions.
    # We should delete the rules matching our interfaces.
    
    # Generic delete attempt for our common rules
    run_command(['iptables', '-D', 'FORWARD', '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN', '-j', 'TCPMSS', '--clamp-mss-to-pmtu'], check=False)
    run_command(['iptables', '-D', 'FORWARD', '-m', 'state', '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'], check=False)
    
    # Reverting Connection
    run_command(['nmcli', 'con', 'delete', CONNECTION_NAME], check=False)
    
    # Kill PID file
    if os.path.exists(PID_FILE): os.remove(PID_FILE)
    sys.exit(0)

def main():
    global HOTSPOT_IFACE, CURRENT_UPSTREAM_IFACE, MAC_MODE, MAC_LIST, EXCLUDE_VPN
    
    if subprocess.call(["id", "-u"], stdout=subprocess.PIPE) != 0:
        print("Run with sudo.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description='Hotspot Backend Service')
    parser.add_argument('--interface', help='Wi-Fi interface')
    parser.add_argument('--ssid', default=DEFAULT_HOTSPOT_NAME)
    parser.add_argument('--password', default=DEFAULT_PASSWORD)
    parser.add_argument('--band', default='bg', choices=['bg', 'a'])
    parser.add_argument('--hidden', action='store_true')
    parser.add_argument('--dns', help='Custom DNS')
    parser.add_argument('--mac-mode', default="block", choices=["block", "allow"])
    parser.add_argument('--block', action='append')
    parser.add_argument('--allow', action='append')
    parser.add_argument('--auto-off', type=int, default=0)
    parser.add_argument('--exclude-vpn', action='store_true', help='Avoid routing through VPN interfaces')
    parser.add_argument('--force-single-interface', action='store_true', 
                        help='Force hotspot on single WiFi interface even if it will disconnect internet')
    parser.add_argument('--stop', action='store_true')
    
    args = parser.parse_args()

    if args.stop:
        print("Stopping hotspot...")
        
        # 1. Try to stop via PID file first
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                # Wait for process to actually terminate
                for _ in range(10):
                    try:
                        os.kill(pid, 0)  # Check if still alive
                        time.sleep(0.5)
                    except OSError:
                        break  # Process terminated
            except Exception as e:
                print(f"PID-based stop failed: {e}")
        
        # 2. Fallback: Kill any remaining backend processes (excluding ourselves)
        my_pid = os.getpid()
        try:
            result = subprocess.run(['pgrep', '-f', 'hotspot_backend.py'], 
                                    capture_output=True, text=True)
            if result.stdout:
                for pid_str in result.stdout.strip().split('\n'):
                    try:
                        pid = int(pid_str)
                        if pid != my_pid:
                            os.kill(pid, signal.SIGTERM)
                    except (ValueError, OSError):
                        pass
        except Exception:
            pass
        
        # 3. Always clean up the nmcli connection
        run_command(['nmcli', 'con', 'delete', CONNECTION_NAME], check=False)
        
        # 4. Clean up firewall rules
        run_command(['iptables', '-t', 'nat', '-F', 'POSTROUTING'], check=False)
        run_command(['iptables', '-D', 'FORWARD', '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN', '-j', 'TCPMSS', '--clamp-mss-to-pmtu'], check=False)
        run_command(['iptables', '-D', 'FORWARD', '-m', 'state', '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'], check=False)
        
        # 5. Remove PID file
        if os.path.exists(PID_FILE): os.remove(PID_FILE)
        
        print("Hotspot stopped.")
        sys.exit(0)
    
    MAC_MODE = args.mac_mode
    if MAC_MODE == "allow" and args.allow: MAC_LIST = args.allow
    elif MAC_MODE == "block" and args.block: MAC_LIST = args.block
    
    EXCLUDE_VPN = args.exclude_vpn

    # =============================================
    # PRE-FLIGHT VALIDATION
    # =============================================
    print("Running pre-flight checks...")
    success, error_msg, warnings_list = preflight_checks(
        interface=args.interface,
        ssid=args.ssid,
        password=args.password,
        exclude_vpn=EXCLUDE_VPN,
        force_single_interface=args.force_single_interface,
        band=args.band
    )
    
    # Print warnings (non-fatal)
    for warning in warnings_list:
        print(f"[!] {warning}")
    
    # If errors, abort with clear message and notify GUI
    if not success:
        print(f"\n[ERROR] Cannot start hotspot:\n{error_msg}")
        write_status("error", error_msg, is_error=True)
        sys.exit(1)
    
    print("Pre-flight checks passed.\n")

    with open(PID_FILE, 'w') as f: f.write(str(os.getpid()))
    signal.signal(signal.SIGINT, cleanup); signal.signal(signal.SIGTERM, cleanup)

    # SMART SELECTION LOGIC
    if args.interface: 
        HOTSPOT_IFACE = args.interface
    else:
        # Use new smart selector
        HOTSPOT_IFACE = get_smart_interface(EXCLUDE_VPN)
        if not HOTSPOT_IFACE:
            print("Error: No Wi-Fi interfaces found.")
            cleanup()
    
    print(f"Selected Hotspot Interface: {HOTSPOT_IFACE}")
    ensure_wifi_active(HOTSPOT_IFACE)
    run_command(['nmcli', 'device', 'disconnect', HOTSPOT_IFACE], check=False)
    run_command(['nmcli', 'con', 'delete', CONNECTION_NAME], check=False)


    try:
        print(f"Creating Hotspot '{args.ssid}'...")
        run_command([
            'nmcli', 'con', 'add', 'type', 'wifi', 'ifname', HOTSPOT_IFACE, 
            'con-name', CONNECTION_NAME, 'autoconnect', 'no', 
            'ssid', args.ssid, 'mode', 'ap', '802-11-wireless.band', args.band
        ])

        if args.hidden: run_command(['nmcli', 'con', 'modify', CONNECTION_NAME, '802-11-wireless.hidden', 'yes'])

        run_command(['nmcli', 'con', 'modify', CONNECTION_NAME, 'wifi-sec.key-mgmt', 'wpa-psk'])
        run_command(['nmcli', 'con', 'modify', CONNECTION_NAME, 'wifi-sec.psk', args.password])
        run_command(['nmcli', 'con', 'modify', CONNECTION_NAME, 'ipv4.method', 'shared'])
        
        if args.dns:
            run_command(['nmcli', 'con', 'modify', CONNECTION_NAME, 'ipv4.dns', args.dns])
            run_command(['nmcli', 'con', 'modify', CONNECTION_NAME, 'ipv4.ignore-auto-dns', 'yes'])

        print("Activating hotspot...")
        run_command(['nmcli', 'con', 'up', CONNECTION_NAME, 'ifname', HOTSPOT_IFACE])
        print(f"\nHotspot ACTIVE on {HOTSPOT_IFACE}")
        write_status("active", f"Hotspot '{args.ssid}' is now active on {HOTSPOT_IFACE}")
        print("Monitoring internet source...")

        idle_seconds = 0
        check_counter = 0
        while True:
            # Continually ensure we are using the correct upstream (changes if VPN connects/disconnects)
            # Check every iteration (1 second) for fast VPN switching response
            new_upstream = get_upstream_interface(EXCLUDE_VPN)
            
            if new_upstream and new_upstream != CURRENT_UPSTREAM_IFACE:
                if new_upstream != HOTSPOT_IFACE:
                    update_firewall(HOTSPOT_IFACE, new_upstream)
                    CURRENT_UPSTREAM_IFACE = new_upstream
            
            # Auto-off check: only check clients every 5 seconds to reduce overhead
            if args.auto_off > 0:
                check_counter += 1
                if check_counter >= 5:  # Every 5 seconds
                    check_counter = 0
                    clients = count_connected_clients(HOTSPOT_IFACE)
                    if clients == 0: 
                        idle_seconds += 5
                    else: 
                        idle_seconds = 0
                    if idle_seconds >= (args.auto_off * 60):  # Convert minutes to seconds
                        print("Auto-off trigger."); cleanup()

            time.sleep(1)  # Check every 1 second for faster VPN change detection

    except Exception as e:
        print(f"Error: {e}"); cleanup()

if __name__ == "__main__":
    main()
