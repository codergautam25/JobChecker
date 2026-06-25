"use client";

import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useState, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { MemoryInspectorPanel } from '@/components/MemoryInspectorPanel';
import { Database, Loader2 } from 'lucide-react';

// Dynamically import ForceGraph2D with SSR disabled since it uses HTML5 Canvas
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { 
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 bg-[#0b1120]">
      <Loader2 className="animate-spin mb-4" size={32} />
      <span>Initializing Neural Physics Engine...</span>
    </div>
  )
});

export default function MemoryGraph() {
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);


  // Fetch settings for Cache TTL
  const { data: settings } = useQuery({
    queryKey: ['settings', 'config'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/settings');
      return res.data;
    },
    staleTime: 60000
  });
  const cacheTtlMs = settings?.cache_ttl ? parseInt(settings.cache_ttl, 10) * 1000 : 60000;

  // Fetch Full Graph Data
  const { data: graphData, isLoading } = useQuery({
    queryKey: ['memory', 'graph'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/memory/graph');
      const graph = res.data.graph;
      
      // Calculate link counts
      graph.nodes.forEach((node: any) => {
        node.linkCount = graph.links.filter((l: any) => 
          (l.source.id || l.source) === node.id || 
          (l.target.id || l.target) === node.id
        ).length;
      });
      
      return graph;
    },
    staleTime: cacheTtlMs
  });

  // Configure edge lengths when graphData changes
  useEffect(() => {
    if (fgRef.current && graphData) {
      const linkForce = fgRef.current.d3Force('link');
      if (linkForce) {
        linkForce.distance(80);
      }
      const chargeForce = fgRef.current.d3Force('charge');
      if (chargeForce) {
        // If no links are present, use a gentler repulsion to keep nodes on screen
        const strength = graphData.links && graphData.links.length > 0 ? -400 : -100;
        chargeForce.strength(strength);
      }
      
      // Auto zoom to fit nodes on load
      setTimeout(() => {
        if (fgRef.current) {
          fgRef.current.zoomToFit(400, 50);
        }
      }, 500);
    }
  }, [graphData]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node);
    // Pan and zoom camera to the selected node
    if (fgRef.current) {
      fgRef.current.centerAt(node.x, node.y, 1000);
      fgRef.current.zoom(8, 2000);
    }
  }, []);

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null);
    if (fgRef.current) {
      fgRef.current.zoomToFit(400, 50);
    }
  }, []);

  // Custom node drawing to create glowing/cyberpunk effect
  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name;
    const fontSize = 12/globalScale;
    const nodeR = Math.max(Math.sqrt(node.val || 1) * 2, 3);
    const isSelected = selectedNode?.id === node.id;
    const baseColor = node.color || '#4f46e5';
    
    // Outer Aura (faint glow)
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeR + (isSelected ? 8 : 4), 0, 2 * Math.PI, false);
    ctx.fillStyle = isSelected ? 'rgba(255, 255, 255, 0.2)' : `rgba(${hexToRgb(baseColor)}, 0.15)`;
    ctx.fill();

    // Secondary Ring
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeR + (isSelected ? 4 : 1.5), 0, 2 * Math.PI, false);
    ctx.fillStyle = isSelected ? 'rgba(255, 255, 255, 0.5)' : `rgba(${hexToRgb(baseColor)}, 0.4)`;
    ctx.fill();

    // Inner Solid Core
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI, false);
    ctx.fillStyle = '#060b13'; // Match background
    ctx.fill();

    // Show link count in the middle instead of geometric crosshair
    const linkCountStr = (node.linkCount || 0).toString();
    const countFontSize = Math.max(nodeR * 0.7, 4); // Scale text to fit inside core
    ctx.font = `bold ${countFontSize}px monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = isSelected ? '#ffffff' : baseColor;
    
    // Only show number if node is big enough to be readable
    if (nodeR > 4) {
      ctx.fillText(linkCountStr, node.x, node.y);
    }

    // Node text (Label below)
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = isSelected ? '#ffffff' : '#94a3b8';
    
    // Only show text if zoomed in enough or if it's a big node
    if (globalScale > 2 || node.val > 8 || isSelected) {
      ctx.fillText(label, node.x, node.y + nodeR + fontSize + 4);
    }
  }, [selectedNode]);

  // Helper to convert hex to rgb string for rgba
  function hexToRgb(hex: string) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? 
      `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` 
      : '99, 102, 241';
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 h-[calc(100vh-8rem)] flex flex-col relative -mx-8 -my-8 overflow-hidden rounded-xl border border-slate-800">
      
      {/* HUD Header overlay */}
      <div className="absolute top-6 left-6 z-10 pointer-events-none">
        <h2 className="text-3xl font-light tracking-wide text-indigo-400 flex items-center gap-3 drop-shadow-[0_0_15px_rgba(99,102,241,0.5)]" style={{ fontFamily: 'Georgia, serif' }}>
          <Database className="text-indigo-500" />
          Neural Memory Network
        </h2>
        <p className="text-sm text-sky-200/60 mt-1 max-w-md backdrop-blur-sm bg-[#0b1120]/40 rounded-lg p-2 border border-slate-800/50">
          Interactive force-directed topology of the agent's contextual knowledge base. Scroll to zoom, drag nodes to manipulate physics.
        </p>
      </div>

      <div className="flex-1 flex w-full h-full relative bg-[#060b13]">
        
        {/* Animated Cyberpunk/Neural Aurora Background */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
          <style dangerouslySetInnerHTML={{__html: `
            @keyframes aurora1 {
              0% { transform: translate(0, 0) scale(1); }
              33% { transform: translate(5%, -5%) scale(1.1); }
              66% { transform: translate(-5%, 5%) scale(0.9); }
              100% { transform: translate(0, 0) scale(1); }
            }
            @keyframes aurora2 {
              0% { transform: translate(0, 0) scale(1); }
              33% { transform: translate(-5%, 5%) scale(0.9); }
              66% { transform: translate(5%, -5%) scale(1.1); }
              100% { transform: translate(0, 0) scale(1); }
            }
          `}} />
          
          {/* Base Grid */}
          <div className="absolute inset-0 opacity-[0.04] bg-[radial-gradient(#60a5fa_1px,transparent_1px)] [background-size:40px_40px] z-10"></div>
          
          {/* Glowing Neural Fog Orbs */}
          <div className="absolute -top-[20%] -left-[10%] w-[60vw] h-[60vh] rounded-full bg-indigo-600/20 blur-[120px]" style={{ animation: 'aurora1 20s infinite ease-in-out' }}></div>
          <div className="absolute top-[10%] -right-[10%] w-[50vw] h-[70vh] rounded-full bg-rose-600/15 blur-[120px]" style={{ animation: 'aurora2 25s infinite ease-in-out' }}></div>
          <div className="absolute -bottom-[20%] left-[15%] w-[70vw] h-[60vh] rounded-full bg-emerald-600/10 blur-[120px]" style={{ animation: 'aurora1 22s infinite ease-in-out 3s' }}></div>
          <div className="absolute top-[30%] left-[30%] w-[40vw] h-[40vh] rounded-full bg-sky-500/10 blur-[100px]" style={{ animation: 'aurora2 18s infinite ease-in-out 1s' }}></div>
        </div>
        
        {/* Force Graph Container */}
        <div ref={containerRef} className="absolute inset-0 z-10">
          {!isLoading && graphData && dimensions.width > 0 && (
            <ForceGraph2D
              ref={fgRef}
              width={dimensions.width}
              height={dimensions.height}
              graphData={graphData}
              nodeCanvasObject={paintNode}
              nodePointerAreaPaint={(node, color, ctx) => {
                ctx.fillStyle = color;
                const r = Math.max(Math.sqrt((node as any).val || 1) * 2, 3) + 4; // click area
                ctx.beginPath();
                ctx.arc(node.x as number, node.y as number, r, 0, 2 * Math.PI, false);
                ctx.fill();
              }}
              linkColor={() => 'rgba(51, 65, 85, 0.6)'}
              linkWidth={(link: any) => selectedNode && (link.source.id === selectedNode.id || link.target.id === selectedNode.id) ? 3 : 1}
              linkDirectionalParticles={(link: any) => selectedNode && (link.source.id === selectedNode.id || link.target.id === selectedNode.id) ? 6 : 2}
              linkDirectionalParticleWidth={(link: any) => selectedNode && (link.source.id === selectedNode.id || link.target.id === selectedNode.id) ? 3 : 1.5}
              linkDirectionalParticleSpeed={0.005}
              linkDirectionalParticleColor={() => '#60a5fa'}
              onNodeClick={handleNodeClick}
              onBackgroundClick={handleBackgroundClick}
              cooldownTicks={100}
              d3AlphaDecay={0.02}
              d3VelocityDecay={0.3}
              warmupTicks={50}
              minZoom={0.5}
              maxZoom={12}
            />
          )}
        </div>

        {/* Data Inspector Popup Modal */}
        {selectedNode && (
          <div className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-[#0b1120]/60 backdrop-blur-sm transition-opacity">
            <MemoryInspectorPanel 
              node={selectedNode} 
              onClose={() => setSelectedNode(null)} 
            />
          </div>
        )}

      </div>
    </div>
  );
}
