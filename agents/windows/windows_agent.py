# windows_agent.py (modified excerpt)

import socket
import time
import requests
from datetime import datetime
from pysnmp.hlapi import *
import ipaddress

SERVER_URL = "http://localhost:5000/api/ingest"
INTERVAL   = 60
SNMP_COMMUNITY = 'public'
SNMP_PORT = 161

# Already have get_primary_ip() and get_interface_network() from before
# We just add an SNMP helper:

def snmp_walk(target, oid, community=SNMP_COMMUNITY):
    """
    Generator over (oid, value) for the given base OID via SNMPv2c GETNEXT.
    """
    for (errorIndication,
         errorStatus,
         errorIndex,
         varBinds) in nextCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),      # v2c
            UdpTransportTarget((target, SNMP_PORT), timeout=1, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False
    ):
        if errorIndication or errorStatus:
            return
        for varBind in varBinds:
            yield varBind  # yields (ObjectIdentity, Value)

def collect_neighbors_snmp(host_ip, local_net):
    """
    Query Windows host's SNMP agent for its ARP table:
      - ipNetToMediaNetAddress => the IP of the entry
      - ipNetToMediaPhysAddress => the MAC of the entry
    Only return IPs that belong to our local_net (IPv4Network).
    """
    neighbors = []
    # Base OID for ipNetToMediaEntry:
    #   .1.3.6.1.2.1.4.22.1.2 = ipNetToMediaNetAddress
    #   .1.3.6.1.2.1.4.22.1.3 = ipNetToMediaPhysAddress
    #
    # The *.1 suffix in the OID will encode: [ifIndex].[IP‐address]
    #
    for varBind in snmp_walk(host_ip, '1.3.6.1.2.1.4.22.1.2'):
        # varBind = (ObjectIdentity('IP-MIB', 'ipNetToMediaNetAddress', idx1, idx2, idx3, idx4), IpAddressVal)
        oid, ip_value = varBind
        ip_str = str(ip_value)  # e.g. '192.168.1.5'
        ip_obj = ipaddress.IPv4Address(ip_str)

        # Skip if not in our local subnet:
        if local_net and ip_obj not in local_net:
            continue
        if ip_str == host_ip:  # skip ourselves
            continue

        # Optionally, if you need the MAC, do a second walk for .1.3.6.1.2.1.4.22.1.3
        mac_oid_prefix = oid[:oid.prettyPrint().rfind('.')+1] + '3'
        # e.g. if the netAddress OID was .1.3.6.1.2.1.4.22.1.2.<ifIndex>.<IPbytes>,
        # then PhysAddress is the same OID with '3' instead of '2', and same suffix.
        # But for topology purposes, you probably only need the IP.

        neighbors.append(ip_str)

    return neighbors

def get_default_gateway_snmp(host_ip):
    """
    Query ipRouteTable OIDs to find which route has destination 0.0.0.0/0,
    then return its nexthop (default gateway).
    """
    # OIDs in ipRouteTable:
    #   ipRouteDest  = .1.3.6.1.2.1.4.21.1.1
    #   ipRouteMask  = .1.3.6.1.2.1.4.21.1.11
    #   ipRouteNextHop = .1.3.6.1.2.1.4.21.1.7
    #
    default_gw = None
    for varBind in snmp_walk(host_ip, '1.3.6.1.2.1.4.21.1.1'):
        # varBind is (oid, IpAddressVal) where OID suffix encodes the route index
        oid_dest, dest_ip = varBind
        dest_str = str(dest_ip)  # e.g. '0.0.0.0' for default route
        if dest_str != '0.0.0.0':
            continue

        # Extract the same index suffix from oid_dest to query ipRouteNextHop (.1.3.6.1.2.1.4.21.1.7.<suffix>)
        suffix = oid_dest.prettyPrint().split('1.3.6.1.2.1.4.21.1.1.')[-1]
        nexthop_oid = f'1.3.6.1.2.1.4.21.1.7.{suffix}'
        for vb in snmp_walk(host_ip, nexthop_oid):
            _, gw_ip = vb
            default_gw = str(gw_ip)
            break
        if default_gw:
            break

    return default_gw

if __name__ == "__main__":
    host_ip = get_primary_ip()
    local_net = get_interface_network()  # returns IPv4Network
    print(f"Detected IP={host_ip}, NET={local_net.with_prefixlen}")

    while True:
        neighbors = collect_neighbors_snmp(host_ip, local_net)
        default_gateway = get_default_gateway_snmp(host_ip)
        payload = {
            "host":            host_ip,
            "timestamp":       datetime.utcnow().isoformat() + "Z",
            "subnet":          local_net.with_prefixlen,
            "neighbors":       neighbors,
            "default_gateway": default_gateway
        }
        try:
            resp = requests.post(SERVER_URL, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] SNMP POST failed: {e}")
        time.sleep(INTERVAL)
