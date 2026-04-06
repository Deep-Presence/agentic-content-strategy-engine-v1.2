/**
 * Process real pipeline data into optimized JSON for the Embedding Lab.
 *
 * Reads from: /Users/shashank/Documents/deep-embedding-lab-prototype/data/
 * Outputs to: public/data/
 *
 * Run: npx tsx scripts/process-embedding-data.ts
 */

import * as fs from 'fs';
import * as path from 'path';

const SOURCE = '/Users/shashank/Documents/deep-embedding-lab-prototype/data';
const OUTPUT = path.join(__dirname, '..', 'public', 'data');

// ── Cluster ID mapping ─────────────────────────────────────
const CLUSTER_ID_MAP: Record<string, string> = {
  'Mechanism': 'mechanism',
  'Boundary': 'boundary',
  'Category Comparison': 'category-comparison',
  'Decision Criteria': 'decision-criteria',
  'Definition': 'definition',
  'Problem/Awareness': 'problem-awareness',
  'Best-of/Consideration': 'best-of-consideration',
  'Branded Evaluation': 'branded-evaluation',
  'Feature Verification': 'feature-verification',
};

function mapClusterId(name: string): string {
  return CLUSTER_ID_MAP[name] || name.toLowerCase().replace(/[\/\s]+/g, '-');
}

// ── Process embedding projections ──────────────────────────
function processEmbeddings(method: 'umap' | 'tsne') {
  console.log(`Processing ${method} embeddings...`);
  const raw = JSON.parse(fs.readFileSync(path.join(SOURCE, `embedding_projections_${method}.json`), 'utf-8'));

  const points = raw.points.map((p: any) => ({
    id: p.id,
    x: Math.round(p.x * 1000) / 1000,
    y: Math.round(p.y * 1000) / 1000,
    type: p.type,
    label: p.label,
    cluster: p.cluster,
    clusterId: mapClusterId(p.cluster_id || p.cluster),
    queryId: p.query_id || null,
    similarity: p.similarity ? Math.round(p.similarity * 1000) / 1000 : undefined,
  }));

  const output = { method, pointCount: points.length, points };
  fs.writeFileSync(path.join(OUTPUT, `embedding-${method}.json`), JSON.stringify(output));
  console.log(`  → ${points.length} points written`);
}

