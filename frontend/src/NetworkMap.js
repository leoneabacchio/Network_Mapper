import React, { useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function NetworkMap() {
  const [data, setData] = useState({ nodes: [], links: [] });

  useEffect(() => {
  fetch('http://localhost:5000/api/topology')
    .then(r => r.json())
    .then(rawData => {
      // build a Set of valid node IDs
      const nodeIds = new Set(rawData.nodes.map(n => n.id));

      // filter links so both source & target exist in nodeIds
      const filteredLinks = rawData.links.filter(
        l => nodeIds.has(l.source) && nodeIds.has(l.target)
      );

      setData({
        nodes: rawData.nodes,
        links: filteredLinks
      });
    })
    .catch(console.error);
}, []);


  return (
    <div style={{ height: '100%', width: '100%' }}>
      {/* ─────── Debug JSON ─────── */}
      <pre
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          margin: 8,
          padding: 8,
          maxHeight: '30vh',
          overflow: 'auto',
          background: 'rgba(0,0,0,0.5)',
          color: 'white',
          zIndex: 10
        }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>

      {/* ───── The graph ───── */}
      <ForceGraph2D
  graphData={data}
  backgroundColor="#222"
  nodeColor={node => {
  if (node.type === 'router') return 'orange';
  if (node.type === 'switch') return 'lightgreen';
  return 'lightblue';
}}
  linkColor={() => 'white'}
  nodeLabel="label"
/>
    </div>
  );
}
