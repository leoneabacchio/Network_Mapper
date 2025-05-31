#!/usr/bin/env python3
import socket
import time
import subprocess
import requests
import re
import ipaddress
from datetime import datetime
import netifaces

# ─────────────── CONFIG ───────────────
SERVER_URL = "http://localhost:5000/api/ingest"
INTERVAL   = 60  # seconds between posts
# ────────────────────────────────────────

def get_primary_interface():
    """
    Returns the default network interface used for outgoing traffic.
    """
    try:
        gws = netifaces.gateways()
        default_iface = gws['default'][netifaces.AF_INET][1]
        return default_iface
    except Exception:
        return None

def get_network_info():
    """
    Returns a tuple: (IP address, subnet CIDR, gateway IP)
    """
    iface = get_primary_interface()
    if not iface:
        return None, None, None

    try:
        iface_data = netifaces.ifaddresses(iface)
        inet_data = iface_data[netifaces.AF_INET][0]
        ip_addr = inet_data['addr']
        netmask = inet_data['netmask']
        cidr = ipaddress.IPv4Network(f"{ip_addr}/{netmask}", strict=False).with_prefixlen

        gws = netifaces.gateways()
        gateway = gws['default'][netifaces.AF_INET][0]

        return ip_addr, cidr, gateway
    except Exception:
        return None, None, None

def get_arp_neighbors(local_cidr, host_ip):
    """
    Uses 'ip neigh' or 'arp -n' to find neighbors in the same subnet.
    """
    neighbors = []
    try:
        out = subprocess.check_output(["ip", "neigh"], text=True)
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                ip_str, state = parts[0], parts[4]
                try:
                    ip = ipaddress.IPv4Address(ip_str)
                    if ip == ipaddress.IPv4Address(host_ip):
                        continue
                    if ip not in ipaddress.IPv4Network(local_cidr, strict=False):
                        continue
                    neighbors.append(str(ip))
                except ValueError:
                    continue
    except Exception:
        pass
    return neighbors

if __name__ == "__main__":
    host_ip, subnet_str, gateway_ip = get_network_info()

    if not host_ip or not subnet_str:
        print(f"[{datetime.now().isoformat()}] Failed to determine local network configuration.")
        exit(1)

    print(f"[{datetime.now().isoformat()}] Linux agent starting with IP: {host_ip}, Subnet: {subnet_str}, Gateway: {gateway_ip}")

    while True:
        neighbors = get_arp_neighbors(subnet_str, host_ip)

        payload = {
            "host":            host_ip,
            "timestamp":       datetime.utcnow().isoformat() + "Z",
            "subnet":          subnet_str,
            "neighbors":       neighbors,
            "default_gateway": gateway_ip
        }

        print(f"[{datetime.now().isoformat()}] Payload: {payload}")

        try:
            resp = requests.post(SERVER_URL, json=payload, timeout=10)
            resp.raise_for_status()
            print(f"[{datetime.now().isoformat()}] POST ok")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] ERROR posting: {e}")

        time.sleep(INTERVAL)