// ── Process gap analysis ───────────────────────────────────
function processGaps() {
  console.log('Processing gap analysis...');
  const raw = JSON.parse(fs.readFileSync(path.join(SOURCE, 'gap_analysis_complete.json'), 'utf-8'));
  const analysis = raw.analysis;

  const gaps = analysis.gaps.map((g: any) => {
    // Pick top 2 exemplars with key signals only
    const exemplars = (g.top_cited_exemplars || []).slice(0, 2).map((ex: any) => ({
      domain: ex.domain,
      url: ex.url,
      similarity: Math.round(ex.similarity * 1000) / 1000,
      contentType: ex.structural_signals?.content_type || null,
      authorityType: ex.structural_signals?.authority_type || null,
      wordCount: ex.structural_signals?.word_count || null,
      headerCount: ex.structural_signals?.header_count || null,
      hasFaq: ex.structural_signals?.has_faq_section || false,
      hasTables: (ex.structural_signals?.table_count || 0) > 0,
      readingLevel: ex.structural_signals?.reading_level ? Math.round(ex.structural_signals.reading_level * 10) / 10 : null,
      listItemCount: ex.structural_signals?.list_item_count || 0,
      statCount: ex.structural_signals?.stat_count || 0,
      citationCount: ex.structural_signals?.citation_count || 0,
    }));

    // Company structural signals
    const cs = g.best_company_structural_signals;
    const companySignals = cs ? {
      wordCount: cs.word_count || null,
      headerCount: cs.header_count || null,
      hasFaq: cs.has_faq_section || false,
      hasTables: (cs.table_count || 0) > 0,
      readingLevel: cs.reading_level ? Math.round(cs.reading_level * 10) / 10 : null,
      listItemCount: cs.list_item_count || 0,
    } : null;

    // Content brief
    const cb = g.content_brief || {};

    return {
      id: g.query_id,
      query: g.query_text,
      cluster: g.cluster_name,
      clusterId: mapClusterId(g.cluster_name),
      gap: Math.round(g.gap * 1000) / 1000,
      classification: g.interpretation,
      companyCited: g.company_cited || false,
      companyUrl: g.best_company_url || null,
      companySimilarity: g.best_company_similarity ? Math.round(g.best_company_similarity * 1000) / 1000 : null,
      avgCitationSimilarity: Math.round(g.avg_citation_similarity * 1000) / 1000,
      exemplars,
      companySignals,
      contentBrief: {
        wordCountRange: cb.target_word_count || null,
        readingLevelRange: cb.target_reading_level || null,
        headerCountRange: cb.recommended_header_count || null,
        headerHierarchy: cb.header_hierarchy || null,
        hasFaq: cb.has_faq_section || 0,
        hasTables: cb.has_tables || 0,
        hasDefinition: cb.has_definition_opening || 0,
        hasKeyTakeaways: cb.has_key_takeaways || 0,
        hasStepByStep: cb.has_step_by_step || 0,
        dominantContentType: cb.dominant_content_type || null,
        dominantAuthorityType: cb.dominant_authority_type || null,
        dataDensity: cb.target_data_point_density ? Math.round(cb.target_data_point_density * 10) / 10 : null,
        citationDensity: cb.target_citation_density ? Math.round(cb.target_citation_density * 10) / 10 : null,
      },
    };
  });

  // Proximity stats
  const ps = analysis.proximity_stats;
  const spa = analysis.spa_results?.[0] || {};

  const output = {
    gaps: gaps.sort((a: any, b: any) => b.gap - a.gap),
    totalGaps: gaps.length,
    uncoveredQueries: gaps.filter((g: any) => !g.companyCited).length,
    proximityStats: {
      citationMean: Math.round(ps.citation_similarity_mean * 1000) / 1000,
      citationMedian: Math.round(ps.citation_similarity_median * 1000) / 1000,
      companyMean: Math.round(ps.company_similarity_mean * 1000) / 1000,
      companyMedian: Math.round(ps.company_similarity_median * 1000) / 1000,
      similarityGap: Math.round((ps.citation_similarity_mean - ps.company_similarity_mean) * 1000) / 1000,
    },
    spa: {
      tStat: Math.round(spa.t_stat * 100) / 100,
      pValue: spa.p_value,
      effect: spa.effect,
    },
    perClusterProximity: Object.entries(ps.per_cluster).reduce((acc: any, [name, stats]: [string, any]) => {
      acc[mapClusterId(name)] = {
        mean: Math.round(stats.mean * 1000) / 1000,
        std: Math.round(stats.std * 1000) / 1000,
        min: Math.round(stats.min * 1000) / 1000,
        max: Math.round(stats.max * 1000) / 1000,
        count: stats.count,
      };
      return acc;
    }, {}),
  };

  fs.writeFileSync(path.join(OUTPUT, 'gaps.json'), JSON.stringify(output));
  console.log(`  → ${gaps.length} gaps written`);
}

