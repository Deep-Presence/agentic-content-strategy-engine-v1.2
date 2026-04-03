'use client';

import { useState, useRef, useEffect } from 'react';
import { DayPicker } from 'react-day-picker';
import type { DateRange } from 'react-day-picker';
import { format, subDays, startOfMonth, startOfQuarter } from 'date-fns';
import { Calendar, ChevronDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export type { DateRange };

interface Preset {
  label: string;
  range: () => DateRange;
}

const DEFAULT_PRESETS: Preset[] = [
  { label: 'Last 7 days', range: () => ({ from: subDays(new Date(), 6), to: new Date() }) },
  { label: 'Last 30 days', range: () => ({ from: subDays(new Date(), 29), to: new Date() }) },
  { label: 'Last 90 days', range: () => ({ from: subDays(new Date(), 89), to: new Date() }) },
  { label: 'This month', range: () => ({ from: startOfMonth(new Date()), to: new Date() }) },
  { label: 'This quarter', range: () => ({ from: startOfQuarter(new Date()), to: new Date() }) },
];

interface DateRangePickerProps {
  value?: DateRange;
  onChange: (range: DateRange | undefined) => void;
  presets?: Preset[];
  placeholder?: string;
  className?: string;
  /** Disable dates after this date */
  maxDate?: Date;
  /** Disable dates before this date */
  minDate?: Date;
}

export function DateRangePicker({
  value,
  onChange,
  presets = DEFAULT_PRESETS,
  placeholder = 'Select date range',
  className,
  maxDate,
  minDate,
}: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  const displayText =
    value?.from && value?.to
      ? `${format(value.from, 'MMM d, yyyy')} – ${format(value.to, 'MMM d, yyyy')}`
      : value?.from
        ? `${format(value.from, 'MMM d, yyyy')} – ...`
        : placeholder;

  const hasValue = !!value?.from;

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'inline-flex items-center gap-2 h-[32px] px-3 rounded-sm border transition-colors cursor-pointer',
          'text-[13px] font-body',
          open
            ? 'border-accent bg-accent-subtle text-text-primary'
            : 'border-border bg-surface text-text-secondary hover:border-border-strong hover:text-text-primary',
        )}
      >
        <Calendar size={14} strokeWidth={1.5} className="shrink-0" />
        <span className="truncate">{displayText}</span>
        {hasValue ? (
          <X
            size={12}
            strokeWidth={1.5}
            className="shrink-0 text-text-tertiary hover:text-text-primary"
            onClick={(e) => {
              e.stopPropagation();
              onChange(undefined);
            }}
          />
        ) : (
          <ChevronDown size={12} strokeWidth={1.5} className="shrink-0" />
        )}
      </button>

      {/* Popover */}
      {open && (
        <div
          className={cn(
            'absolute top-[calc(100%+4px)] left-0 z-50',
            'bg-surface-raised border border-border rounded-md',
            'shadow-[var(--shadow-float)]',
            'flex',
          )}
        >
          {/* Presets sidebar */}
          {presets.length > 0 && (
            <div className="border-r border-border p-2 min-w-[140px]">
              <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary px-2 pb-1.5">
                Presets
              </div>
              {presets.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    onChange(preset.range());
                    setOpen(false);
                  }}
                  className={cn(
                    'w-full text-left px-2 py-1.5 rounded-sm text-[12px] font-body',
                    'text-text-secondary hover:bg-accent-subtle hover:text-text-primary',
                    'transition-colors cursor-pointer',
                  )}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          )}

          {/* Calendar */}
          <div className="p-3">
            <DayPicker
              mode="range"
              selected={value}
              onSelect={(range) => onChange(range)}
              numberOfMonths={2}
              disabled={[
                ...(maxDate ? [{ after: maxDate }] : []),
                ...(minDate ? [{ before: minDate }] : []),
              ]}
              classNames={{
                months: 'flex gap-4',
                month_caption: 'flex justify-center items-center h-8',
                caption_label: 'text-[13px] font-semibold text-text-primary font-body',
                nav: 'flex items-center',
                button_previous: cn(
                  'absolute left-3 top-3 size-7 inline-flex items-center justify-center',
                  'rounded-sm border border-border hover:bg-surface transition-colors cursor-pointer',
                  'text-text-secondary hover:text-text-primary',
                ),
                button_next: cn(
                  'absolute right-3 top-3 size-7 inline-flex items-center justify-center',
                  'rounded-sm border border-border hover:bg-surface transition-colors cursor-pointer',
                  'text-text-secondary hover:text-text-primary',
                ),
                weekday: 'text-[10px] font-semibold uppercase tracking-[0.04em] text-text-tertiary w-9 text-center font-body',
                day: 'size-9 text-center text-[12px] font-body',
                day_button: cn(
                  'size-9 inline-flex items-center justify-center rounded-sm',
                  'text-text-primary hover:bg-accent-subtle transition-colors cursor-pointer',
                ),
                selected: 'bg-accent text-text-on-accent hover:bg-accent-hover',
                range_start: 'bg-accent text-text-on-accent rounded-l-sm rounded-r-none',
                range_end: 'bg-accent text-text-on-accent rounded-r-sm rounded-l-none',
                range_middle: 'bg-accent-subtle text-text-primary rounded-none',
                today: 'font-semibold',
                disabled: 'text-text-tertiary opacity-40 cursor-not-allowed',
                outside: 'text-text-tertiary opacity-30',
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
