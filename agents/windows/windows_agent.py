#!/usr/bin/env python3
import socket
import time
import requests
import re
import subprocess
from datetime import datetime
import wmi
import ipaddress

# ─────────────── CONFIG ───────────────
SERVER_URL = "http://localhost:5000/api/ingest"
INTERVAL   = 60  # seconds between posts
# ────────────────────────────────────────

def get_interface_network():
    """
    Use WMI to find the network (IPv4 address + mask) of the primary interface.
    Returns an IPv4Network object, or None on failure.
    """
    c = wmi.WMI()
    for nic in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
        addrs = nic.IPAddress or []
        subnets = nic.IPSubnet or []
        # Look for the one matching our chosen HOST_IP
        for ip, mask in zip(addrs, subnets):
            try:
                # build network
                net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                # pick the first non-loopback, non-APIPA
                if not net.network_address.is_loopback and not ip.startswith("169.254"):
                    return net
            except Exception:
                continue
    return None

def get_primary_ip():
    """
    Return the first non-loopback IPv4 address on the machine.
    This should match one of the addresses from get_interface_network().
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()

# Determine our network and IP once at startup
NET = get_interface_network()
HOST_IP = get_primary_ip()
if NET:
    print(f"[{datetime.now().isoformat()}] Detected network: {NET}, host IP: {HOST_IP}")
else:
    print(f"[{datetime.now().isoformat()}] Could not detect network; HOST_IP={HOST_IP}")

def collect_physical_neighbors():
    """
    Run `arp -a` and extract only those neighbors whose IP falls in our subnet.
    Skips broadcast/multicast and VMware MACs as before.
    """
    neighbors = []
    try:
        out = subprocess.check_output(["arp", "-a"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.match(r'\s*([\d\.]+)\s+([\da-fA-F\-]+)\s+\w+', line)
            if not m:
                continue
            ip_str, mac = m.groups()
            ip = ipaddress.IPv4Address(ip_str)
            mac = mac.lower()

            # Filter: only hosts in our NET
            if NET and ip not in NET:
                continue

            # Skip broadcast/multicast
            if mac == "ff-ff-ff-ff-ff-ff":       continue
            if ip.is_multicast or ip.is_reserved: continue
            # Skip VMware virtual MACs if you still want:
            # if any(mac.startswith(oui) for oui in VMWARE_OUIS): continue
            if ip_str == HOST_IP:                 continue

            neighbors.append(ip_str)
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
                return gws[0]
    except Exception:
        pass
    return None

if __name__ == "__main__":
    print(f"[{datetime.now().isoformat()}] Agent starting; posting every {INTERVAL}s")

    while True:
        neighbors       = collect_physical_neighbors()
        default_gateway = get_default_gateway_wmi()

        payload = {
            "host":            HOST_IP,
            "timestamp":       datetime.utcnow().isoformat() + "Z",
            "neighbors":       neighbors,
            "default_gateway": default_gateway
        }

        print(f"[{datetime.now().isoformat()}] Payload:", payload)

        try:
            resp = requests.post(SERVER_URL, json=payload, timeout=10)
            resp.raise_for_status()
            print(f"[{datetime.now().isoformat()}] POST ok")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] ERROR posting: {e}")

        time.sleep(INTERVAL)
