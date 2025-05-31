# ~/network-mapper/collector/collector_api.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for all incoming payloads
data_store: list[dict] = []

@app.post('/api/ingest')
async def ingest(request: Request):
    p = await request.json()
    # Stamp when we received it
    p['received_at'] = datetime.utcnow().isoformat() + 'Z'
    data_store.append(p)
    return {'status': 'ok'}

@app.get('/api/topology')
async def topology():
    """
    Build a topology in which:
      - Each unique host IP is a PC node.
      - Each unique subnet string (e.g. "192.168.1.0/24") is a SWITCH node.
      - Each default gateway IP is a ROUTER node.
      - Every host → switch (its own subnet) link is added.
      - Every switch → router (default gateway) link is added.
    """
    nodes_map: dict[str, dict] = {}
    links: list[tuple[str, str]] = []

    # 1) Add all hosts as PC nodes
    for entry in data_store:
        host_ip = entry.get("host")
        if not host_ip:
            continue
        if host_ip not in nodes_map:
            nodes_map[host_ip] = {
                "id": host_ip,
                "label": host_ip,
                "type": "pc"
            }

    # 2) Identify all unique subnets, create SWITCH nodes
    #    and link each host to its subnet-switch
    seen_switch_links = set()   # to dedupe (host, switch) links
    for entry in data_store:
        host_ip = entry.get("host")
        subnet  = entry.get("subnet")
        if not host_ip or not subnet:
            continue

        # Create switch node if not exists
        if subnet not in nodes_map:
            nodes_map[subnet] = {
                "id": subnet,
                "label": subnet,
                "type": "switch"
            }

        # Link host → switch (once per host-subnet pair)
        key_hs = (host_ip, subnet)
        if key_hs not in seen_switch_links:
            links.append((host_ip, subnet))
            seen_switch_links.add(key_hs)

    # 3) For each unique subnet, find its gateway and link switch → gateway
    seen_switch_router_links = set()
    for entry in data_store:
        subnet         = entry.get("subnet")
        default_gateway = entry.get("default_gateway")
        if not subnet or not default_gateway:
            continue

        # Create router node if not exists
        if default_gateway not in nodes_map:
            nodes_map[default_gateway] = {
                "id": default_gateway,
                "label": default_gateway,
                "type": "router"
            }

        # Link switch → router (once per subnet-gateway pair)
        key_sr = (subnet, default_gateway)
        if key_sr not in seen_switch_router_links:
            links.append((subnet, default_gateway))
            seen_switch_router_links.add(key_sr)

    # 4) Build lists for JSON output
    nodes = list(nodes_map.values())
    links_fmt = [{"source": src, "target": dst} for src, dst in links]

    return {"nodes": nodes, "links": links_fmt}

if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=5000)