// ── Process cluster profiles ───────────────────────────────
function processClusterProfiles() {
  console.log('Processing cluster profiles...');

  // Generation spec
  const genSpec = JSON.parse(fs.readFileSync(path.join(SOURCE, 'generation_spec.json'), 'utf-8'));
  const clusterSpecs = genSpec.cluster_specs;

  // Gap analysis for proximity stats
  const gapRaw = JSON.parse(fs.readFileSync(path.join(SOURCE, 'gap_analysis_complete.json'), 'utf-8'));
  const proximityPerCluster = gapRaw.analysis.proximity_stats.per_cluster;

  // Enriched citations for per-cluster domain/engine aggregation
  console.log('  Reading enriched citations (this may take a moment)...');
  const citations: any[] = JSON.parse(fs.readFileSync(path.join(SOURCE, 'enriched_citations.json'), 'utf-8'));

  // Aggregate enriched citations per cluster
  const clusterAgg: Record<string, {
    domains: Record<string, { count: number; isCompany: boolean }>;
    engines: Record<string, number>;
    companyCitations: number;
    totalCitations: number;
  }> = {};

  // Per-domain structural signal accumulator
  const domainSignals: Record<string, Record<string, {
    wordCounts: number[]; headerCounts: number[]; faqCount: number; tableCount: number;
    readingLevels: number[]; contentTypes: Record<string, number>; authorityTypes: Record<string, number>;
    total: number;
  }>> = {};

  for (const cit of citations) {
    const cl = cit.cluster_name;
    if (!clusterAgg[cl]) {
      clusterAgg[cl] = { domains: {}, engines: {}, companyCitations: 0, totalCitations: 0 };
    }
    const agg = clusterAgg[cl];
    agg.totalCitations++;

    const domain = cit.domain;
    if (!agg.domains[domain]) agg.domains[domain] = { count: 0, isCompany: false };
    agg.domains[domain].count++;
    if (cit.is_company_citation) {
      agg.domains[domain].isCompany = true;
      agg.companyCitations++;
    }

    const engine = cit.engine;
    agg.engines[engine] = (agg.engines[engine] || 0) + 1;

    // Accumulate structural signals per domain per cluster
    if (!domainSignals[cl]) domainSignals[cl] = {};
    if (!domainSignals[cl][domain]) {
      domainSignals[cl][domain] = { wordCounts: [], headerCounts: [], faqCount: 0, tableCount: 0, readingLevels: [], contentTypes: {}, authorityTypes: {}, total: 0 };
    }
    const ds = domainSignals[cl][domain];
    ds.total++;
    const ss = cit.structural_signals;
    if (ss) {
      if (ss.word_count) ds.wordCounts.push(ss.word_count);
      if (ss.header_count != null) ds.headerCounts.push(ss.header_count);
      if (ss.has_faq_section) ds.faqCount++;
      if (ss.table_count > 0) ds.tableCount++;
      if (ss.reading_level) ds.readingLevels.push(ss.reading_level);
      if (ss.content_type) ds.contentTypes[ss.content_type] = (ds.contentTypes[ss.content_type] || 0) + 1;
      if (ss.authority_type) ds.authorityTypes[ss.authority_type] = (ds.authorityTypes[ss.authority_type] || 0) + 1;
    }
  }

  // Build cluster profiles
  const profiles: Record<string, any> = {};
  for (const spec of clusterSpecs) {
    const id = mapClusterId(spec.cluster_name);
    const agg = clusterAgg[spec.cluster_name] || { domains: {}, engines: {}, companyCitations: 0, totalCitations: 0 };
    const prox = proximityPerCluster[spec.cluster_name];

    // Top 15 domains sorted by citation count with structural signals
    const clusterDomainSignals = domainSignals[spec.cluster_name] || {};
    const sortedDomains = Object.entries(agg.domains)
      .map(([domain, info]: [string, any]) => {
        const ds = clusterDomainSignals[domain];
        const avg = (arr: number[]) => arr.length > 0 ? Math.round(arr.reduce((s, v) => s + v, 0) / arr.length) : null;
        const topType = (rec: Record<string, number>) => {
          const entries = Object.entries(rec);
          return entries.length > 0 ? entries.sort((a, b) => b[1] - a[1])[0][0] : null;
        };
        return {
          domain,
          citations: info.count,
          isCompany: info.isCompany,
          share: agg.totalCitations > 0 ? Math.round((info.count / agg.totalCitations) * 1000) / 10 : 0,
          // Structural signals
          avgWordCount: ds ? avg(ds.wordCounts) : null,
          avgHeaderCount: ds ? avg(ds.headerCounts) : null,
          faqRate: ds && ds.total > 0 ? Math.round((ds.faqCount / ds.total) * 100) / 100 : null,
          tableRate: ds && ds.total > 0 ? Math.round((ds.tableCount / ds.total) * 100) / 100 : null,
          avgReadingLevel: ds && ds.readingLevels.length > 0 ? Math.round(ds.readingLevels.reduce((s, v) => s + v, 0) / ds.readingLevels.length * 10) / 10 : null,
          contentType: ds ? topType(ds.contentTypes) : null,
          authorityType: ds ? topType(ds.authorityTypes) : null,
        };
      })
      .sort((a, b) => b.citations - a.citations)
      .slice(0, 15);

    // Determine competitor type (heuristic)
    const directDomains = new Set(['innovaccer.com', 'www.healthcatalyst.com', 'arcadia.io', 'censinet.com', 'definitivehc.com', 'persivia.com', 'epic.com', 'cerner.com', 'athenahealth.com', 'www.insighthealth.ai', 'help.insighthealth.ai']);
    const authorityDomains = new Set<string>();
    for (const d of sortedDomains) {
      if (d.domain.endsWith('.gov') || d.domain.endsWith('.edu') || d.domain.endsWith('.org')) {
        authorityDomains.add(d.domain);
      }
    }

    const domainsWithType = sortedDomains.map(d => ({
      ...d,
      type: d.isCompany ? 'company' as const
        : directDomains.has(d.domain) ? 'direct' as const
        : authorityDomains.has(d.domain) ? 'authority' as const
        : 'mindshare' as const,
    }));

    // Company presence
    const companyDomainEntry = sortedDomains.find(d => d.isCompany);
    const companyRank = companyDomainEntry ? sortedDomains.indexOf(companyDomainEntry) + 1 : null;

    profiles[id] = {
      id,
      name: spec.cluster_name,
      queryCount: spec.query_count,
      totalCitations: agg.totalCitations,
      uniqueDomains: Object.keys(agg.domains).length,

      // Company presence
      companyCitations: agg.companyCitations,
      companyShare: agg.totalCitations > 0 ? Math.round((agg.companyCitations / agg.totalCitations) * 1000) / 10 : 0,
      companyRank,
      presence: agg.companyCitations === 0 ? 'none'
        : agg.companyCitations <= 2 ? 'minimal'
        : agg.companyCitations <= 5 ? 'low'
        : agg.companyCitations <= 15 ? 'moderate'
        : 'strong',

      // Structural norms from generation spec
      avgWordCount: Math.round(spec.avg_word_count),
      wordCountRange: spec.word_count_range,
      dominantContentType: spec.dominant_content_type,
      dominantAuthorityType: spec.dominant_authority_type,
      structuralRates: spec.structural_rates,
      faqRate: Math.round(spec.faq_rate * 100) / 100,
      tableRate: Math.round(spec.table_rate * 100) / 100,
      requiredElements: spec.required_elements,
      exemplarThemes: spec.exemplar_themes,

      // Authority signals
      authoritySignals: spec.authority_signals,

      // Proximity stats
      proximity: prox ? {
        mean: Math.round(prox.mean * 1000) / 1000,
        std: Math.round(prox.std * 1000) / 1000,
        count: prox.count,
      } : null,

      // Engine breakdown
      engineBreakdown: agg.engines,

      // Top domains
      topDomains: domainsWithType,
    };
  }

  fs.writeFileSync(path.join(OUTPUT, 'cluster-profiles.json'), JSON.stringify(profiles, null, 0));
  console.log(`  → ${Object.keys(profiles).length} cluster profiles written`);
}

