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

function scoreColor(s: number) {
  if (s > 60) return 'var(--success)';
  if (s >= 50) return 'var(--accent)';
  return 'var(--error)';
}

function complianceColor(pct: number) {
  if (pct > 90) return 'var(--success)';
  if (pct >= 70) return 'var(--accent)';
  return 'var(--warning)';
}

function MetricsTab({ card }: { card: ContentCard }) {
  const article = card.articleContent;
  if (!article) {
    return (
      <div className="p-4" style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>
        Metrics available after article generation.
      </div>
    );
  }

  const avgScore = Math.round(article.citPrediction.reduce((a, b) => a + b.score, 0) / article.citPrediction.length);

  return (
    <div className="p-4 space-y-5 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
      {/* Citation Prediction */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Citation Prediction
        </div>
        <div className="space-y-2">
          {article.citPrediction.map((p) => (
            <div key={p.engine} className="flex items-center gap-2">
              <img
                src={`https://www.google.com/s2/favicons?domain=${ENGINE_DOMAINS[p.engine]}&sz=32`}
                alt={p.engine}
                width={14}
                height={14}
                style={{ borderRadius: 2 }}
              />
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', width: 70, flexShrink: 0 }}>{p.engine}</span>
              <div className="flex-1" style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${p.score}%`, height: '100%', background: scoreColor(p.score), borderRadius: 3, transition: 'width 0.6s ease' }} />
              </div>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: scoreColor(p.score), width: 24, textAlign: 'right' }}>
                {p.score}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-2 flex items-baseline gap-1">
          <span style={{ fontSize: 20, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)' }}>{avgScore}</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>avg across engines</span>
        </div>
      </div>

      {/* Structural Compliance */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Structural Compliance
        </div>
        <div className="space-y-2">
          {article.compliance.map((c) => {
            const pct = Math.round((c.current / c.target) * 100);
            return (
              <div key={c.label}>
                <div className="flex items-center justify-between mb-1">
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{c.label}</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                    {c.current}/{c.target}
                  </span>
                </div>
                <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: complianceColor(pct), borderRadius: 2 }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Voice Compliance */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Voice Compliance
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1" style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ width: `${article.voiceCompliance}%`, height: '100%', background: 'var(--accent)', borderRadius: 3 }} />
          </div>
          <span style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--accent)' }}>
            {article.voiceCompliance}%
          </span>
        </div>
      </div>

      {/* E-E-A-T */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          E-E-A-T Score
        </div>
        <div className="flex items-baseline gap-1 mb-3">
          <span style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
            {article.eeat.overall}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>/100</span>
        </div>
        <div className="space-y-2">
          {[
            { label: 'Experience', value: article.eeat.experience },
            { label: 'Expertise', value: article.eeat.expertise },
            { label: 'Authoritativeness', value: article.eeat.authoritativeness },
            { label: 'Trustworthiness', value: article.eeat.trustworthiness },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2">
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', width: 110, flexShrink: 0 }}>{item.label}</span>
              <div className="flex-1" style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{ width: `${item.value}%`, height: '100%', background: complianceColor(item.value), borderRadius: 2 }} />
              </div>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', width: 20, textAlign: 'right' }}>
                {item.value}
              </span>
            </div>
          ))}
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

  return (
    <div className="p-4 space-y-4 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
      {/* Slug */}
      <div>
        <label style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', display: 'block', marginBottom: 4 }}>
          Slug URL
        </label>
        <input
          value={meta.slug}
          onChange={(e) => onChange({ ...meta, slug: e.target.value })}
          className="w-full"
          style={{
            height: 30,
            padding: '0 8px',
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            outline: 'none',
          }}
          placeholder="/blog/your-slug"
        />
      </div>

      {/* Meta title */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>
            Meta Title
          </label>
          <span style={{
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            color: meta.metaTitle.length > 60 ? 'var(--error)' : meta.metaTitle.length > 50 ? 'var(--warning)' : 'var(--text-tertiary)',
          }}>
            {meta.metaTitle.length}/60
          </span>
        </div>
        <input
          value={meta.metaTitle}
          onChange={(e) => onChange({ ...meta, metaTitle: e.target.value })}
          className="w-full"
          style={{
            height: 30,
            padding: '0 8px',
            fontSize: 12,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            outline: 'none',
          }}
        />
      </div>

      {/* Meta description */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>
            Meta Description
          </label>
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
          className="w-full"
          rows={3}
          style={{
            padding: '6px 8px',
            fontSize: 12,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            outline: 'none',
            resize: 'vertical',
          }}
        />
      </div>

      {/* Canonical URL */}
      <div>
        <label style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', display: 'block', marginBottom: 4 }}>
          Canonical URL
        </label>
        <input
          value={meta.canonicalUrl}
          onChange={(e) => onChange({ ...meta, canonicalUrl: e.target.value })}
          className="w-full"
          style={{
            height: 30,
            padding: '0 8px',
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            outline: 'none',
          }}
        />
      </div>

      {/* Schema markup toggle */}
      <div className="flex items-center justify-between">
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Schema markup</span>
        <button
          onClick={() => onChange({ ...meta, schemaMarkup: !meta.schemaMarkup })}
          style={{
            width: 36,
            height: 20,
            borderRadius: 10,
            background: meta.schemaMarkup ? 'var(--accent)' : 'var(--border)',
            position: 'relative',
            cursor: 'pointer',
            border: 'none',
            transition: 'background 0.2s',
          }}
        >
          <span style={{
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: 'white',
            position: 'absolute',
            top: 2,
            left: meta.schemaMarkup ? 18 : 2,
            transition: 'left 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
          }} />
        </button>
      </div>

      {/* Publish date */}
      <div>
        <label style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', display: 'block', marginBottom: 4 }}>
          Publish Date
        </label>
        <input
          type="date"
          value={meta.publishDate || ''}
          onChange={(e) => onChange({ ...meta, publishDate: e.target.value })}
          className="w-full"
          style={{
            height: 30,
            padding: '0 8px',
            fontSize: 12,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            outline: 'none',
          }}
        />
      </div>

      {/* Author */}
      <div>
        <label style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', display: 'block', marginBottom: 4 }}>
          Author
        </label>
        <input
          value={meta.author || ''}
          onChange={(e) => onChange({ ...meta, author: e.target.value })}
          className="w-full"
          style={{
            height: 30,
            padding: '0 8px',
            fontSize: 12,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            outline: 'none',
          }}
        />
      </div>

      {/* Tags */}
      <div>
        <label style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', display: 'block', marginBottom: 4 }}>
          Tags
        </label>
        <div className="flex flex-wrap gap-1 mb-2">
          {meta.tags.map((tag) => (
            <span
              key={tag}
              className="flex items-center gap-1"
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                background: 'var(--accent-subtle)',
                color: 'var(--accent)',
              }}
            >
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
            style={{
              flex: 1,
              height: 26,
              padding: '0 8px',
              fontSize: 11,
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
          <button
            onClick={addTag}
            style={{
              height: 26,
              padding: '0 8px',
              fontSize: 11,
              fontWeight: 500,
              background: 'var(--accent)',
              color: 'var(--text-on-accent)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
            }}
          >
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
    <div className="p-4 space-y-5 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Interlink Suggestions
        </div>
        <div className="space-y-2">
          {interlinks.map((link) => (
            <label key={link.path} className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={link.linked}
                readOnly
                style={{ marginTop: 2, accentColor: 'var(--accent)' }}
              />
              <div>
                <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>{link.title}</div>
                <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{link.path}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* External Citations */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          External Citations
        </div>
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

  return (
    <div className="p-4 space-y-5 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
      {/* Copy */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Copy
        </div>
        <div className="space-y-2">
          {['Markdown', 'HTML', 'Plain text'].map((fmt) => (
            <button
              key={fmt}
              onClick={() => handleCopy(fmt)}
              className="w-full flex items-center gap-2"
              style={{
                height: 30,
                padding: '0 12px',
                fontSize: 12,
                fontWeight: 500,
                background: 'transparent',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: copied === fmt ? 'var(--success)' : 'var(--text-primary)',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {copied === fmt ? <Check size={12} /> : <Copy size={12} />}
              {copied === fmt ? 'Copied' : `Copy as ${fmt}`}
            </button>
          ))}
        </div>
      </div>

      {/* Download */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Download
        </div>
        <div className="space-y-2">
          {['.md', '.html'].map((ext) => (
            <button
              key={ext}
              className="w-full flex items-center gap-2"
              style={{
                height: 30,
                padding: '0 12px',
                fontSize: 12,
                fontWeight: 500,
                background: 'transparent',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                cursor: 'pointer',
              }}
            >
              <Download size={12} />
              Download {ext}
            </button>
          ))}
        </div>
      </div>

      {/* Publish */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Publish
        </div>

        {!showPublishForm ? (
          <>
            <button
              onClick={() => setShowPublishForm(true)}
              className="w-full flex items-center justify-center gap-2"
              style={{
                height: 30,
                padding: '0 12px',
                fontSize: 12,
                fontWeight: 500,
                background: 'var(--accent)',
                color: 'var(--text-on-accent)',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Mark as Published
            </button>

            <div
              className="mt-3 p-3"
              style={{
                border: '1px dashed var(--border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 11,
                color: 'var(--text-tertiary)',
                textAlign: 'center',
              }}
            >
              Connect your CMS to publish directly.<br />
              Supported: WordPress, Webflow, Ghost, Custom API<br />
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4, display: 'inline-block' }}>Connect CMS — Coming Soon</span>
            </div>
          </>
        ) : (
          <div
            className="p-3 space-y-3"
            style={{
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--surface)',
            }}
          >
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              Published this content? Paste the live URL so we can track citations.
            </div>
            <input
              value={publishUrl}
              onChange={(e) => setPublishUrl(e.target.value)}
              placeholder="https://yourdomain.com/blog/..."
              style={{
                width: '100%',
                height: 30,
                padding: '0 8px',
                fontSize: 12,
                fontFamily: 'var(--font-mono)',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                outline: 'none',
              }}
            />
            <div className="flex gap-2">
              <button
                onClick={() => setShowPublishForm(false)}
                style={{
                  height: 26,
                  padding: '0 10px',
                  fontSize: 11,
                  fontWeight: 500,
                  background: 'transparent',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => { onPublish(); setShowPublishForm(false); }}
                className="flex items-center gap-1"
                style={{
                  height: 26,
                  padding: '0 10px',
                  fontSize: 11,
                  fontWeight: 500,
                  background: 'var(--success)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
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
      {/* Tab bar */}
      <div
        className="flex"
        style={{
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              height: 36,
              fontSize: 11,
              fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-secondary)',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'metrics' && <MetricsTab card={card} />}
        {activeTab === 'seo' && <SEOTab metadata={metadata} onChange={onMetadataChange} />}
        {activeTab === 'links' && <LinksTab card={card} />}
        {activeTab === 'export' && <ExportTab onPublish={onPublish} />}
      </div>
    </div>
  );
}
