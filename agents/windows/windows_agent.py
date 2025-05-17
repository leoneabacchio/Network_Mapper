#!/usr/bin/env python3
import socket
import time
import requests
import re
import subprocess
from datetime import datetime

# Use the WMI module for gateway discovery
import wmi

# ─────────────── CONFIG ───────────────
SERVER_URL = "http://localhost:5000/api/ingest"
INTERVAL   = 60  # seconds between posts
# ────────────────────────────────────────

def get_primary_ip():
    """Return the first non-loopback IPv4 address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

HOST_IP = get_primary_ip()

def collect_physical_neighbors():
    """
    Run `arp -a` and extract only real Layer-2 neighbors:
    """
    neighbors = []
    try:
        out = subprocess.check_output(
            ["arp", "-a"], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            m = re.match(r'\s*([\d\.]+)\s+([\da-fA-F\-]+)\s+\w+', line)
            if not m:
                continue
            ip, mac = m.groups()
            if mac.lower() == "ff-ff-ff-ff-ff-ff": continue
            if ip.startswith("224.") or ip.startswith("239.") or ip == "255.255.255.255": continue
            if ip == HOST_IP: continue
            neighbors.append(ip)
    except Exception:
        pass
    return neighbors

def get_default_gateway_wmi():
    """
    Use WMI to get the default gateway from Win32_NetworkAdapterConfiguration.
    """
    try:
        c = wmi.WMI()
        for nic in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
            gws = nic.DefaultIPGateway
            if gws:
                # DefaultIPGateway is a list; take the first
                return gws[0]
    except Exception:
        pass
    return None

if __name__ == "__main__":
    print(f"[{datetime.now().isoformat()}] Windows agent starting; posting every {INTERVAL}s as {HOST_IP}")

    while True:
        neighbors      = collect_physical_neighbors()
        default_gateway = get_default_gateway_wmi()

        payload = {
            "host": HOST_IP,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "neighbors": neighbors,
            "default_gateway": default_gateway
        }

        # Debug: print what we're sending
        print(f"[{datetime.now().isoformat()}] Payload:", payload)

        try:
            resp = requests.post(SERVER_URL, json=payload, timeout=10)
            resp.raise_for_status()
            print(f"[{datetime.now().isoformat()}] POST ok")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] ERROR posting: {e}")

        time.sleep(INTERVAL)