// ── Process company positioning ────────────────────────────
function processCompanyPositioning() {
  console.log('Processing company positioning...');
  const umap = JSON.parse(fs.readFileSync(path.join(SOURCE, 'embedding_projections_umap.json'), 'utf-8'));
  const points = umap.points;

  // Compute topic cluster centroids (exclude Company cluster)
  const topicCentroids: Record<string, { xs: number[]; ys: number[] }> = {};
  for (const p of points) {
    if (p.cluster === 'Company') continue;
    if (!topicCentroids[p.cluster]) topicCentroids[p.cluster] = { xs: [], ys: [] };
    topicCentroids[p.cluster].xs.push(p.x);
    topicCentroids[p.cluster].ys.push(p.y);
  }

  const centroids: Record<string, [number, number]> = {};
  for (const [cl, data] of Object.entries(topicCentroids)) {
    centroids[cl] = [
      data.xs.reduce((s: number, x: number) => s + x, 0) / data.xs.length,
      data.ys.reduce((s: number, y: number) => s + y, 0) / data.ys.length,
    ];
  }

  // Assign each company point to nearest topic cluster
  const companyPoints = points.filter((p: any) => p.type === 'company');
  const distribution: Record<string, number> = {};
  for (const cl of Object.keys(centroids)) {
    distribution[mapClusterId(cl)] = 0;
  }

  for (const cp of companyPoints) {
    let minDist = Infinity;
    let nearest = '';
    for (const [cl, [cx, cy]] of Object.entries(centroids)) {
      const d = Math.sqrt(Math.pow(cp.x - cx, 2) + Math.pow(cp.y - cy, 2));
      if (d < minDist) { minDist = d; nearest = cl; }
    }
    const id = mapClusterId(nearest);
    distribution[id] = (distribution[id] || 0) + 1;
  }

  // Company centroid
  const compCx = companyPoints.reduce((s: number, p: any) => s + p.x, 0) / companyPoints.length;
  const compCy = companyPoints.reduce((s: number, p: any) => s + p.y, 0) / companyPoints.length;

  // Distance from company centroid to each topic centroid
  const distances: Record<string, number> = {};
  for (const [cl, [cx, cy]] of Object.entries(centroids)) {
    distances[mapClusterId(cl)] = Math.round(Math.sqrt(Math.pow(compCx - cx, 2) + Math.pow(compCy - cy, 2)) * 100) / 100;
  }

  // Cluster spatial characteristics
  const clusterDensity: Record<string, { spread: number; density: number; count: number }> = {};
  for (const [cl, data] of Object.entries(topicCentroids)) {
    const cx = centroids[cl][0];
    const cy = centroids[cl][1];
    const n = data.xs.length;
    const spread = Math.sqrt(data.xs.reduce((s, x, i) => s + Math.pow(x - cx, 2) + Math.pow(data.ys[i] - cy, 2), 0) / n);
    const xRange = Math.max(...data.xs) - Math.min(...data.xs);
    const yRange = Math.max(...data.ys) - Math.min(...data.ys);
    const area = Math.max(xRange * yRange, 0.01);
    clusterDensity[mapClusterId(cl)] = {
      spread: Math.round(spread * 100) / 100,
      density: Math.round((n / area) * 10) / 10,
      count: n,
    };
  }

  const output = {
    distribution,
    distances,
    clusterDensity,
    totalCompanyPages: companyPoints.length,
    companyCentroid: [Math.round(compCx * 100) / 100, Math.round(compCy * 100) / 100],
  };

  fs.writeFileSync(path.join(OUTPUT, 'company-positioning.json'), JSON.stringify(output));
  console.log(`  → Company positioning written (${companyPoints.length} pages)`);
}

