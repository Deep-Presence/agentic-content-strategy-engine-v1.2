import { formatDistanceToNow, format, parseISO } from 'date-fns';

export function relativeTime(dateString: string): string {
  try {
    return formatDistanceToNow(parseISO(dateString), { addSuffix: true });
  } catch {
    return dateString;
  }
}

export function shortDate(dateString: string): string {
  try {
    return format(parseISO(dateString), 'MMM d, yyyy');
  } catch {
    return dateString;
  }
}

export function shortDateTime(dateString: string): string {
  try {
    return format(parseISO(dateString), 'MMM d, h:mm a');
  } catch {
    return dateString;
  }
}

export function formatPercent(value: number, decimals = 0): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatCompactNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toString();
}

export function scoreColor(score: number): string {
  if (score < 0.5) return 'text-error';
  if (score < 0.8) return 'text-warning';
  return 'text-sage-400';
}

export function scoreBgColor(score: number): string {
  if (score < 0.5) return 'bg-error/10';
  if (score < 0.8) return 'bg-warning/10';
  return 'bg-sage-50';
}
