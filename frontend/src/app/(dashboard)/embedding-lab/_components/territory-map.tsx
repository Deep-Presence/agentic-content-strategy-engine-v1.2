'use client';

import { useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';
import type { ClusterData, EngineKey } from './data';

interface TerritoryMapProps {
  clusters: ClusterData[];
  engineFilter: EngineKey | 'all';
  viewMode: 'citations' | 'market_share' | 'authority';
  onClusterSelect: (clusterId: string | null) => void;
  selectedCluster: string | null;
}

interface ClusterNode {
  cluster: ClusterData;
  r: number;
  x: number;
  y: number;
  index: number;
}


export function TerritoryMap({
  clusters,
  engineFilter,
  viewMode,
  onClusterSelect,
  selectedCluster,
}: TerritoryMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setDimensions({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Render D3
  useEffect(() => {
    const svg = d3.select(svgRef.current);
    if (!svgRef.current || dimensions.width < 100) return;

    svg.selectAll('*').remove();

    const { width, height } = dimensions;
    const padding = 50;
    const w = width - padding * 2;
    const h = height - padding * 2;

    // Root group with zoom
    const g = svg.append('g');
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 6])
      .on('zoom', (event) => g.attr('transform', event.transform));
    (svg as d3.Selection<SVGSVGElement, unknown, null, undefined>).call(zoom);

    // ── Layout clusters using force simulation ──
    const totalCitations = clusters.reduce((s, c) => s + c.citations, 0) || 1;
    const clusterNodes: ClusterNode[] = clusters.map((c, i) => {
      const sizeValue = viewMode === 'market_share' ? c.share : c.citations;
      const sizeRef = viewMode === 'market_share'
        ? clusters.reduce((s, cl) => s + cl.share, 0) || 1
        : totalCitations;
      const area = (Math.max(sizeValue, 1) / sizeRef) * w * h * 0.4;
      const r = Math.max(Math.sqrt(area / Math.PI), 40);
      return { cluster: c, r, x: padding + w / 2, y: padding + h / 2, index: i };
    });

    const sim = d3.forceSimulation(clusterNodes)
      .force('center', d3.forceCenter(padding + w / 2, padding + h / 2))
      .force('collision', d3.forceCollide<ClusterNode>((d) => d.r + 10).strength(0.9))
      .force('x', d3.forceX(padding + w / 2).strength(0.04))
      .force('y', d3.forceY(padding + h / 2).strength(0.04))
      .stop();
    for (let i = 0; i < 300; i++) sim.tick();

    // ── Defs ──
    const defs = g.append('defs');

    // Clip paths for logos
    let clipIdx = 0;

    // ── Render cluster circles ──
    const groups = g.selectAll('.cluster-g')
      .data(clusterNodes)
      .join('g')
      .attr('class', 'cluster-g')
      .attr('transform', (d) => `translate(${d.x},${d.y})`);

    // Cluster boundary circle
    groups.append('circle')
      .attr('r', (d) => d.r)
      .attr('fill', 'transparent')
      .attr('stroke', (d) => d.cluster.color)
      .attr('stroke-width', (d) => d.cluster.id === selectedCluster ? 2 : 1)
      .attr('stroke-opacity', (d) => {
        if (!selectedCluster) return 0.3;
        return d.cluster.id === selectedCluster ? 0.7 : 0.1;
      })
      .attr('cursor', 'pointer')
      .on('click', (_event, d) => {
        onClusterSelect(d.cluster.id === selectedCluster ? null : d.cluster.id);
      });

    // Cluster label (top)
    groups.append('text')
      .attr('y', (d) => -d.r - 12)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-primary)')
      .attr('font-family', 'var(--font-display)')
      .attr('font-size', (d) => Math.max(10, Math.min(12, d.r / 8)))
      .attr('font-weight', 500)
      .attr('opacity', (d) => {
        if (!selectedCluster) return 1;
        return d.cluster.id === selectedCluster ? 1 : 0.3;
      })
      .text((d) => d.cluster.name);

    // Cluster sub-label
    groups.append('text')
      .attr('y', (d) => -d.r - 1)
      .attr('text-anchor', 'middle')
      .attr('fill', (d) => d.cluster.yourCitations === 0 ? 'var(--error)' : 'var(--text-secondary)')
      .attr('font-family', 'var(--font-display)')
      .attr('font-size', 9)
      .attr('opacity', (d) => {
        if (!selectedCluster) return 1;
        return d.cluster.id === selectedCluster ? 1 : 0.3;
      })
      .text((d) => {
        if (d.cluster.yourCitations === 0) return `No presence · ${d.cluster.citations} cit.`;
        return `${d.cluster.yourShare.toFixed(1)}% share · ${d.cluster.citations} cit.`;
      });

    // ── Render brand logos inside clusters ──
    for (const cNode of clusterNodes) {
      const comps = cNode.cluster.competitors.slice(0, 8);
      if (!comps.length) continue;

      const maxCit = comps[0].citations;
      const angleStep = (2 * Math.PI) / comps.length;

      comps.forEach((comp, i) => {
        const sizeScale = Math.sqrt(comp.citations / Math.max(maxCit, 1));
        const logoSize = Math.max(14, Math.min(30, sizeScale * 30));
        const orbitR = cNode.r * 0.55 * (0.4 + sizeScale * 0.5);
        const angle = angleStep * i - Math.PI / 2;
        const lx = cNode.x + Math.cos(angle) * orbitR;
        const ly = cNode.y + Math.sin(angle) * orbitR;
        const isCompany = comp.domain === 'insighthealth.ai';

        const cid = `clip-${clipIdx++}`;
        defs.append('clipPath').attr('id', cid)
          .append('circle').attr('cx', lx).attr('cy', ly).attr('r', logoSize / 2);

        // Company glow ring
        if (isCompany) {
          g.append('circle')
            .attr('cx', lx).attr('cy', ly)
            .attr('r', logoSize / 2 + 4)
            .attr('fill', 'none')
            .attr('stroke', 'var(--accent)')
            .attr('stroke-width', 2)
            .attr('opacity', 0.6)
            .style('animation', 'pulse 3s ease-in-out infinite');
        }

        // Border circle
        const borderStyle = comp.type === 'mindshare'
          ? '4,3'
          : comp.type === 'authority'
          ? '2,2'
          : 'none';

        g.append('circle')
          .attr('cx', lx).attr('cy', ly)
          .attr('r', logoSize / 2)
          .attr('fill', viewMode === 'authority'
            ? getAuthorityFill(comp.domain)
            : 'var(--surface-raised)')
          .attr('stroke', isCompany ? 'var(--accent)' : 'var(--border)')
          .attr('stroke-width', isCompany ? 1.5 : 0.5)
          .attr('stroke-dasharray', borderStyle)
          .attr('opacity', () => {
            if (!selectedCluster) return 1;
            return cNode.cluster.id === selectedCluster ? 1 : 0.15;
          });

        // Favicon image
        g.append('image')
          .attr('x', lx - logoSize / 2)
          .attr('y', ly - logoSize / 2)
          .attr('width', logoSize)
          .attr('height', logoSize)
          .attr('href', `https://www.google.com/s2/favicons?domain=${comp.domain}&sz=64`)
          .attr('clip-path', `url(#${cid})`)
          .attr('cursor', 'pointer')
          .attr('opacity', () => {
            if (!selectedCluster) return 1;
            return cNode.cluster.id === selectedCluster ? 1 : 0.15;
          })
          .on('click', () => {
            onClusterSelect(cNode.cluster.id === selectedCluster ? null : cNode.cluster.id);
          })
          .append('title')
          .text(`${comp.domain} · ${comp.citations} citations · ${comp.share.toFixed(1)}% share`);
      });
    }
  }, [clusters, dimensions, engineFilter, viewMode, selectedCluster, onClusterSelect]);

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[500px]">
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="w-full h-full"
      />
      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex items-center gap-4 text-[10px] text-text-secondary font-display">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full border border-border-strong" />
          Direct
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full border border-border-strong" style={{ borderStyle: 'dashed' }} />
          Mind share
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full border border-border-strong" style={{ borderStyle: 'dotted' }} />
          Authority
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full border-2 border-accent" />
          Your brand
        </span>
      </div>
    </div>
  );
}

function getAuthorityFill(domain: string): string {
  if (domain.endsWith('.gov')) return 'rgba(66,133,244,0.12)';
  if (domain.endsWith('.edu')) return 'rgba(16,185,129,0.12)';
  if (domain.endsWith('.org')) return 'rgba(139,92,246,0.12)';
  return 'var(--surface-raised)';
}
