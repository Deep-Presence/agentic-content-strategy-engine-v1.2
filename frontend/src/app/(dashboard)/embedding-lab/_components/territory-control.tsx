'use client';

import { useRef, useEffect, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { BrandLogo } from './brand-logo';
import { GapBadge } from './gap-badge';
import { ShareOfVoiceBar } from './share-of-voice-bar';
import { useThemeColors } from './use-theme-colors';
import type { ClusterData, GapSummaryResponse, BrandPresence } from './embedding-lab-data';

// ─── Types ──────────────────────────────────────────────────────────────────

interface ClusterNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  queryCount: number;
  avgGap: number;
  gapClassification: ClusterData['gapClassification'];
  brands: BrandPresence[];
  radius: number;
}

interface BrandNode extends d3.SimulationNodeDatum {
  domain: string;
  citationCount: number;
  avgSimilarity: number;
  isCompany: boolean;
  radius: number;
  clusterId: string;
}

interface RenderedBrand {
  domain: string;
  isCompany: boolean;
  cx: number; // absolute x in viewBox coords
  cy: number; // absolute y in viewBox coords
  radius: number;
  clusterId: string;
}

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  cluster: ClusterNode | null;
}

interface TerritoryControlProps {
  clusters: ClusterData[];
  summary: GapSummaryResponse;
  onClusterClick: (clusterId: string) => void;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const VB_WIDTH = 920;
const VB_HEIGHT = 580;

// Gap severity → stroke style
function getGapStroke(classification: string, c: ReturnType<typeof useThemeColors>) {
  switch (classification) {
    case 'critical': return { color: c.error, dasharray: '6,3', glow: true, glowColor: c.error };
    case 'warning': return { color: c.warning, dasharray: 'none', glow: false, glowColor: '' };
    case 'moderate': return { color: c.textTertiary, dasharray: 'none', glow: false, glowColor: '' };
    case 'strong': return { color: c.success, dasharray: 'none', glow: true, glowColor: c.success };
    default: return { color: c.border, dasharray: 'none', glow: false, glowColor: '' };
  }
}

// ─── Component ──────────────────────────────────────────────────────────────

export function TerritoryControl({ clusters, summary, onClusterClick }: TerritoryControlProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const colors = useThemeColors();
  const [hoveredClusterId, setHoveredClusterId] = useState<string | null>(null);
  const [brandPositions, setBrandPositions] = useState<RenderedBrand[]>([]);
  const [tooltip, setTooltip] = useState<TooltipState>({ visible: false, x: 0, y: 0, cluster: null });
  const clickRef = useRef(onClusterClick);
  clickRef.current = onClusterClick;

  // Build cluster nodes
  const clusterNodes: ClusterNode[] = useMemo(() => {
    const maxQ = Math.max(...clusters.map(c => c.queryCount));
    return clusters.map(c => ({
      id: c.id,
      name: c.name,
      queryCount: c.queryCount,
      avgGap: c.avgGap,
      gapClassification: c.gapClassification,
      brands: c.brands,
      radius: 52 + (c.queryCount / maxQ) * 58,
    }));
  }, [clusters]);

  // D3 force simulation — draws SVG shapes, computes brand positions
  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const svg = d3.select(svgEl);
    svg.selectAll('*').remove();

    const width = VB_WIDTH;
    const height = VB_HEIGHT;

    // ─── Defs: gradients + filters ────────────────────────────────────
    const defs = svg.append('defs');

    // Radial gradient for each cluster fill
    clusterNodes.forEach(cn => {
      const grad = defs.append('radialGradient')
        .attr('id', `fill-${cn.id}`)
        .attr('cx', '45%').attr('cy', '40%').attr('r', '65%');
      grad.append('stop')
        .attr('offset', '0%')
        .attr('stop-color', colors.surfaceRaised)
        .attr('stop-opacity', 0.6);
      grad.append('stop')
        .attr('offset', '100%')
        .attr('stop-color', colors.surface)
        .attr('stop-opacity', 0.35);
    });

    // Glow filter for critical/strong borders
    ['error', 'success'].forEach(name => {
      const glowColor = name === 'error' ? colors.error : colors.success;
      const filter = defs.append('filter')
        .attr('id', `glow-${name}`)
        .attr('x', '-30%').attr('y', '-30%')
        .attr('width', '160%').attr('height', '160%');
      filter.append('feGaussianBlur')
        .attr('in', 'SourceGraphic')
        .attr('stdDeviation', 3)
        .attr('result', 'blur');
      filter.append('feColorMatrix')
        .attr('in', 'blur')
        .attr('type', 'matrix')
        .attr('values', `0 0 0 0 ${parseInt(glowColor.slice(1, 3), 16) / 255} 0 0 0 0 ${parseInt(glowColor.slice(3, 5), 16) / 255} 0 0 0 0 ${parseInt(glowColor.slice(5, 7), 16) / 255} 0 0 0 0.35 0`)
        .attr('result', 'colorBlur');
      filter.append('feMerge')
        .selectAll('feMergeNode')
        .data(['colorBlur', 'SourceGraphic'])
        .enter()
        .append('feMergeNode')
        .attr('in', d => d);
    });

    const g = svg.append('g');

    // Clone and simulate
    const nodes: ClusterNode[] = clusterNodes.map(d => ({ ...d }));

    const sim = d3.forceSimulation(nodes)
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('collide', d3.forceCollide<ClusterNode>(d => d.radius + 16).strength(0.85))
      .force('x', d3.forceX(width / 2).strength(0.04))
      .force('y', d3.forceY(height / 2).strength(0.04));

    sim.stop();
    for (let i = 0; i < 300; i++) sim.tick();

    // ─── Draw clusters ────────────────────────────────────────────────
    const allBrands: RenderedBrand[] = [];

    const clusterGroups = g.selectAll<SVGGElement, ClusterNode>('g.cluster')
      .data(nodes, d => d.id)
      .enter()
      .append('g')
      .attr('class', 'cluster')
      .style('cursor', 'pointer');

    // Set initial state and stagger in
    clusterGroups
      .attr('transform', d => `translate(${d.x ?? width / 2},${d.y ?? height / 2}) scale(0.8)`)
      .style('opacity', 0);

    clusterGroups.transition()
      .delay((_d, idx) => idx * 90)
      .duration(400)
      .ease(d3.easeCubicOut)
      .style('opacity', 1)
      .attr('transform', d => `translate(${d.x ?? width / 2},${d.y ?? height / 2}) scale(1)`);

    clusterGroups.each(function (d) {
      const group = d3.select(this);
      const stroke = getGapStroke(d.gapClassification, colors);

      // ── Organic border path ─────────────────────────────────────────
      const nPts = 16;
      const jitter = d.radius * 0.04;
      const edgePoints: [number, number][] = [];
      for (let i = 0; i < nPts; i++) {
        const angle = (2 * Math.PI * i) / nPts;
        const r = d.radius + (Math.random() - 0.5) * jitter * 2;
        edgePoints.push([Math.cos(angle) * r, Math.sin(angle) * r]);
      }

      const lineGen = d3.line<[number, number]>()
        .x(p => p[0]).y(p => p[1])
        .curve(d3.curveBasisClosed);

      // Cluster fill with radial gradient
      group.append('path')
        .attr('d', lineGen(edgePoints))
        .attr('fill', `url(#fill-${d.id})`)
        .attr('stroke', stroke.color)
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', stroke.dasharray)
        .attr('filter', stroke.glow ? `url(#glow-${d.gapClassification === 'critical' ? 'error' : 'success'})` : null);

      // ── Labels ABOVE the circle ─────────────────────────────────────
      group.append('text')
        .attr('y', -d.radius - 14)
        .attr('text-anchor', 'middle')
        .attr('fill', colors.textPrimary)
        .attr('font-size', '11px')
        .attr('font-weight', 500)
        .attr('font-family', "'Space Grotesk', sans-serif")
        .text(d.name);

      group.append('text')
        .attr('y', -d.radius - 3)
        .attr('text-anchor', 'middle')
        .attr('fill', colors.textTertiary)
        .attr('font-size', '9px')
        .attr('font-weight', 400)
        .attr('font-family', "'JetBrains Mono', monospace")
        .attr('letter-spacing', '0.04em')
        .text(`${d.queryCount} queries`);

      // ── Brand logos: compute positions via inner force ───────────────
      const topBrands = d.brands.slice(0, 7);
      const maxCit = Math.max(...topBrands.map(tb => tb.citationCount));
      const logoMaxR = Math.min(d.radius * 0.28, 20);

      const brandNodes: BrandNode[] = topBrands.map((b, i) => ({
        domain: b.domain,
        citationCount: b.citationCount,
        avgSimilarity: b.avgSimilarity,
        isCompany: b.isCompany,
        radius: i === 0 ? logoMaxR : 6 + (b.citationCount / maxCit) * (logoMaxR * 0.7 - 6),
        clusterId: d.id,
      }));

      const innerSim = d3.forceSimulation(brandNodes)
        .force('center', d3.forceCenter(0, 4))
        .force('collide', d3.forceCollide<BrandNode>(bn => bn.radius + 2.5).strength(0.9))
        .force('radial', d3.forceRadial<BrandNode>(
          (bn) => bn.isCompany ? 0 : d.radius * 0.35,
          0, 4
        ).strength(0.4))
        .stop();

      for (let t = 0; t < 120; t++) innerSim.tick();

      brandNodes.forEach(bn => {
        allBrands.push({
          domain: bn.domain,
          isCompany: bn.isCompany,
          cx: (d.x ?? 0) + (bn.x ?? 0),
          cy: (d.y ?? 0) + (bn.y ?? 0),
          radius: bn.radius,
          clusterId: d.id,
        });
      });
    });

    setBrandPositions(allBrands);

    // ─── Hover interactions ─────────────────────────────────────────────
    clusterGroups
      .on('mouseenter', function (event, d) {
        setHoveredClusterId(d.id);

        clusterGroups.transition().duration(200)
          .style('opacity', (n: ClusterNode) => n.id === d.id ? 1 : 0.2);

        // Brighten hovered cluster border
        d3.select(this).select('path')
          .transition().duration(200)
          .attr('stroke-width', 2.5);

        const rect = svgEl.getBoundingClientRect();
        const scaleX = rect.width / VB_WIDTH;
        const scaleY = rect.height / VB_HEIGHT;
        setTooltip({
          visible: true,
          x: rect.left + (d.x ?? 0) * scaleX,
          y: rect.top + ((d.y ?? 0) - d.radius) * scaleY - 12,
          cluster: d,
        });
      })
      .on('mouseleave', function () {
        setHoveredClusterId(null);
        clusterGroups.transition().duration(200).style('opacity', 1);
        d3.select(this).select('path')
          .transition().duration(200)
          .attr('stroke-width', 1.5);
        setTooltip(prev => ({ ...prev, visible: false }));
      })
      .on('click', function (_, d) {
        clickRef.current(d.id);
      });

    return () => { sim.stop(); };
  }, [clusterNodes, colors]);

  // Compute viewBox-to-pixel scale for logo overlay
  const [containerRect, setContainerRect] = useState<DOMRect | null>(null);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => setContainerRect(el.getBoundingClientRect());
    measure();
    const obs = new ResizeObserver(measure);
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const svgScale = containerRect
    ? { x: containerRect.width / VB_WIDTH, y: containerRect.height / VB_HEIGHT }
    : { x: 1, y: 1 };

  return (
    <div className="space-y-3">
      <ShareOfVoiceBar summary={summary} />

      <div
        ref={containerRef}
        className="relative bg-bg border border-border rounded-md overflow-hidden"
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${VB_WIDTH} ${VB_HEIGHT}`}
          preserveAspectRatio="xMidYMid meet"
          className="w-full"
          style={{ display: 'block', minHeight: 420 }}
        />

        {/* Brand logos as React overlay */}
        {containerRect && brandPositions.map((b, i) => {
          const px = b.cx * svgScale.x;
          const py = b.cy * svgScale.y;
          const pr = b.radius * Math.min(svgScale.x, svgScale.y);
          const logoSize = Math.round(pr * 1.6);
          const isHidden = hoveredClusterId !== null && hoveredClusterId !== b.clusterId;

          return (
            <div
              key={`${b.clusterId}-${b.domain}-${i}`}
              className="absolute pointer-events-none transition-opacity duration-200"
              style={{
                left: px - logoSize / 2,
                top: py - logoSize / 2,
                width: logoSize,
                height: logoSize,
                opacity: isHidden ? 0.15 : 1,
              }}
            >
              <BrandLogo
                domain={b.domain}
                size={logoSize}
                isCompany={b.isCompany}
              />
            </div>
          );
        })}

        {/* Tooltip */}
        {tooltip.visible && tooltip.cluster && (
          <div
            className="fixed z-50 pointer-events-none"
            style={{
              left: tooltip.x,
              top: tooltip.y,
              transform: 'translate(-50%, -100%)',
            }}
          >
            <div className="bg-surface-raised border border-border rounded-md p-3 min-w-[220px] shadow-float">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[13px] font-medium text-text-primary">
                  {tooltip.cluster.name}
                </span>
                <GapBadge classification={tooltip.cluster.gapClassification} />
              </div>
              <div className="space-y-1.5">
                {tooltip.cluster.brands.slice(0, 5).map(b => (
                  <div key={b.domain} className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-2">
                      <BrandLogo domain={b.domain} size={16} isCompany={b.isCompany} />
                      <span className={b.isCompany ? 'text-accent font-medium' : 'text-text-secondary'}>
                        {b.domain}
                      </span>
                    </div>
                    <span className="text-text-tertiary font-mono text-[10px]">
                      {b.citationCount} cit
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="absolute bottom-3 right-3 bg-surface border border-border rounded-md p-2.5 text-[10px]">
          <div className="text-text-tertiary font-medium uppercase tracking-[0.06em] mb-2">
            Gap Severity
          </div>
          {([
            { key: 'critical', label: 'Critical', color: colors.error, dash: true },
            { key: 'warning', label: 'Warning', color: colors.warning, dash: false },
            { key: 'moderate', label: 'Moderate', color: colors.textTertiary, dash: false },
            { key: 'strong', label: 'Strong', color: colors.success, dash: false },
          ]).map(g => (
            <div key={g.key} className="flex items-center gap-2 mb-1">
              <svg width="16" height="8">
                <line
                  x1="0" y1="4" x2="16" y2="4"
                  stroke={g.color}
                  strokeWidth="2"
                  strokeDasharray={g.dash ? '4,2' : 'none'}
                />
              </svg>
              <span className="text-text-secondary">{g.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
