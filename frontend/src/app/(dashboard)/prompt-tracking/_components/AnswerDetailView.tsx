'use client';

import { cn } from '@/lib/utils';
import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import type { Platform } from '@/types';
import type { AnswerHistoryRow } from '../_lib/types';
import { PLATFORM_MAP } from '../_lib/adapters';
import { BrandLogo } from '@/components/ui';

interface AnswerDetailViewProps {
  promptText: string;
  promptId: string;
  answer: AnswerHistoryRow;
  answerHistory: AnswerHistoryRow[];
  brandName: string;
  onBack: () => void;
}

export function AnswerDetailView({ promptText, promptId, answer, answerHistory, brandName, onBack }: AnswerDetailViewProps) {
  const [activePlatform, setActivePlatform] = useState<Platform>(answer.platform);

  // Use the answerHistory prop directly instead of fetching from mock data
  const allAnswers = answerHistory;
  const sameDateAnswers = allAnswers.filter((a) => a.date === answer.date);
  const currentAnswer = sameDateAnswers.find((a) => a.platform === activePlatform) || answer;

  const platforms: Platform[] = ['chatgpt', 'perplexity', 'google_ai_overview', 'gemini'];

  // Derive the brand's own citation domain from mentionedBrands (checked === true)
  const brandCitationDomain = currentAnswer.mentionedBrands.find((b) => b.checked)?.domain ?? '';

  // Highlight brand name in answer text with spec-exact teal background
  function renderAnswer(text: string, brand: string): React.ReactNode {
    const escaped = brand.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const parts = text.split(new RegExp(`(\\*\\*${escaped}\\*\\*|${escaped})`, 'gi'));
    return parts.map((part, i) => {
      if (part.replace(/\*\*/g, '').toLowerCase() === brand.toLowerCase()) {
        return (
          <span
            key={i}
            style={{
              background: 'rgba(108, 184, 210, 0.15)',
              fontWeight: 600,
              padding: '1px 4px',
              borderRadius: 2,
            }}
          >
            {brand}
          </span>
        );
      }
      // Strip remaining markdown bold
      return <span key={i}>{part.replace(/\*\*(.*?)\*\*/g, '$1')}</span>;
    });
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid var(--border)' }}>
        {/* Back link: 12px, var(--text-secondary), hover underline */}
        <button
          onClick={onBack}
          className="cursor-pointer"
          style={{
            fontSize: 12,
            color: 'var(--text-secondary)',
            background: 'none',
            border: 'none',
            padding: 0,
            marginBottom: 12,
            display: 'block',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
          onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
        >
          <ArrowLeft size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />Back
        </button>

        {/* Overline */}
        <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 4 }}>
          Prompt
        </div>
        <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.3, paddingRight: 32 }}>
          &ldquo;{promptText}&rdquo;
        </div>

        {/* Platform tabs: real favicon + name, selected = accent bottom border */}
        <div style={{ display: 'flex', gap: 0, marginTop: 12, borderBottom: '1px solid var(--border)' }}>
          {platforms.map((p) => {
            const info = PLATFORM_MAP[p];
            const isActive = activePlatform === p;
            return (
              <button
                key={p}
                onClick={() => setActivePlatform(p)}
                className="cursor-pointer"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 12px',
                  fontSize: 12,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: 'none',
                  border: 'none',
                  borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                  marginBottom: -1,
                  transition: 'color 0.12s',
                }}
              >
                <BrandLogo domain={info.domain} size={14} />
                {info.label}
              </button>
            );
          })}
        </div>

        {/* Meta line */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
          <span>🧑 {currentAnswer.persona}</span>
          <span>·</span>
          <span>🌐 United States</span>
          <span>·</span>
          <span>📅 {currentAnswer.date}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto" style={{ padding: 16 }}>
        {/* Brand Status Line: ✅ pill green, ✗ gray */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          {currentAnswer.mentioned ? (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontSize: 13, fontWeight: 500,
              background: 'var(--success-subtle)', color: 'var(--success)',
              padding: '4px 10px', borderRadius: 'var(--radius-full)',
            }}>
              ✅ {brandName} is mentioned
            </span>
          ) : (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontSize: 13,
              color: 'var(--text-secondary)',
            }}>
              ✗ {brandName} is not mentioned
            </span>
          )}
          {currentAnswer.cited ? (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontSize: 13, fontWeight: 500,
              background: 'var(--success-subtle)', color: 'var(--success)',
              padding: '4px 10px', borderRadius: 'var(--radius-full)',
            }}>
              ✅ {brandName} is cited
            </span>
          ) : (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontSize: 13,
              color: 'var(--text-secondary)',
            }}>
              ✗ {brandName} is not cited
            </span>
          )}
        </div>

        {/* Mentions: horizontal pills, 28px height, 11px text, 12px favicon */}
        {currentAnswer.mentionedBrands.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 6 }}>
              Mentions
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {currentAnswer.mentionedBrands.map((brand) => (
                <span
                  key={brand.domain}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    height: 28,
                    padding: '0 8px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 11,
                    color: 'var(--text-primary)',
                  }}
                >
                  <BrandLogo domain={brand.domain} size={12} />
                  {brand.name}
                  {brand.checked && <span style={{ color: 'var(--success)', fontSize: 12, marginLeft: 2 }}>✓</span>}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Citations: same pill style, domain favicon + domain name */}
        {currentAnswer.citations.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 6 }}>
              Citations ({currentAnswer.citations.length})
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {currentAnswer.citations.map((domain, i) => (
                <span
                  key={`${domain}-${i}`}
                  className={cn(domain === brandCitationDomain && 'font-medium')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    height: 28,
                    padding: '0 8px',
                    border: `1px solid ${domain === brandCitationDomain ? 'var(--accent)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 11,
                    color: 'var(--text-primary)',
                    background: domain === brandCitationDomain ? 'var(--accent-subtle)' : 'transparent',
                  }}
                >
                  <BrandLogo domain={domain} size={12} />
                  {domain}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Full Answer: bordered card, 13px, line-height 1.6 */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 6 }}>
            Full Answer
          </div>
          <div style={{
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: 16,
          }}>
            {currentAnswer.fullAnswer ? (
              <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)', whiteSpace: 'pre-line' }}>
                {renderAnswer(currentAnswer.fullAnswer, brandName)}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                Response text no longer available (older than 30 days)
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
