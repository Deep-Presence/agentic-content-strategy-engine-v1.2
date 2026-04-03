'use client';

import { useState } from 'react';
import { Card, Badge, Button } from '@/components/ui';
import {
  Globe,
  Upload,
  Palette,
  Type,
  Image,
  Loader2,
  RefreshCw,
  Plus,
  ExternalLink,
  CheckCircle,
  ChevronRight,
} from 'lucide-react';

type SetupStep = 'input' | 'crawling' | 'complete';

export function VisualBrandTab({ onBack }: { onBack: () => void }) {
  const [setupStep, setSetupStep] = useState<SetupStep>('input');
  const [brandUrl, setBrandUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleCrawl = () => {
    if (!brandUrl) return;
    setIsLoading(true);
    setSetupStep('crawling');
    // Simulate crawl — in production this calls the backend
    setTimeout(() => {
      setIsLoading(false);
      setSetupStep('complete');
    }, 3000);
  };

  if (setupStep === 'complete') {
    return <VisualBrandContent onRecrawl={() => setSetupStep('input')} />;
  }

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 mb-4 text-[12px]">
        <button onClick={onBack} className="text-text-secondary hover:text-accent cursor-pointer transition-colors">
          Brand Artifact
        </button>
        <ChevronRight size={11} strokeWidth={1.5} className="text-text-tertiary" />
        <span className="text-text-primary font-medium">Visual Brand</span>
      </nav>

      {/* Section Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-md bg-warning-subtle flex items-center justify-center">
          <Palette size={18} strokeWidth={1.5} className="text-warning" />
        </div>
        <div>
          <h2 className="font-display text-[16px] font-semibold tracking-[-0.01em] text-text-primary">
            Visual Brand Guidelines
          </h2>
          <div className="text-[13px] text-text-secondary mt-0.5">
            Extract and manage your brand&apos;s visual identity for AI-generated content
          </div>
        </div>
      </div>

      {/* Setup Card */}
      <Card className="max-w-[640px] mx-auto mt-8 !p-8">
        <div className="text-center mb-6">
          <div className="w-16 h-16 rounded-full bg-warning-subtle flex items-center justify-center mx-auto mb-4">
            {isLoading ? (
              <Loader2 size={28} strokeWidth={1.5} className="text-warning animate-spin" />
            ) : (
              <Globe size={28} strokeWidth={1.5} className="text-warning" />
            )}
          </div>
          <h3 className="font-display text-[18px] font-semibold text-text-primary mb-2">
            {isLoading ? 'Extracting brand assets...' : 'Connect your brand'}
          </h3>
          <p className="text-[14px] text-text-secondary leading-[1.6] max-w-[440px] mx-auto">
            {isLoading
              ? 'We\'re crawling your website to extract colors, fonts, logos, and visual patterns. This usually takes 30-60 seconds.'
              : 'Enter your website URL and we\'ll crawl it to extract your brand colors, typography, logos, and visual guidelines automatically.'
            }
          </p>
        </div>

        {!isLoading && (
          <>
            {/* URL Input */}
            <div className="mb-4">
              <label className="block text-[12px] font-medium text-text-primary mb-1.5">
                Website URL
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  placeholder="https://yourcompany.com"
                  value={brandUrl}
                  onChange={e => setBrandUrl(e.target.value)}
                  className="flex-1 h-[36px] px-3 text-[13px] border border-border rounded-md bg-surface text-text-primary outline-none focus:border-accent placeholder:text-text-tertiary"
                />
                <Button variant="primary" size="lg" onClick={handleCrawl}>
                  <Globe size={14} strokeWidth={1.5} className="mr-1.5" />
                  Extract Brand
                </Button>
              </div>
            </div>

            {/* Divider */}
            <div className="flex items-center gap-3 my-5">
              <div className="flex-1 border-t border-border" />
              <span className="text-[11px] text-text-tertiary uppercase tracking-[0.08em]">or</span>
              <div className="flex-1 border-t border-border" />
            </div>

            {/* Manual Upload */}
            <div className="border-2 border-dashed border-border rounded-md p-6 text-center hover:border-border-strong transition-colors cursor-pointer">
              <Upload size={24} strokeWidth={1.5} className="text-text-tertiary mx-auto mb-2" />
              <p className="text-[13px] font-medium text-text-primary mb-1">Upload brand guidelines</p>
              <p className="text-[12px] text-text-tertiary">
                PDF, PNG, SVG, or brand book files &middot; Max 50MB
              </p>
            </div>

            {/* Supported formats */}
            <div className="mt-4 flex items-center justify-center gap-2">
              <span className="text-[11px] text-text-tertiary">Supported:</span>
              {['PDF', 'PNG', 'SVG', 'AI', 'Figma'].map(fmt => (
                <Badge key={fmt} variant="neutral">{fmt}</Badge>
              ))}
            </div>
          </>
        )}

        {isLoading && (
          <div className="space-y-3">
            {['Discovering pages', 'Extracting color palette', 'Identifying typography', 'Finding logos & assets'].map((step, i) => (
              <div key={step} className="flex items-center gap-3 px-3 py-2 rounded-md bg-bg">
                {i < 2 ? (
                  <CheckCircle size={14} strokeWidth={1.5} className="text-success" />
                ) : (
                  <Loader2 size={14} strokeWidth={1.5} className="text-text-tertiary animate-spin" />
                )}
                <span className={`text-[13px] ${i < 2 ? 'text-text-primary' : 'text-text-secondary'}`}>
                  {step}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// Full visual brand content view (shown after crawl or when data exists)
function VisualBrandContent({ onRecrawl }: { onRecrawl: () => void }) {
  // Mock brand data — in production this comes from the backend
  const brandColors = [
    { name: 'Primary', hex: '#5BA4C4', usage: 'CTA buttons, links, active states' },
    { name: 'Secondary', hex: '#1A1A2E', usage: 'Headlines, body text' },
    { name: 'Accent', hex: '#E8B931', usage: 'Highlights, badges, warnings' },
    { name: 'Background', hex: '#F8FAFC', usage: 'Page backgrounds, cards' },
    { name: 'Surface', hex: '#FFFFFF', usage: 'Card surfaces, modals' },
    { name: 'Border', hex: '#E2E8F0', usage: 'Dividers, card borders' },
  ];

  const fonts = [
    { name: 'Space Grotesk', role: 'Display & Body', weights: ['400', '500', '600'], sample: 'The quick brown fox jumps over the lazy dog' },
    { name: 'JetBrains Mono', role: 'Code & Data', weights: ['400', '500'], sample: 'const value = 42; // monospace' },
  ];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md bg-warning-subtle flex items-center justify-center">
            <Palette size={18} strokeWidth={1.5} className="text-warning" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-[16px] font-semibold tracking-[-0.01em] text-text-primary">
                Visual Brand Guidelines
              </h2>
              <Badge variant="info">v1.0</Badge>
            </div>
            <div className="text-[12px] text-text-tertiary mt-0.5">
              Extracted from lovable.dev &middot; Mar 24, 2026
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary">
            <Upload size={13} strokeWidth={1.5} className="mr-1.5" />
            Upload Assets
          </Button>
          <Button variant="secondary" onClick={onRecrawl}>
            <RefreshCw size={13} strokeWidth={1.5} className="mr-1.5" />
            Re-crawl
          </Button>
        </div>
      </div>

      <div className="space-y-5">
        {/* Color Palette */}
        <Card className="!p-5">
          <div className="flex items-center gap-2 mb-4">
            <Palette size={14} strokeWidth={1.5} className="text-warning" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">
              Color Palette
            </span>
            <Button variant="ghost" size="sm" className="ml-auto">
              <Plus size={12} strokeWidth={1.5} className="mr-1" />
              Add Color
            </Button>
          </div>
          <div className="grid grid-cols-6 gap-3">
            {brandColors.map(color => (
              <div key={color.name} className="group">
                <div
                  className="h-20 rounded-md border border-border mb-2 cursor-pointer group-hover:ring-2 ring-accent ring-offset-2 transition-all"
                  style={{ backgroundColor: color.hex }}
                />
                <div className="text-[13px] font-medium text-text-primary">{color.name}</div>
                <div className="text-[11px] font-mono text-text-tertiary">{color.hex}</div>
                <div className="text-[11px] text-text-tertiary mt-0.5 line-clamp-1">{color.usage}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Typography */}
        <Card className="!p-5">
          <div className="flex items-center gap-2 mb-4">
            <Type size={14} strokeWidth={1.5} className="text-info" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">
              Typography
            </span>
          </div>
          <div className="space-y-4">
            {fonts.map(font => (
              <div key={font.name} className="border border-border rounded-md p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-[15px] font-semibold text-text-primary">{font.name}</div>
                    <div className="text-[12px] text-text-tertiary">{font.role}</div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {font.weights.map(w => (
                      <Badge key={w} variant="neutral">{w}</Badge>
                    ))}
                  </div>
                </div>
                <div
                  className="text-[20px] text-text-secondary leading-[1.4]"
                  style={{ fontFamily: font.name === 'JetBrains Mono' ? 'var(--font-code)' : 'var(--font-body)' }}
                >
                  {font.sample}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Logo & Assets */}
        <Card className="!p-5">
          <div className="flex items-center gap-2 mb-4">
            <Image size={14} strokeWidth={1.5} className="text-success" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-tertiary">
              Logos & Brand Assets
            </span>
            <Button variant="ghost" size="sm" className="ml-auto">
              <Upload size={12} strokeWidth={1.5} className="mr-1" />
              Upload
            </Button>
          </div>
          <div className="border-2 border-dashed border-border rounded-md p-8 text-center">
            <Image size={32} strokeWidth={1} className="text-text-tertiary mx-auto mb-3" />
            <p className="text-[14px] font-medium text-text-primary mb-1">No logos uploaded yet</p>
            <p className="text-[13px] text-text-tertiary mb-4">
              Upload your logo variants (light, dark, icon) for use in generated content
            </p>
            <Button variant="secondary">
              <Upload size={13} strokeWidth={1.5} className="mr-1.5" />
              Upload Logo Files
            </Button>
          </div>
        </Card>

        {/* Source */}
        <div className="flex items-center justify-between px-1 text-[12px] text-text-tertiary">
          <span className="flex items-center gap-1.5">
            <Globe size={12} strokeWidth={1.5} />
            Source: lovable.dev
          </span>
          <span className="flex items-center gap-1.5">
            <ExternalLink size={12} strokeWidth={1.5} />
            View original site
          </span>
        </div>
      </div>
    </div>
  );
}
