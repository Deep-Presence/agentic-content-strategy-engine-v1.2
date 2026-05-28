'use client';

import { useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';
import type { ClusterProfile, EngineKey } from './data';

interface TerritoryMapProps {
  clusters: ClusterProfile[];
  engineFilter: EngineKey | 'all';
  viewMode: 'citations' | 'market_share' | 'authority';
  onClusterSelect: (clusterId: string | null) => void;
  selectedCluster: string | null;
}

interface ClusterNode {
  cluster: ClusterProfile;
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
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [tooltip, setTooltip] = useState<{ x: number; y: number; cluster: ClusterProfile } | null>(null);

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
    const padding = 30;
    const w = width - padding * 2;
    const h = height - padding * 2;

    // Root group with zoom
    const g = svg.append('g');
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 6])
      .on('zoom', (event) => g.attr('transform', event.transform));
    (svg as d3.Selection<SVGSVGElement, unknown, null, undefined>).call(zoom);

    // ── Sqrt scale for proportional circle sizing ──
    const minR = 45;
    const maxR = Math.min(w, h) * 0.25;

    const sizeValues = clusters.map((c) =>
      viewMode === 'market_share' ? c.companyShare : c.totalCitations
    );
    const maxSizeValue = Math.max(...sizeValues, 1);

    const sqrtScale = d3.scaleSqrt()
      .domain([0, maxSizeValue])
      .range([minR, maxR]);

    // ── Layout clusters using force simulation ──
    const clusterNodes: ClusterNode[] = clusters.map((c, i) => {
      const sizeValue = viewMode === 'market_share' ? c.companyShare : c.totalCitations;
      const r = sqrtScale(Math.max(sizeValue, 0.1));
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

    // Cluster boundary circle with health coding
    groups.append('circle')
      .attr('r', (d) => d.r)
      .attr('fill', (d) => {
        if (d.cluster.presence === 'none') return 'rgba(229,72,77,0.04)';
        if (d.cluster.presence === 'strong' || d.cluster.presence === 'moderate') {
          return d.cluster.color + '0F'; // ~6% opacity via hex alpha
        }
        return 'transparent';
      })
      .attr('stroke', (d) => {
        if (d.cluster.presence === 'none') return 'var(--error)';
        return d.cluster.color;
      })
      .attr('stroke-width', (d) => d.cluster.id === selectedCluster ? 2 : 1)
      .attr('stroke-dasharray', (d) => d.cluster.presence === 'none' ? '6,4' : 'none')
      .attr('stroke-opacity', (d) => {
        if (!selectedCluster) return d.cluster.presence === 'none' ? 0.5 : 0.3;
        return d.cluster.id === selectedCluster ? 0.7 : 0.1;
      })
      .attr('cursor', 'pointer')
      .on('mouseenter', (event, d) => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          cluster: d.cluster,
        });
      })
      .on('mousemove', (event) => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        setTooltip((prev) => prev ? {
          ...prev,
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
        } : null);
      })
      .on('mouseleave', () => setTooltip(null))
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
      .attr('fill', (d) => d.cluster.presence === 'none' ? 'var(--error)' : 'var(--text-secondary)')
      .attr('font-family', 'var(--font-display)')
      .attr('font-size', 9)
      .attr('opacity', (d) => {
        if (!selectedCluster) return 1;
        return d.cluster.id === selectedCluster ? 1 : 0.3;
      })
      .text((d) => {
        if (d.cluster.companyCitations === 0) return `No presence \u00b7 ${d.cluster.totalCitations} cit.`;
        return `${d.cluster.companyShare.toFixed(1)}% share \u00b7 ${d.cluster.totalCitations} cit.`;
      });

    // ── Render brand logos inside clusters ──
    for (const cNode of clusterNodes) {
      const domains = cNode.cluster.topDomains.slice(0, 10);
      if (!domains.length) continue;

      const maxCit = domains[0].citations;
      const angleStep = (2 * Math.PI) / domains.length;

      domains.forEach((dom, i) => {
        const sizeScale = Math.sqrt(dom.citations / Math.max(maxCit, 1));
        const logoSize = Math.max(14, Math.min(30, sizeScale * 30));
        const orbitR = cNode.r * 0.6 * (0.4 + sizeScale * 0.5);
        const angle = angleStep * i - Math.PI / 2;
        const lx = cNode.x + Math.cos(angle) * orbitR;
        const ly = cNode.y + Math.sin(angle) * orbitR;

        const cid = `clip-${clipIdx++}`;
        defs.append('clipPath').attr('id', cid)
          .append('circle').attr('cx', lx).attr('cy', ly).attr('r', logoSize / 2);

        // Company glow ring
        if (dom.isCompany) {
          g.append('circle')
            .attr('cx', lx).attr('cy', ly)
            .attr('r', logoSize / 2 + 4)
            .attr('fill', 'none')
            .attr('stroke', 'var(--accent)')
            .attr('stroke-width', 2)
            .attr('opacity', 0.6)
            .style('animation', 'pulse 3s ease-in-out infinite');
        }

        // Border style by domain type
        const borderStyle = dom.type === 'mindshare'
          ? '4,3'
          : dom.type === 'authority'
          ? '2,2'
          : 'none';

        g.append('circle')
          .attr('cx', lx).attr('cy', ly)
          .attr('r', logoSize / 2)
          .attr('fill', viewMode === 'authority'
            ? getAuthorityFill(dom.domain)
            : 'var(--surface-raised)')
          .attr('stroke', dom.isCompany ? 'var(--accent)' : 'var(--border)')
          .attr('stroke-width', dom.isCompany ? 1.5 : 0.5)
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
          .attr('href', `https://www.google.com/s2/favicons?domain=${dom.domain}&sz=64`)
          .attr('clip-path', `url(#${cid})`)
          .attr('cursor', 'pointer')
          .attr('opacity', () => {
            if (!selectedCluster) return 1;
            return cNode.cluster.id === selectedCluster ? 1 : 0.15;
          })
          .on('click', () => {
            onClusterSelect(cNode.cluster.id === selectedCluster ? null : cNode.cluster.id);
          });
      });
    }

    // Zoom to selected cluster
    if (selectedCluster) {
      const selectedNode = clusterNodes.find(n => n.cluster.id === selectedCluster);
      if (selectedNode) {
        const scale = 2.5;
        const tx = width / 2 - selectedNode.x * scale;
        const ty = height / 2 - selectedNode.y * scale;
        (svg as d3.Selection<SVGSVGElement, unknown, null, undefined>)
          .transition()
          .duration(600)
          .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
      }
    } else {
      // Reset zoom when deselected
      (svg as d3.Selection<SVGSVGElement, unknown, null, undefined>)
        .transition()
        .duration(400)
        .call(zoom.transform, d3.zoomIdentity);
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
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full border border-[var(--error)]" style={{ borderStyle: 'dashed' }} />
          No presence
        </span>
        {selectedCluster && (
          <button
            onClick={() => onClusterSelect(null)}
            className="ml-2 px-2 py-0.5 text-[10px] font-medium text-text-secondary hover:text-text-primary border border-border rounded transition-colors cursor-pointer"
          >
            Reset View
          </button>
        )}
      </div>

      {/* Rich hover tooltip */}
      {tooltip && (
        <div
          ref={tooltipRef}
          className="absolute z-30 pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          <div className="bg-[var(--surface-raised)] border border-[var(--border)] rounded-md p-3 shadow-[var(--shadow-float)] w-[220px]">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: tooltip.cluster.color }} />
              <span className="text-[13px] font-semibold text-[var(--text-primary)] font-display">{tooltip.cluster.name}</span>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
              <span className="text-[var(--text-tertiary)]">Citations</span>
              <span className="font-mono text-[var(--text-primary)] text-right">{tooltip.cluster.totalCitations}</span>
              <span className="text-[var(--text-tertiary)]">Your share</span>
              <span className="font-mono text-right" style={{ color: tooltip.cluster.companyShare > 0 ? 'var(--success)' : 'var(--error)' }}>
                {tooltip.cluster.companyShare > 0 ? `${tooltip.cluster.companyShare}%` : 'No presence'}
              </span>
              <span className="text-[var(--text-tertiary)]">Domains</span>
              <span className="font-mono text-[var(--text-primary)] text-right">{tooltip.cluster.uniqueDomains}</span>
              <span className="text-[var(--text-tertiary)]">Coverage</span>
              <span className="font-mono text-[var(--text-primary)] text-right">{tooltip.cluster.queryCount} queries</span>
            </div>
            {/* Top 3 domains mini-list */}
            <div className="mt-2 pt-2 border-t border-[var(--border)] space-y-1">
              {tooltip.cluster.topDomains.slice(0, 3).map((d, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px]">
                  <img src={`https://www.google.com/s2/favicons?domain=${d.domain}&sz=16`} width={10} height={10} className="rounded-sm" alt={d.domain} />
                  <span className="text-[var(--text-secondary)] truncate flex-1">{d.domain}</span>
                  <span className="font-mono text-[var(--text-tertiary)]">{d.citations}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function getAuthorityFill(domain: string): string {
  if (domain.endsWith('.gov')) return 'rgba(66,133,244,0.12)';
  if (domain.endsWith('.edu')) return 'rgba(16,185,129,0.12)';
  if (domain.endsWith('.org')) return 'rgba(139,92,246,0.12)';
  return 'var(--surface-raised)';
}
