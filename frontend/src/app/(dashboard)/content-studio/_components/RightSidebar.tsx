'use client';

import { useState } from 'react';
import { Check, Download, ExternalLink, Copy } from 'lucide-react';
import type { ContentCard, ContentMetadata } from './types';

type Tab = 'metrics' | 'seo' | 'links' | 'export';

const ENGINE_DOMAINS: Record<string, string> = {
  ChatGPT: 'openai.com',
  Claude: 'anthropic.com',
  Perplexity: 'perplexity.ai',
  'Google AI': 'google.com',
  Gemini: 'gemini.google.com',
};

// Brand-consistent colors — teal as primary, warning only for low values
function scoreColor(s: number) {
  if (s >= 60) return 'var(--accent)';
  if (s >= 50) return 'var(--warning)';
  return 'var(--error)';
}

function complianceColor(pct: number) {
  if (pct >= 85) return 'var(--accent)';
  if (pct >= 70) return 'var(--warning)';
  return 'var(--error)';
}

const OVERLINE: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  color: 'var(--text-tertiary)',
  marginBottom: 10,
};

const BAR_HEIGHT = 6;
const BAR_RADIUS = 3;
const BAR_BG = 'var(--border)';

function MetricsTab({ card }: { card: ContentCard }) {
  const article = card.articleContent;
  if (!article) {
    return (
      <div className="p-4 flex flex-col items-center justify-center" style={{ paddingTop: 48, color: 'var(--text-tertiary)', fontSize: 12 }}>
        <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 10, fontSize: 18 }}>
          &#x2014;
        </div>
        Metrics available after article generation.
      </div>
    );
  }

  const avgScore = Math.round(article.citPrediction.reduce((a, b) => a + b.score, 0) / article.citPrediction.length);

  return (
    <div className="p-3 space-y-4 overflow-y-auto flex-1">
      {/* Citation Prediction — card with avg score prominent */}
      <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
          <div className="flex items-center justify-between">
            <span style={{ ...OVERLINE, marginBottom: 0 }}>Citation Prediction</span>
            <div className="flex items-baseline gap-1">
              <span style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)' }}>{avgScore}</span>
              <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>avg</span>
            </div>
          </div>
        </div>
        <div className="px-3 py-2 space-y-2">
          {article.citPrediction.map((p) => (
            <div key={p.engine} className="flex items-center gap-2">
              <img
                src={`https://www.google.com/s2/favicons?domain=${ENGINE_DOMAINS[p.engine]}&sz=32`}
                alt={p.engine}
                width={14}
                height={14}
                style={{ borderRadius: 2 }}
              />
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', width: 60, flexShrink: 0 }}>{p.engine}</span>
              <div className="flex-1" style={{ height: BAR_HEIGHT, background: BAR_BG, borderRadius: BAR_RADIUS, overflow: 'hidden' }}>
                <div style={{ width: `${p.score}%`, height: '100%', background: 'var(--accent)', borderRadius: BAR_RADIUS, transition: 'width 0.6s ease', opacity: p.score >= 60 ? 1 : 0.6 }} />
              </div>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', width: 24, textAlign: 'right' }}>
                {p.score}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Structural Compliance — compact grid */}
      <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
          <span style={{ ...OVERLINE, marginBottom: 0 }}>Structural Compliance</span>
        </div>
        <div className="px-3 py-2 space-y-2.5">
          {article.compliance.map((c) => {
            const pct = Math.round((c.current / c.target) * 100);
            const isGood = pct >= 85;
            return (
              <div key={c.label}>
                <div className="flex items-center justify-between mb-1">
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{c.label}</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: isGood ? 'var(--accent)' : 'var(--warning)' }}>
                    {c.current}/{c.target}
                  </span>
                </div>
                <div style={{ height: BAR_HEIGHT, background: BAR_BG, borderRadius: BAR_RADIUS, overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: isGood ? 'var(--accent)' : 'var(--warning)', borderRadius: BAR_RADIUS, transition: 'width 0.6s ease' }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Voice + E-E-A-T combined */}
      <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
          <span style={{ ...OVERLINE, marginBottom: 0 }}>Quality Scores</span>
        </div>
        <div className="px-3 py-2 space-y-3">
          {/* Voice */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Voice compliance</span>
              <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)' }}>
                {article.voiceCompliance}%
              </span>
            </div>
            <div style={{ height: BAR_HEIGHT, background: BAR_BG, borderRadius: BAR_RADIUS, overflow: 'hidden' }}>
              <div style={{ width: `${article.voiceCompliance}%`, height: '100%', background: 'var(--accent)', borderRadius: BAR_RADIUS }} />
            </div>
          </div>

          {/* Divider */}
          <div style={{ borderTop: '1px solid var(--border)' }} />

          {/* E-E-A-T */}
          <div className="flex items-center justify-between">
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>E-E-A-T overall</span>
            <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
              {article.eeat.overall}<span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 400 }}>/100</span>
            </span>
          </div>
          <div className="space-y-2">
            {[
              { label: 'Experience', value: article.eeat.experience },
              { label: 'Expertise', value: article.eeat.expertise },
              { label: 'Authority', value: article.eeat.authoritativeness },
              { label: 'Trust', value: article.eeat.trustworthiness },
            ].map((item) => (
              <div key={item.label}>
                <div className="flex items-center justify-between mb-1">
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{item.label}</span>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-secondary)' }}>
                    {item.value}
                  </span>
                </div>
                <div style={{ height: 4, background: BAR_BG, borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${item.value}%`, height: '100%', background: 'var(--accent)', borderRadius: 2, opacity: item.value >= 75 ? 1 : 0.6 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SEOTab({ metadata, onChange }: { metadata?: ContentMetadata; onChange: (m: ContentMetadata) => void }) {
  const meta = metadata || {
    slug: '',
    metaTitle: '',
    metaDescription: '',
    canonicalUrl: '',
    schemaMarkup: false,
    tags: [],
  };

  const [tagInput, setTagInput] = useState('');

  function addTag() {
    if (tagInput.trim() && !meta.tags.includes(tagInput.trim())) {
      onChange({ ...meta, tags: [...meta.tags, tagInput.trim()] });
      setTagInput('');
    }
  }

  const inputStyle: React.CSSProperties = {
    height: 30,
    padding: '0 8px',
    fontSize: 12,
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-primary)',
    outline: 'none',
    width: '100%',
  };

  return (
    <div className="p-4 space-y-4 overflow-y-auto flex-1">
      <div>
        <label style={{ ...OVERLINE, marginBottom: 4, display: 'block' }}>Slug URL</label>
        <input
          value={meta.slug}
          onChange={(e) => onChange({ ...meta, slug: e.target.value })}
          style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
          placeholder="/blog/your-slug"
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label style={{ ...OVERLINE, marginBottom: 0 }}>Meta Title</label>
          <span style={{
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            color: meta.metaTitle.length > 60 ? 'var(--error)' : meta.metaTitle.length > 50 ? 'var(--warning)' : 'var(--text-tertiary)',
          }}>
            {meta.metaTitle.length}/60
          </span>
        </div>
        <input value={meta.metaTitle} onChange={(e) => onChange({ ...meta, metaTitle: e.target.value })} style={inputStyle} />
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label style={{ ...OVERLINE, marginBottom: 0 }}>Meta Description</label>
          <span style={{
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            color: meta.metaDescription.length > 155 ? 'var(--error)' : meta.metaDescription.length > 140 ? 'var(--warning)' : 'var(--text-tertiary)',
          }}>
            {meta.metaDescription.length}/155
          </span>
        </div>
        <textarea
          value={meta.metaDescription}
          onChange={(e) => onChange({ ...meta, metaDescription: e.target.value })}
          rows={3}
          style={{ ...inputStyle, height: 'auto', padding: '6px 8px', resize: 'vertical' }}
        />
      </div>

      <div>
        <label style={{ ...OVERLINE, marginBottom: 4, display: 'block' }}>Canonical URL</label>
        <input
          value={meta.canonicalUrl}
          onChange={(e) => onChange({ ...meta, canonicalUrl: e.target.value })}
          style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
        />
      </div>

      <div className="flex items-center justify-between" style={{ padding: '4px 0' }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Schema markup</span>
        <button
          onClick={() => onChange({ ...meta, schemaMarkup: !meta.schemaMarkup })}
          style={{
            width: 36, height: 20, borderRadius: 10,
            background: meta.schemaMarkup ? 'var(--accent)' : 'var(--border)',
            position: 'relative', cursor: 'pointer', border: 'none', transition: 'background 0.2s',
          }}
        >
          <span style={{
            width: 16, height: 16, borderRadius: '50%', background: 'white',
            position: 'absolute', top: 2, left: meta.schemaMarkup ? 18 : 2,
            transition: 'left 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
          }} />
        </button>
      </div>

      <div>
        <label style={{ ...OVERLINE, marginBottom: 4, display: 'block' }}>Publish Date</label>
        <input type="date" value={meta.publishDate || ''} onChange={(e) => onChange({ ...meta, publishDate: e.target.value })} style={inputStyle} />
      </div>

      <div>
        <label style={{ ...OVERLINE, marginBottom: 4, display: 'block' }}>Author</label>
        <input value={meta.author || ''} onChange={(e) => onChange({ ...meta, author: e.target.value })} style={inputStyle} />
      </div>

      <div>
        <label style={{ ...OVERLINE, marginBottom: 4, display: 'block' }}>Tags</label>
        <div className="flex flex-wrap gap-1 mb-2">
          {meta.tags.map((tag) => (
            <span key={tag} className="flex items-center gap-1" style={{
              fontSize: 10, fontWeight: 500, padding: '2px 8px',
              borderRadius: 'var(--radius-full)', background: 'var(--accent-subtle)', color: 'var(--accent)',
            }}>
              {tag}
              <button
                onClick={() => onChange({ ...meta, tags: meta.tags.filter((t) => t !== tag) })}
                style={{ cursor: 'pointer', background: 'none', border: 'none', color: 'var(--accent)', fontSize: 12, lineHeight: 1 }}
              >
                &times;
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-1">
          <input
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addTag()}
            placeholder="Add tag..."
            style={{ ...inputStyle, flex: 1, height: 26, fontSize: 11 }}
          />
          <button onClick={addTag} style={{
            height: 26, padding: '0 8px', fontSize: 11, fontWeight: 500,
            background: 'var(--accent)', color: 'var(--text-on-accent)',
            border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
          }}>
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

function LinksTab({ card }: { card: ContentCard }) {
  const interlinks = card.articleContent?.interlinks || [];

  return (
    <div className="p-4 space-y-5 overflow-y-auto flex-1">
      <div>
        <div style={OVERLINE}>Interlink Suggestions</div>
        <div className="space-y-2">
          {interlinks.map((link) => (
            <label key={link.path} className="flex items-start gap-2 cursor-pointer">
              <input type="checkbox" checked={link.linked} readOnly style={{ marginTop: 2, accentColor: 'var(--accent)' }} />
              <div>
                <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>{link.title}</div>
                <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{link.path}</div>
              </div>
            </label>
          ))}
          {interlinks.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>No interlink suggestions yet.</div>
          )}
        </div>
      </div>

      <div>
        <div style={OVERLINE}>External Citations</div>
        <div className="space-y-2">
          {(card.briefContent?.sources || []).map((source) => (
            <div key={source.domain} className="flex items-center gap-2">
              <img
                src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
                alt={source.domain}
                width={14}
                height={14}
                style={{ borderRadius: 2 }}
              />
              <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{source.name}</span>
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{source.domain}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ExportTab({ onPublish }: { onPublish: () => void }) {
  const [copied, setCopied] = useState<string | null>(null);
  const [showPublishForm, setShowPublishForm] = useState(false);
  const [publishUrl, setPublishUrl] = useState('');

  function handleCopy(format: string) {
    navigator.clipboard.writeText(`[${format} content would be copied here]`);
    setCopied(format);
    setTimeout(() => setCopied(null), 1500);
  }

  const btnStyle: React.CSSProperties = {
    height: 30, padding: '0 12px', fontSize: 12, fontWeight: 500,
    background: 'transparent', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', cursor: 'pointer', transition: 'all 0.15s',
    width: '100%', display: 'flex', alignItems: 'center', gap: 8,
  };

  return (
    <div className="p-4 space-y-5 overflow-y-auto flex-1">
      <div>
        <div style={OVERLINE}>Copy</div>
        <div className="space-y-2">
          {['Markdown', 'HTML', 'Plain text'].map((fmt) => (
            <button
              key={fmt}
              onClick={() => handleCopy(fmt)}
              style={{ ...btnStyle, color: copied === fmt ? 'var(--success)' : 'var(--text-primary)' }}
            >
              {copied === fmt ? <Check size={12} /> : <Copy size={12} />}
              {copied === fmt ? 'Copied' : `Copy as ${fmt}`}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div style={OVERLINE}>Download</div>
        <div className="space-y-2">
          {['.md', '.html'].map((ext) => (
            <button key={ext} style={{ ...btnStyle, color: 'var(--text-primary)' }}>
              <Download size={12} />
              Download {ext}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div style={OVERLINE}>Publish</div>
        {!showPublishForm ? (
          <>
            <button
              onClick={() => setShowPublishForm(true)}
              style={{
                ...btnStyle,
                background: 'var(--accent)',
                color: 'var(--text-on-accent)',
                border: 'none',
                justifyContent: 'center',
              }}
            >
              Mark as Published
            </button>
            <div className="mt-3 p-3" style={{
              border: '1px dashed var(--border)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 11,
              color: 'var(--text-tertiary)',
              textAlign: 'center',
            }}>
              Connect your CMS to publish directly.<br />
              <span style={{ fontSize: 10, marginTop: 4, display: 'inline-block' }}>Coming Soon</span>
            </div>
          </>
        ) : (
          <div className="p-3 space-y-3" style={{
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--bg)',
          }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              Paste the live URL so we can track citations.
            </div>
            <input
              value={publishUrl}
              onChange={(e) => setPublishUrl(e.target.value)}
              placeholder="https://yourdomain.com/blog/..."
              style={{
                width: '100%', height: 30, padding: '0 8px', fontSize: 12,
                fontFamily: 'var(--font-mono)', background: 'var(--surface)',
                border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)', outline: 'none',
              }}
            />
            <div className="flex gap-2">
              <button onClick={() => setShowPublishForm(false)} style={{
                height: 26, padding: '0 10px', fontSize: 11, fontWeight: 500,
                background: 'transparent', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)', color: 'var(--text-secondary)', cursor: 'pointer',
              }}>
                Cancel
              </button>
              <button
                onClick={() => { onPublish(); setShowPublishForm(false); }}
                className="flex items-center gap-1"
                style={{
                  height: 26, padding: '0 10px', fontSize: 11, fontWeight: 500,
                  background: 'var(--success)', color: '#fff', border: 'none',
                  borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                }}
              >
                <ExternalLink size={10} />
                Confirm — Start Tracking
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface RightSidebarProps {
  card: ContentCard;
  metadata?: ContentMetadata;
  onMetadataChange: (m: ContentMetadata) => void;
  onPublish: () => void;
}

export function RightSidebar({ card, metadata, onMetadataChange, onPublish }: RightSidebarProps) {
  const [activeTab, setActiveTab] = useState<Tab>('metrics');

  const tabs: { id: Tab; label: string }[] = [
    { id: 'metrics', label: 'Metrics' },
    { id: 'seo', label: 'SEO' },
    { id: 'links', label: 'Links' },
    { id: 'export', label: 'Export' },
  ];

  return (
    <div
      className="flex flex-col h-full"
      style={{
        width: 300,
        borderLeft: '1px solid var(--border)',
        background: 'var(--surface)',
        flexShrink: 0,
      }}
    >
      <div className="flex" style={{ borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1, height: 36, fontSize: 11,
              fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-secondary)',
              background: 'transparent', border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer', transition: 'all 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === 'metrics' && <MetricsTab card={card} />}
        {activeTab === 'seo' && <SEOTab metadata={metadata} onChange={onMetadataChange} />}
        {activeTab === 'links' && <LinksTab card={card} />}
        {activeTab === 'export' && <ExportTab onPublish={onPublish} />}
      </div>
    </div>
  );
}
