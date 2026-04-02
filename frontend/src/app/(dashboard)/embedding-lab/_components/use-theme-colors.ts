'use client';

import { useMemo } from 'react';
import { useThemeStore } from '@/stores/theme';

/**
 * Returns resolved color values for use in Canvas/D3 contexts
 * where CSS variables don't apply directly. Reactive to theme changes.
 */
export function useThemeColors() {
  const { mode } = useThemeStore();
  const isDark = mode === 'dark';

  return useMemo(() => ({
    isDark,
    bg: isDark ? '#171717' : '#F8F9FA',
    surface: isDark ? '#1F1F1F' : '#FBFCFD',
    surfaceRaised: isDark ? '#292929' : '#FFFFFF',
    surfaceOverlay: isDark ? '#242424' : '#FBFCFD',
    border: isDark ? '#2E2E2E' : '#ECEEF0',
    borderSubtle: isDark ? '#242424' : '#F1F3F5',
    borderStrong: isDark ? '#3E3E3E' : '#D7DBDF',
    textPrimary: isDark ? '#EDEDED' : '#11181C',
    textSecondary: isDark ? '#A0A0A0' : '#687076',
    textTertiary: isDark ? '#707070' : '#889096',
    accent: isDark ? '#6CB8D2' : '#5BA4C4',
    accentHover: isDark ? '#7CC8E2' : '#4A93B3',
    accentSubtle: isDark ? 'rgba(108,184,210,0.1)' : 'rgba(91,164,196,0.08)',
    success: isDark ? '#3ECF8E' : '#34B27B',
    warning: isDark ? '#FFB224' : '#DC7B18',
    error: isDark ? '#F87171' : '#E5484D',
  }), [isDark]);
}
