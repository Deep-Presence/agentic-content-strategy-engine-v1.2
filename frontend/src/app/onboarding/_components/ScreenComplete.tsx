'use client';

import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { Button, LocusLogo } from '@/components/ui';

const METRICS = [
  { label: 'AI Presence Score', value: '38.7/100' },
  { label: 'Queries Tracked', value: '99' },
  { label: 'Citations Analyzed', value: '1,816' },
  { label: 'Content Clusters', value: '9' },
];

export function ScreenComplete() {
  const router = useRouter();

  return (
    <div className="max-w-[520px] mx-auto text-center">
      <motion.div
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="mb-8 inline-flex"
      >
        <LocusLogo variant="symbol" size={80} animated className="text-accent" />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
      >
        <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
          Analysis complete
        </h1>
        <p className="text-[14px] text-text-secondary mb-8 leading-[1.6]">
          Your brand intelligence is ready. Here&apos;s a snapshot.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.4 }}
        className="grid grid-cols-2 gap-3 mb-8"
      >
        {METRICS.map((m) => (
          <div key={m.label} className="bg-surface border border-border rounded-md p-4">
            <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
              {m.label}
            </p>
            <p className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary">
              {m.value}
            </p>
          </div>
        ))}
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
      >
        <Button
          variant="primary"
          className="w-full h-[40px] text-[14px]"
          onClick={() => router.push('/')}
        >
          Enter Home &rarr;
        </Button>
      </motion.div>
    </div>
  );
}
