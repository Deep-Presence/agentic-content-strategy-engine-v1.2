'use client';

import { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import { X } from 'lucide-react';
import {
  CLUSTERS,
  GAP_QUERIES,
  CLUSTER_COLORS,
  type ClusterProfile,
  type GapQuery,
  type GapExemplar,
} from './data';
import { BrandLogo } from './brand-logo';

// ── Types ──────────────────────────────────────────────────

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  nodeType: 'cluster' | 'query' | 'domain';
  label: string;
  clusterId: string;
  r: number;
  color: string;
  data: ClusterProfile | GapQuery | DomainData;
}

interface GraphEdge extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  type: 'cluster-query' | 'query-domain' | 'mindshare';
  similarity?: number;
}

interface DomainData {
  domain: string;
  citations: number;
  isCompany: boolean;
  clusters: { clusterId: string; clusterName: string; citations: number }[];
  authorityType: string | null;
}

// ── Component ──────────────────────────────────────────────

export function KnowledgeGraph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 900, height: 600 });
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: GraphNode } | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Filter state
  const [clusterFilter, setClusterFilter] = useState<string>('all');
  const [showClusterQuery, setShowClusterQuery] = useState(true);
  const [showQueryDomain, setShowQueryDomain] = useState(true);
  const [showMindShare, setShowMindShare] = useState(true);

  // ── Build graph data ────────────────────────────────────

  const { graphNodes, graphEdges, domainMap } = useMemo(() => {
    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];

    // 1. Cluster nodes
    for (const c of CLUSTERS) {
      nodes.push({
        id: `cluster-${c.id}`,
        nodeType: 'cluster',
        label: c.name,
        clusterId: c.id,
        r: 28,
        color: c.color,
        data: c,
      });
    }

    // 2. Query nodes (top 3 per cluster by gap descending)
    const queryNodes: GraphNode[] = [];
    for (const c of CLUSTERS) {
      const clusterGaps = GAP_QUERIES
        .filter((g) => g.clusterId === c.id)
        .sort((a, b) => b.gap - a.gap)
        .slice(0, 3);
      for (const g of clusterGaps) {
        const qNode: GraphNode = {
          id: `query-${g.id}`,
          nodeType: 'query',
          label: g.query.length > 50 ? g.query.slice(0, 50) + '...' : g.query,
          clusterId: c.id,
          r: 6,
          color: c.color,
          data: g,
        };
        queryNodes.push(qNode);
      }
    }
    nodes.push(...queryNodes);

    // 3. Domain nodes (top 5 per cluster, deduplicated)
    const dMap = new Map<string, DomainData>();
    for (const c of CLUSTERS) {
      for (const d of c.topDomains.slice(0, 5)) {
        if (!dMap.has(d.domain)) {
          dMap.set(d.domain, {
            domain: d.domain,
            citations: d.citations,
            isCompany: d.isCompany,
            clusters: [{ clusterId: c.id, clusterName: c.name, citations: d.citations }],
            authorityType: d.type,
          });
        } else {
          const existing = dMap.get(d.domain)!;
          existing.citations += d.citations;
          existing.clusters.push({ clusterId: c.id, clusterName: c.name, citations: d.citations });
        }
      }
    }
    dMap.forEach((dData, domain) => {
      nodes.push({
        id: `domain-${domain}`,
        nodeType: 'domain',
        label: domain,
        clusterId: dData.clusters[0].clusterId,
        r: 14,
        color: '#888',
        data: dData,
      });
    });

    // 4. Cluster -> Query edges
    for (const q of queryNodes) {
      edges.push({
        source: `cluster-${q.clusterId}`,
        target: q.id,
        type: 'cluster-query',
      });
    }

    // 5. Query -> Domain edges (from exemplars)
    for (const q of queryNodes) {
      const gap = q.data as GapQuery;
      for (const ex of gap.exemplars || []) {
        if (dMap.has(ex.domain)) {
          edges.push({
            source: q.id,
            target: `domain-${ex.domain}`,
            type: 'query-domain',
            similarity: ex.similarity,
          });
        }
      }
    }

    // 6. Domain <-> Domain (mind share: domains sharing a query's exemplars)
    const mindshareSet = new Set<string>();
    for (const q of queryNodes) {
      const gap = q.data as GapQuery;
      const domains = (gap.exemplars || [])
        .map((e: GapExemplar) => e.domain)
        .filter((d: string) => dMap.has(d));
      for (let i = 0; i < domains.length; i++) {
        for (let j = i + 1; j < domains.length; j++) {
          const edgeId = [domains[i], domains[j]].sort().join('|');
          if (!mindshareSet.has(edgeId)) {
            mindshareSet.add(edgeId);
            edges.push({
              source: `domain-${domains[i]}`,
              target: `domain-${domains[j]}`,
              type: 'mindshare',
            });
          }
        }
      }
    }

    return { graphNodes: nodes, graphEdges: edges, domainMap: dMap };
  }, []);

  // ── Filter nodes and edges ──────────────────────────────

  const { filteredNodes, filteredEdges } = useMemo(() => {
    let fNodes = graphNodes;
    let fEdges = graphEdges;

    if (clusterFilter !== 'all') {
      // Keep the selected cluster, its queries, and connected domains
      const clusterQueryIds = new Set(
        fNodes
          .filter((n) => n.nodeType === 'query' && n.clusterId === clusterFilter)
          .map((n) => n.id)
      );

      // Find connected domain IDs
      const connectedDomainIds = new Set<string>();
      for (const e of fEdges) {
        const src = typeof e.source === 'string' ? e.source : e.source.id;
        const tgt = typeof e.target === 'string' ? e.target : e.target.id;
        if (clusterQueryIds.has(src) && tgt.startsWith('domain-')) connectedDomainIds.add(tgt);
        if (clusterQueryIds.has(tgt) && src.startsWith('domain-')) connectedDomainIds.add(src);
      }

      const validNodeIds = new Set<string>([`cluster-${clusterFilter}`]);
      clusterQueryIds.forEach((id) => validNodeIds.add(id));
      connectedDomainIds.forEach((id) => validNodeIds.add(id));

      fNodes = fNodes.filter((n) => validNodeIds.has(n.id));
      fEdges = fEdges.filter((e) => {
        const src = typeof e.source === 'string' ? e.source : e.source.id;
        const tgt = typeof e.target === 'string' ? e.target : e.target.id;
        return validNodeIds.has(src) && validNodeIds.has(tgt);
      });
    }

    // Filter edge types
    fEdges = fEdges.filter((e) => {
      if (e.type === 'cluster-query' && !showClusterQuery) return false;
      if (e.type === 'query-domain' && !showQueryDomain) return false;
      if (e.type === 'mindshare' && !showMindShare) return false;
      return true;
    });

    return { filteredNodes: fNodes, filteredEdges: fEdges };
  }, [graphNodes, graphEdges, clusterFilter, showClusterQuery, showQueryDomain, showMindShare]);

  // ── Counts for legend ───────────────────────────────────

  const nodeCounts = useMemo(() => {
    let clusters = 0, queries = 0, domains = 0;
    for (const n of filteredNodes) {
      if (n.nodeType === 'cluster') clusters++;
      else if (n.nodeType === 'query') queries++;
      else domains++;
    }
    return { clusters, queries, domains };
  }, [filteredNodes]);

  // ── ResizeObserver ──────────────────────────────────────

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

  // ── D3 Render ───────────────────────────────────────────

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    if (!svgRef.current || dimensions.width < 100) return;

    svg.selectAll('*').remove();

    const { width, height } = dimensions;

    // Deep-clone nodes to avoid mutating useMemo cache
    const simNodes: GraphNode[] = filteredNodes.map((n) => ({ ...n }));
    const nodeById = new Map(simNodes.map((n) => [n.id, n]));

    // Build sim edges with resolved references
    const simEdges: GraphEdge[] = [];
    for (const e of filteredEdges) {
      const srcId = typeof e.source === 'string' ? e.source : e.source.id;
      const tgtId = typeof e.target === 'string' ? e.target : e.target.id;
      const srcNode = nodeById.get(srcId);
      const tgtNode = nodeById.get(tgtId);
      if (srcNode && tgtNode) {
        simEdges.push({ ...e, source: srcNode, target: tgtNode });
      }
    }

    // ── Force Simulation ────────────────────────────────
    const simulation = d3.forceSimulation(simNodes)
      .force(
        'link',
        d3.forceLink<GraphNode, GraphEdge>(simEdges)
          .id((d) => d.id)
          .distance((d) => {
            if (d.type === 'cluster-query') return 60;
            if (d.type === 'query-domain') return 100;
            return 150;
          })
          .strength(0.5)
      )
      .force(
        'charge',
        d3.forceManyBody<GraphNode>().strength((d) => {
          if (d.nodeType === 'cluster') return -400;
          if (d.nodeType === 'query') return -100;
          return -50;
        })
      )
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force(
        'collision',
        d3.forceCollide<GraphNode>().radius((d) => d.r + 5)
      )
      .force('x', d3.forceX(width / 2).strength(0.03))
      .force('y', d3.forceY(height / 2).strength(0.03))
      .stop();

    for (let i = 0; i < 300; i++) simulation.tick();

    // ── Root group with zoom ────────────────────────────
    const g = svg.append('g');
    const zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 5])
      .on('zoom', (event) => g.attr('transform', event.transform));
    (svg as d3.Selection<SVGSVGElement, unknown, null, undefined>).call(zoomBehavior);

    // ── Defs ────────────────────────────────────────────
    const defs = g.append('defs');

    // Clip paths for domain favicons
    for (const node of simNodes) {
      if (node.nodeType === 'domain') {
        defs.append('clipPath')
          .attr('id', `clip-${node.id.replace(/[^a-zA-Z0-9-]/g, '_')}`)
          .append('circle')
          .attr('cx', 0)
          .attr('cy', 0)
          .attr('r', node.r - 2);
      }
    }

    // ── Edges ───────────────────────────────────────────
    const edgeGroup = g.append('g').attr('class', 'edges');
    edgeGroup.selectAll('line')
      .data(simEdges)
      .join('line')
      .attr('x1', (d) => (d.source as GraphNode).x!)
      .attr('y1', (d) => (d.source as GraphNode).y!)
      .attr('x2', (d) => (d.target as GraphNode).x!)
      .attr('y2', (d) => (d.target as GraphNode).y!)
      .attr('stroke', (d) => {
        if (d.type === 'cluster-query') return 'var(--text-tertiary)';
        if (d.type === 'query-domain') {
          const src = d.source as GraphNode;
          return CLUSTER_COLORS[src.clusterId] || '#888';
        }
        return 'var(--text-tertiary)';
      })
      .attr('stroke-opacity', (d) => {
        if (d.type === 'cluster-query') return 0.15;
        if (d.type === 'query-domain') return 0.3;
        return 0.1;
      })
      .attr('stroke-width', (d) => {
        if (d.type === 'query-domain' && d.similarity) {
          return 0.5 + d.similarity * 1.5;
        }
        return d.type === 'mindshare' ? 0.5 : 1;
      })
      .attr('stroke-dasharray', (d) => d.type === 'mindshare' ? '4,3' : 'none')
      .attr('data-source', (d) => (d.source as GraphNode).id)
      .attr('data-target', (d) => (d.target as GraphNode).id)
      .attr('data-edge-type', (d) => d.type);

    // ── Domain nodes ────────────────────────────────────
    const domainGroup = g.append('g').attr('class', 'domain-nodes');
    const domainNodes = simNodes.filter((n) => n.nodeType === 'domain');

    const domainGs = domainGroup.selectAll('g.domain')
      .data(domainNodes)
      .join('g')
      .attr('class', 'domain')
      .attr('transform', (d) => `translate(${d.x},${d.y})`)
      .attr('cursor', 'pointer');

    // Background circle
    domainGs.append('circle')
      .attr('r', (d) => d.r)
      .attr('fill', 'var(--surface)')
      .attr('stroke', (d) => {
        const dd = d.data as DomainData;
        return dd.isCompany ? 'var(--accent)' : 'var(--border)';
      })
      .attr('stroke-width', (d) => {
        const dd = d.data as DomainData;
        return dd.isCompany ? 2 : 1;
      });

    // Company accent ring
    domainGs.filter((d) => (d.data as DomainData).isCompany)
      .append('circle')
      .attr('r', (d) => d.r + 3)
      .attr('fill', 'none')
      .attr('stroke', 'var(--accent)')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.4);

    // Favicon image
    domainGs.append('image')
      .attr('x', (d) => -(d.r - 2))
      .attr('y', (d) => -(d.r - 2))
      .attr('width', (d) => (d.r - 2) * 2)
      .attr('height', (d) => (d.r - 2) * 2)
      .attr('href', (d) => {
        const dd = d.data as DomainData;
        return `https://www.google.com/s2/favicons?domain=${dd.domain}&sz=64`;
      })
      .attr('clip-path', (d) => `url(#clip-${d.id.replace(/[^a-zA-Z0-9-]/g, '_')})`);

    // Domain label (hidden by default, shown on zoom/hover via CSS)
    domainGs.append('text')
      .attr('y', (d) => d.r + 12)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-secondary)')
      .attr('font-family', 'var(--font-display)')
      .attr('font-size', 9)
      .attr('class', 'domain-label')
      .attr('opacity', 0)
      .text((d) => (d.data as DomainData).domain);

    // ── Query nodes ─────────────────────────────────────
    const queryGroup = g.append('g').attr('class', 'query-nodes');
    const queryNodesData = simNodes.filter((n) => n.nodeType === 'query');

    const queryGs = queryGroup.selectAll('g.query')
      .data(queryNodesData)
      .join('g')
      .attr('class', 'query')
      .attr('transform', (d) => `translate(${d.x},${d.y})`)
      .attr('cursor', 'pointer');

    queryGs.append('circle')
      .attr('r', (d) => d.r)
      .attr('fill', (d) => {
        const c = CLUSTER_COLORS[d.clusterId] || '#888';
        return hexToRgba(c, 0.6);
      })
      .attr('stroke', (d) => CLUSTER_COLORS[d.clusterId] || '#888')
      .attr('stroke-width', 1);

    // ── Cluster nodes ───────────────────────────────────
    const clusterGroup = g.append('g').attr('class', 'cluster-nodes');
    const clusterNodesData = simNodes.filter((n) => n.nodeType === 'cluster');

    const clusterGs = clusterGroup.selectAll('g.cluster')
      .data(clusterNodesData)
      .join('g')
      .attr('class', 'cluster')
      .attr('transform', (d) => `translate(${d.x},${d.y})`)
      .attr('cursor', 'pointer');

    clusterGs.append('circle')
      .attr('r', (d) => d.r)
      .attr('fill', (d) => hexToRgba(d.color, 0.2))
      .attr('stroke', (d) => d.color)
      .attr('stroke-width', 2);

    clusterGs.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', 'var(--text-primary)')
      .attr('font-family', 'var(--font-display)')
      .attr('font-size', 11)
      .attr('font-weight', 600)
      .text((d) => {
        const name = d.label;
        return name.length > 14 ? name.slice(0, 12) + '..' : name;
      });

    // ── Interactions: hover highlighting ────────────────

    function getConnectedIds(nodeId: string): Set<string> {
      const connected = new Set<string>();
      connected.add(nodeId);
      for (const e of simEdges) {
        const srcId = (e.source as GraphNode).id;
        const tgtId = (e.target as GraphNode).id;
        if (srcId === nodeId) connected.add(tgtId);
        if (tgtId === nodeId) connected.add(srcId);
      }
      return connected;
    }

    function handleNodeHover(event: MouseEvent, d: GraphNode) {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setTooltip({
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        node: d,
      });

      const connected = getConnectedIds(d.id);

      // Fade non-connected nodes
      g.selectAll('.cluster-nodes g.cluster')
        .transition().duration(150)
        .attr('opacity', (n: unknown) => connected.has((n as GraphNode).id) ? 1 : 0.15);
      g.selectAll('.query-nodes g.query')
        .transition().duration(150)
        .attr('opacity', (n: unknown) => connected.has((n as GraphNode).id) ? 1 : 0.15);
      g.selectAll('.domain-nodes g.domain')
        .transition().duration(150)
        .attr('opacity', (n: unknown) => connected.has((n as GraphNode).id) ? 1 : 0.15);

      // Highlight connected edges
      edgeGroup.selectAll('line')
        .transition().duration(150)
        .attr('stroke-opacity', (e: unknown) => {
          const edge = e as GraphEdge;
          const srcId = (edge.source as GraphNode).id;
          const tgtId = (edge.target as GraphNode).id;
          if (srcId === d.id || tgtId === d.id) return 0.6;
          return 0.03;
        })
        .attr('stroke-width', (e: unknown) => {
          const edge = e as GraphEdge;
          const srcId = (edge.source as GraphNode).id;
          const tgtId = (edge.target as GraphNode).id;
          if (srcId === d.id || tgtId === d.id) return 2;
          if (edge.type === 'query-domain' && edge.similarity) return 0.5 + edge.similarity * 1.5;
          return edge.type === 'mindshare' ? 0.5 : 1;
        });

      // Show domain labels for connected domains
      g.selectAll<SVGTextElement, GraphNode>('.domain-label')
        .transition().duration(150)
        .attr('opacity', function () {
          const parent = (this as SVGTextElement).parentNode;
          if (!parent) return 0;
          const parentData = d3.select<Element, GraphNode>(parent as Element).datum();
          return connected.has(parentData.id) ? 1 : 0;
        });
    }

    function handleNodeLeave() {
      setTooltip(null);

      // Reset all opacities
      g.selectAll('.cluster-nodes g.cluster')
        .transition().duration(150)
        .attr('opacity', 1);
      g.selectAll('.query-nodes g.query')
        .transition().duration(150)
        .attr('opacity', 1);
      g.selectAll('.domain-nodes g.domain')
        .transition().duration(150)
        .attr('opacity', 1);

      edgeGroup.selectAll('line')
        .transition().duration(150)
        .attr('stroke-opacity', (e: unknown) => {
          const edge = e as GraphEdge;
          if (edge.type === 'cluster-query') return 0.15;
          if (edge.type === 'query-domain') return 0.3;
          return 0.1;
        })
        .attr('stroke-width', (e: unknown) => {
          const edge = e as GraphEdge;
          if (edge.type === 'query-domain' && edge.similarity) return 0.5 + edge.similarity * 1.5;
          return edge.type === 'mindshare' ? 0.5 : 1;
        });

      g.selectAll('.domain-label')
        .transition().duration(150)
        .attr('opacity', 0);
    }

    function handleNodeClick(_event: MouseEvent, d: GraphNode) {
      setSelectedNode(d);
    }

    // Attach events
    clusterGs
      .on('mouseenter', handleNodeHover as unknown as null)
      .on('mousemove', (event: unknown) => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        const e = event as MouseEvent;
        setTooltip((prev) => prev ? { ...prev, x: e.clientX - rect.left, y: e.clientY - rect.top } : null);
      })
      .on('mouseleave', handleNodeLeave)
      .on('click', handleNodeClick as unknown as null);

    queryGs
      .on('mouseenter', handleNodeHover as unknown as null)
      .on('mousemove', (event: unknown) => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        const e = event as MouseEvent;
        setTooltip((prev) => prev ? { ...prev, x: e.clientX - rect.left, y: e.clientY - rect.top } : null);
      })
      .on('mouseleave', handleNodeLeave)
      .on('click', handleNodeClick as unknown as null);

    domainGs
      .on('mouseenter', handleNodeHover as unknown as null)
      .on('mousemove', (event: unknown) => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        const e = event as MouseEvent;
        setTooltip((prev) => prev ? { ...prev, x: e.clientX - rect.left, y: e.clientY - rect.top } : null);
      })
      .on('mouseleave', handleNodeLeave)
      .on('click', handleNodeClick as unknown as null);

    return () => {
      simulation.stop();
    };
  }, [filteredNodes, filteredEdges, dimensions]);

  // ── Tooltip content ─────────────────────────────────────

  const renderTooltip = useCallback((node: GraphNode) => {
    if (node.nodeType === 'cluster') {
      const c = node.data as ClusterProfile;
      return (
        <div className="bg-[var(--surface-raised)] border border-[var(--border)] rounded-md p-3 shadow-[var(--shadow-float)] w-[220px]">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: c.color }} />
            <span className="text-[13px] font-semibold text-[var(--text-primary)] font-display">{c.name}</span>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
            <span className="text-[var(--text-tertiary)]">Citations</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{c.totalCitations}</span>
            <span className="text-[var(--text-tertiary)]">Domains</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{c.uniqueDomains}</span>
            <span className="text-[var(--text-tertiary)]">Queries</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{c.queryCount}</span>
            <span className="text-[var(--text-tertiary)]">Your share</span>
            <span className="font-mono text-right" style={{ color: c.companyShare > 0 ? 'var(--success)' : 'var(--error)' }}>
              {c.companyShare > 0 ? `${c.companyShare.toFixed(1)}%` : 'None'}
            </span>
          </div>
        </div>
      );
    }

    if (node.nodeType === 'query') {
      const g = node.data as GapQuery;
      return (
        <div className="bg-[var(--surface-raised)] border border-[var(--border)] rounded-md p-3 shadow-[var(--shadow-float)] w-[260px]">
          <p className="text-[12px] text-[var(--text-primary)] mb-2 leading-[1.4]">{g.query}</p>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
            <span className="text-[var(--text-tertiary)]">Gap</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{(g.gap * 100).toFixed(1)}%</span>
            <span className="text-[var(--text-tertiary)]">Classification</span>
            <span className="text-[var(--text-primary)] text-right">{g.classification.replace(/_/g, ' ')}</span>
            <span className="text-[var(--text-tertiary)]">Cited</span>
            <span className="text-right" style={{ color: g.companyCited ? 'var(--success)' : 'var(--error)' }}>
              {g.companyCited ? 'Yes' : 'No'}
            </span>
          </div>
        </div>
      );
    }

    // Domain
    const dd = node.data as DomainData;
    return (
      <div className="bg-[var(--surface-raised)] border border-[var(--border)] rounded-md p-3 shadow-[var(--shadow-float)] w-[220px]">
        <div className="flex items-center gap-2 mb-2">
          <BrandLogo domain={dd.domain} size={16} />
          <span className="text-[12px] font-semibold text-[var(--text-primary)]">{dd.domain}</span>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
          <span className="text-[var(--text-tertiary)]">Total citations</span>
          <span className="font-mono text-[var(--text-primary)] text-right">{dd.citations}</span>
          <span className="text-[var(--text-tertiary)]">Clusters</span>
          <span className="font-mono text-[var(--text-primary)] text-right">{dd.clusters.length}</span>
          <span className="text-[var(--text-tertiary)]">Type</span>
          <span className="text-[var(--text-primary)] text-right">{dd.authorityType || 'direct'}</span>
        </div>
      </div>
    );
  }, []);

  // ── Side panel content ──────────────────────────────────

  const renderSidePanel = useCallback((node: GraphNode) => {
    if (node.nodeType === 'cluster') {
      const c = node.data as ClusterProfile;
      const clusterQueries = GAP_QUERIES
        .filter((q) => q.clusterId === c.id)
        .sort((a, b) => b.gap - a.gap)
        .slice(0, 8);
      return (
        <>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-3 h-3 rounded-full" style={{ background: c.color }} />
            <span className="text-[14px] font-semibold text-[var(--text-primary)] font-display">{c.name}</span>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] mt-3 mb-4">
            <span className="text-[var(--text-tertiary)]">Citations</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{c.totalCitations}</span>
            <span className="text-[var(--text-tertiary)]">Domains</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{c.uniqueDomains}</span>
            <span className="text-[var(--text-tertiary)]">Queries</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{c.queryCount}</span>
            <span className="text-[var(--text-tertiary)]">Your share</span>
            <span className="font-mono text-right" style={{ color: c.companyShare > 0 ? 'var(--success)' : 'var(--error)' }}>
              {c.companyShare > 0 ? `${c.companyShare.toFixed(1)}%` : 'No presence'}
            </span>
            <span className="text-[var(--text-tertiary)]">Presence</span>
            <span className="text-[var(--text-primary)] text-right capitalize">{c.presence}</span>
          </div>

          <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-tertiary)] mb-2">
            Top Domains
          </div>
          <div className="space-y-1.5 mb-4">
            {c.topDomains.slice(0, 5).map((d, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px]">
                <BrandLogo domain={d.domain} size={14} />
                <span className="text-[var(--text-secondary)] truncate flex-1">{d.domain}</span>
                <span className="font-mono text-[var(--text-tertiary)]">{d.citations}</span>
              </div>
            ))}
          </div>

          <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-tertiary)] mb-2">
            Queries
          </div>
          <div className="space-y-1">
            {clusterQueries.map((q) => (
              <div key={q.id} className="text-[11px] text-[var(--text-secondary)] py-1 border-b border-[var(--border)] last:border-0">
                <span className="block truncate">{q.query}</span>
                <span className="font-mono text-[10px]" style={{ color: q.companyCited ? 'var(--success)' : 'var(--error)' }}>
                  gap {(q.gap * 100).toFixed(0)}%
                  {q.companyCited ? ' · cited' : ' · not cited'}
                </span>
              </div>
            ))}
          </div>
        </>
      );
    }

    if (node.nodeType === 'domain') {
      const dd = node.data as DomainData;
      return (
        <>
          <div className="flex items-center gap-2 mb-3">
            <BrandLogo domain={dd.domain} size={20} />
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">{dd.domain}</span>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] mb-4">
            <span className="text-[var(--text-tertiary)]">Total citations</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{dd.citations}</span>
            <span className="text-[var(--text-tertiary)]">Clusters present</span>
            <span className="font-mono text-[var(--text-primary)] text-right">{dd.clusters.length}</span>
            <span className="text-[var(--text-tertiary)]">Type</span>
            <span className="text-[var(--text-primary)] text-right capitalize">{dd.authorityType || 'direct'}</span>
          </div>

          {dd.isCompany && (
            <div className="mb-3 px-2 py-1.5 rounded border border-[var(--accent)] bg-[var(--accent-subtle)] text-[11px] text-[var(--accent)]">
              Your brand domain
            </div>
          )}

          <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-tertiary)] mb-2">
            Cluster Presence
          </div>
          <div className="space-y-1.5">
            {dd.clusters.map((cl, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px]">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: CLUSTER_COLORS[cl.clusterId] || '#888' }} />
                <span className="text-[var(--text-secondary)] truncate flex-1">{cl.clusterName}</span>
                <span className="font-mono text-[var(--text-tertiary)]">{cl.citations} cit.</span>
              </div>
            ))}
          </div>
        </>
      );
    }

    // Query node
    const gq = node.data as GapQuery;
    return (
      <>
        <p className="text-[13px] text-[var(--text-primary)] leading-[1.5] mb-3">{gq.query}</p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] mb-4">
          <span className="text-[var(--text-tertiary)]">Gap score</span>
          <span className="font-mono text-[var(--text-primary)] text-right">{(gq.gap * 100).toFixed(1)}%</span>
          <span className="text-[var(--text-tertiary)]">Classification</span>
          <span className="text-[var(--text-primary)] text-right">
            <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${
              gq.classification === 'significant_gap'
                ? 'bg-red-100 text-red-700'
                : gq.classification === 'moderate_gap'
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-emerald-100 text-emerald-700'
            }`}>
              {gq.classification.replace(/_/g, ' ')}
            </span>
          </span>
          <span className="text-[var(--text-tertiary)]">Company cited</span>
          <span className="text-right" style={{ color: gq.companyCited ? 'var(--success)' : 'var(--error)' }}>
            {gq.companyCited ? 'Yes' : 'No'}
          </span>
          <span className="text-[var(--text-tertiary)]">Avg similarity</span>
          <span className="font-mono text-[var(--text-primary)] text-right">{gq.avgCitationSimilarity.toFixed(3)}</span>
        </div>

        {gq.exemplars.length > 0 && (
          <>
            <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-tertiary)] mb-2">
              Top Exemplars
            </div>
            <div className="space-y-1.5">
              {gq.exemplars.slice(0, 5).map((ex, i) => (
                <div key={i} className="flex items-center gap-2 text-[11px]">
                  <BrandLogo domain={ex.domain} size={14} />
                  <span className="text-[var(--text-secondary)] truncate flex-1">{ex.domain}</span>
                  <span className="font-mono text-[var(--text-tertiary)]">{(ex.similarity * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </>
        )}
      </>
    );
  }, []);

  return (
    <div className="space-y-3" style={{ animation: 'fadeIn 150ms ease-out' }}>
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Cluster filter */}
          <select
            value={clusterFilter}
            onChange={(e) => { setClusterFilter(e.target.value); setSelectedNode(null); }}
            className="h-[26px] px-2 text-[11px] border border-border rounded bg-surface text-text-primary cursor-pointer"
          >
            <option value="all">All Clusters</option>
            {CLUSTERS.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          {/* Edge type toggles */}
          <label className="flex items-center gap-1.5 text-[11px] text-text-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={showClusterQuery}
              onChange={(e) => setShowClusterQuery(e.target.checked)}
              className="w-3 h-3"
            />
            Cluster-Query
          </label>
          <label className="flex items-center gap-1.5 text-[11px] text-text-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={showQueryDomain}
              onChange={(e) => setShowQueryDomain(e.target.checked)}
              className="w-3 h-3"
            />
            Query-Domain
          </label>
          <label className="flex items-center gap-1.5 text-[11px] text-text-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={showMindShare}
              onChange={(e) => setShowMindShare(e.target.checked)}
              className="w-3 h-3"
            />
            Mind Share
          </label>
        </div>

        <div className="flex items-center gap-3 text-[10px] text-text-secondary">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-[var(--accent)]" />
            Cluster ({nodeCounts.clusters})
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-[var(--text-tertiary)]" />
            Query ({nodeCounts.queries})
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full border border-[var(--border)]" />
            Domain ({nodeCounts.domains})
          </span>
          <span className="font-mono text-text-tertiary">{filteredEdges.length} connections</span>
        </div>
      </div>

      {/* Graph container */}
      <div className="relative border border-border rounded-md overflow-hidden bg-surface" style={{ height: 'calc(100vh - 240px)', minHeight: 500 }}>
        <div
          ref={containerRef}
          className="w-full h-full"
          style={{ marginRight: selectedNode ? 280 : 0, transition: 'margin-right 200ms ease-out' }}
        >
          <svg
            ref={svgRef}
            width={dimensions.width}
            height={dimensions.height}
            className="w-full h-full"
          />
        </div>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute z-30 pointer-events-none"
            style={{ left: tooltip.x + 14, top: tooltip.y - 10 }}
          >
            {renderTooltip(tooltip.node)}
          </div>
        )}

        {/* Side panel */}
        {selectedNode && (
          <div
            className="absolute top-0 right-0 w-[280px] h-full border-l border-[var(--border)] bg-[var(--surface)] overflow-y-auto shadow-[var(--shadow-float)]"
            style={{ animation: 'slideInRight 200ms ease-out' }}
          >
            <div className="flex items-center justify-between p-3 border-b border-[var(--border)]">
              <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${
                selectedNode.nodeType === 'cluster'
                  ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
                  : selectedNode.nodeType === 'query'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-emerald-100 text-emerald-700'
              }`}>
                {selectedNode.nodeType}
              </span>
              <button
                onClick={() => setSelectedNode(null)}
                className="w-[24px] h-[24px] flex items-center justify-center rounded text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--accent-subtle)] transition-colors cursor-pointer"
              >
                <X size={14} />
              </button>
            </div>
            <div className="p-3">
              {renderSidePanel(selectedNode)}
            </div>
          </div>
        )}

        {/* Bottom legend */}
        <div className="absolute bottom-3 left-3 flex items-center gap-4 text-[10px] text-text-secondary font-display">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-5 h-0.5" style={{ background: 'var(--text-tertiary)', opacity: 0.3 }} />
            Cluster-Query
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-5 h-0.5" style={{ background: 'var(--accent)', opacity: 0.5 }} />
            Query-Domain
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-5 h-0.5 border-t border-dashed border-[var(--text-tertiary)]" />
            Mind Share
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-full border-2 border-accent" />
            Your brand
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
