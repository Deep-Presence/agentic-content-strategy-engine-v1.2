'use client';

import Link from 'next/link';
import { Search, FileText, Dna, Brain } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { LucideIcon } from 'lucide-react';

interface QuickLink {
  label: string;
  description: string;
  href: string;
  icon: LucideIcon;
  accent: string;
  iconColor: string;
}

const LINKS: QuickLink[] = [
  {
    label: 'Run Gap Analysis',
    description: 'Launch 8-step AI citation analysis',
    href: '/signal-analysis/run',
    icon: Search,
    accent: 'border-l-3 border-l-terracotta-400',
    iconColor: 'text-terracotta-400',
  },
  {
    label: 'Generate Content',
    description: 'Create AI-optimized briefs from gaps',
    href: '/content-pipeline',
    icon: FileText,
    accent: 'border-l-3 border-l-sage-400',
    iconColor: 'text-sage-400',
  },
  {
    label: 'Explore Embeddings',
    description: 'Visualize citation patterns in space',
    href: '/embedding-lab',
    icon: Dna,
    accent: 'border-l-3 border-l-ocean-400',
    iconColor: 'text-ocean-400',
  },
  {
    label: 'Brand Brain',
    description: 'Personas, projects, knowledge base',
    href: '/brand-brain',
    icon: Brain,
    accent: 'border-l-3 border-l-cream-500',
    iconColor: 'text-cream-700',
  },
];

export function QuickLinksFooter() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {LINKS.map((link, i) => (
        <Link key={link.href} href={link.href}>
          <Card
            hoverable
            className={`${link.accent} animate-fade-in-up h-full`}
            style={{ animationDelay: `${0.55 + i * 0.06}s` }}
          >
            <CardContent className="p-4">
              <link.icon className={`h-5 w-5 ${link.iconColor} mb-2`} />
              <p className="font-sans text-body-sm font-semibold text-cream-950">
                {link.label}
              </p>
              <p className="text-caption text-cream-600 mt-0.5">
                {link.description}
              </p>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
