'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LocusLogo } from '@/components/ui';
import { ScreenInput } from './_components/ScreenInput';
import { ScreenBriefing } from './_components/ScreenBriefing';
import { ScreenPipeline } from './_components/ScreenPipeline';
import { ScreenComplete } from './_components/ScreenComplete';

type Screen = 'input' | 'briefing' | 'pipeline' | 'complete';

const pageVariants = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
};

export default function OnboardingPage() {
  const [screen, setScreen] = useState<Screen>('input');

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Top bar with compact logo */}
      <div className="px-6 py-4">
        <LocusLogo variant="compact" />
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-6 py-8">
        <AnimatePresence mode="wait">
          {screen === 'input' && (
            <motion.div
              key="input"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <ScreenInput onNext={() => setScreen('briefing')} />
            </motion.div>
          )}

          {screen === 'briefing' && (
            <motion.div
              key="briefing"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <ScreenBriefing onStart={() => setScreen('pipeline')} />
            </motion.div>
          )}

          {screen === 'pipeline' && (
            <motion.div
              key="pipeline"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <ScreenPipeline onComplete={() => setScreen('complete')} />
            </motion.div>
          )}

          {screen === 'complete' && (
            <motion.div
              key="complete"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <ScreenComplete />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Step indicator */}
      <div className="flex items-center justify-center gap-2 pb-6">
        {(['input', 'briefing', 'pipeline', 'complete'] as Screen[]).map((s) => (
          <div
            key={s}
            className={`w-2 h-2 rounded-full transition-colors duration-300 ${
              s === screen ? 'bg-accent' : 'bg-border-strong'
            }`}
          />
        ))}
      </div>
    </div>
  );
}
