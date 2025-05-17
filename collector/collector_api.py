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

data_store: list[dict] = []

@app.post('/api/ingest')
async def ingest(request: Request):
    p = await request.json()
    p['received_at'] = datetime.utcnow().isoformat() + 'Z'
    data_store.append(p)
    return {'status': 'ok'}

@app.get('/api/topology')
async def topology():
    nodes_map: dict[str, dict] = {}
    links: list[tuple[str, str]] = []

    # 1) Make sure every host is in nodes_map as a PC
    for e in data_store:
        host_ip = e.get("host")
        if not host_ip:
            continue
        nodes_map[host_ip] = {"id": host_ip, "label": host_ip, "type": "pc"}

    # 2) Now process each payload for gateway + neighbors
    for e in data_store:
        host_ip = e["host"]
        gw = e.get("default_gateway")
        if gw:
            # overwrite or create gateway entry as router
            nodes_map[gw] = {"id": gw, "label": gw, "type": "router"}
            links.append((host_ip, gw))

        for neigh in e.get("neighbors", []):
            # if this neighbor isn’t already the gateway (router), add if missing
            if neigh not in nodes_map:
                nodes_map[neigh] = {"id": neigh, "label": neigh, "type": "unknown"}
            links.append((host_ip, neigh))

    # 3) Build lists
    nodes = list(nodes_map.values())
    links_fmt = [{"source": s, "target": t} for s, t in links]

    return {"nodes": nodes, "links": links_fmt}

if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=5000)