// ── Process cluster distances (1536-dim cosine) ────────────
function processClusterDistances() {
  console.log('Processing cluster distances...');
  const gapRaw = JSON.parse(fs.readFileSync(path.join(SOURCE, 'gap_analysis_complete.json'), 'utf-8'));
  const rawCentroids = gapRaw.analysis.centroids;

  const clusterNames: string[] = [];
  const clusterIds: string[] = [];
  const vectors: number[][] = [];

  for (const c of rawCentroids) {
    clusterNames.push(c.cluster_name);
    clusterIds.push(mapClusterId(c.cluster_name));
    vectors.push(c.query_centroid);
  }

  // Cosine distance
  function cosineDist(a: number[], b: number[]): number {
    let dot = 0, na = 0, nb = 0;
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      na += a[i] * a[i];
      nb += b[i] * b[i];
    }
    na = Math.sqrt(na);
    nb = Math.sqrt(nb);
    if (na === 0 || nb === 0) return 1;
    return Math.round((1 - dot / (na * nb)) * 10000) / 10000;
  }

  const matrix: number[][] = [];
  for (let i = 0; i < vectors.length; i++) {
    const row: number[] = [];
    for (let j = 0; j < vectors.length; j++) {
      row.push(cosineDist(vectors[i], vectors[j]));
    }
    matrix.push(row);
  }

  // Also include query↔citation centroid distances
  const centroidDistances: Record<string, number> = {};
  for (const c of rawCentroids) {
    centroidDistances[mapClusterId(c.cluster_name)] = Math.round(c.distance * 10000) / 10000;
  }

  const output = {
    clusters: clusterIds,
    clusterNames,
    matrix,
    centroidDistances,
  };

  fs.writeFileSync(path.join(OUTPUT, 'cluster-distances.json'), JSON.stringify(output));
  console.log(`  → ${clusterNames.length}×${clusterNames.length} distance matrix written`);
}

// ── Main ───────────────────────────────────────────────────
function main() {
  console.log('=== Processing Embedding Lab Data ===\n');

  // Ensure output directory exists
  fs.mkdirSync(OUTPUT, { recursive: true });

  processEmbeddings('umap');
  processEmbeddings('tsne');
  processGaps();
  processClusterProfiles();
  processCompanyPositioning();
  processClusterDistances();

  console.log('\n=== Done ===');

  // Print sizes
  const files = fs.readdirSync(OUTPUT);
  for (const f of files) {
    const size = fs.statSync(path.join(OUTPUT, f)).size;
    console.log(`  ${f}: ${(size / 1024).toFixed(1)}KB`);
  }
}

main();
