import {
  LayoutDashboard,
  Search,
  Dna,
  FileText,
  Brain,
  Settings,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  section?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Mission Control', href: '/command-center', icon: LayoutDashboard },
  { label: 'Deep Signal Analysis', href: '/signal-analysis', icon: Search, section: 'Intelligence' },
  { label: 'Deep Embedding Lab', href: '/embedding-lab', icon: Dna, section: 'Intelligence' },
  { label: 'Content Pipeline', href: '/content-pipeline', icon: FileText, section: 'Content' },
  { label: 'Brand Brain', href: '/brand-brain', icon: Brain, section: 'Content' },
  { label: 'Settings', href: '/settings', icon: Settings, section: 'System' },
] as const;

export const STATUS_COLORS = {
  pending: 'bg-cream-400 text-cream-800',
  running: 'bg-ocean-50 text-ocean-500',
  completed: 'bg-sage-50 text-sage-500',
  failed: 'bg-error/10 text-error',
  cancelled: 'bg-cream-300 text-cream-700',
  pending_approval: 'bg-terracotta-50 text-terracotta-500',
  failed_restart: 'bg-error/10 text-error',
} as const;

export const CONTENT_TYPE_LABELS = {
  blog: 'Blog Post',
  guide: 'Guide',
  case_study: 'Case Study',
  product_page: 'Product Page',
} as const;

export const PIPELINE_LABELS = {
  research: 'Research',
  gap_analysis: 'Gap Analysis',
  content: 'Content Generation',
} as const;
