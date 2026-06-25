'use client';

import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { Check } from 'lucide-react';
import { Button, LocusLogo } from '@/components/ui';

const DELIVERABLES = [
  'Site audit',
  'Knowledge base',
  'Audience personas',
  'Voice style guide',
  'Gap analysis',
  'Topic discovery',
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
          Onboarding complete
        </h1>
        <p className="text-[14px] text-text-secondary mb-8 leading-[1.6]">
          Your initial brand intelligence is ready.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.4 }}
        className="grid grid-cols-2 gap-2 mb-8 text-left"
      >
        {DELIVERABLES.map((item) => (
          <div key={item} className="flex items-center gap-2 bg-surface border border-border rounded-md p-3">
            <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-success-subtle text-success">
              <Check size={12} strokeWidth={2} />
            </span>
            <p className="text-[13px] font-medium text-text-primary">{item}</p>
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
