import React, { useEffect, useState, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function NetworkMap() {
  const [data, setData] = useState({ nodes: [], links: [] });
  const images = useRef({}); // will hold Image objects for pc, switch, router

  // 1) Preload the three icon images exactly once:
  useEffect(() => {
    const pcImg = new Image();
    pcImg.src = '/icons/pc.png';
    const switchImg = new Image();
    switchImg.src = '/icons/switch.png';
    const routerImg = new Image();
    routerImg.src = '/icons/router.png';

    // It’s okay if these load asynchronously—canvas will draw as soon as they’re ready.
    images.current = {
      pc: pcImg,
      switch: switchImg,
      router: routerImg
    };
  }, []);

  // 2) Fetch topology data from your collector:
  useEffect(() => {
    fetch('http://localhost:5000/api/topology')
      .then(r => r.json())
      .then(rawData => {
        // Build a set of valid node IDs so we can filter out any stale/missing links:
        const nodeIds = new Set(rawData.nodes.map((n) => n.id));
        const filteredLinks = rawData.links.filter(
          (l) => nodeIds.has(l.source) && nodeIds.has(l.target)
        );

        setData({
          nodes: rawData.nodes,
          links: filteredLinks
        });
      })
      .catch((err) => {
        console.error('Error fetching topology:', err);
      });
  }, []);

  // 3) Helper to pick the correct Image object based on node.type:
  const getIcon = (node) => {
    if (!images.current) return null;
    switch (node.type) {
      case 'router':
        return images.current.router;
      case 'switch':
        return images.current.switch;
      default:
        return images.current.pc;
    }
  };

  // 4) nodeCanvasObject callback draws the icon at each node’s (x,y):
  //    We also provide nodePointerAreaPaint so the cursor/hitbox matches the icon size.
  return (
    <div style={{ width: '100%', height: '100vh' }}>
      <ForceGraph2D
        graphData={data}
        backgroundColor="rgb(255, 255, 255)"
        // We no longer use nodeColor since we’re drawing images
        // nodeColor={...}
        linkColor={() => '#888'} // or any color you prefer for links

        // Draw the icon at the node’s position:
        nodeCanvasObject={(node, ctx, globalScale) => {
          const img = getIcon(node);
          if (!img) return; // in case it's not loaded yet

          // Determine icon size in pixels; you can tweak this:
          // We scale down if the graph is zoomed out, but keep a minimum size.
          const size = Math.max(12, 24 / globalScale);

          // x/y positions from force simulation:
          const x = node.x;
          const y = node.y;

          // Draw the image such that its center is at (x, y):
          ctx.drawImage(img, x - size / 2, y - size / 2, size, size);
        }}

        // Expand the clickable area to match the icon (not just the default circle).
        nodePointerAreaPaint={(node, color, ctx) => {
          const size = Math.max(12, 24 / (this ? this.scale : 1));
          const x = node.x;
          const y = node.y;
          ctx.fillStyle = color;
          ctx.fillRect(x - size / 2, y - size / 2, size, size);
        }}

        // Show a tooltip / label on hover:
        nodeLabel="label"

        // Optional: If you want to tweak link width, distance, etc., you can pass other props here.
      />
    </div>
  );
}
