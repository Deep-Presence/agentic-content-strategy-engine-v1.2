'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LocusLogo } from '@/components/ui';
import { ScreenInput } from './_components/ScreenInput';
import { ScreenBriefing } from './_components/ScreenBriefing';
import { ScreenPipeline } from './_components/ScreenPipeline';
import { ScreenComplete } from './_components/ScreenComplete';
import { apiPost } from '@/lib/api/client';
import { ONBOARDING } from '@/lib/api/endpoints';

type Screen = 'input' | 'briefing' | 'pipeline' | 'complete';

export interface OnboardingFormData {
  companyName: string;
  websiteUrl: string;
  industry: string;
  audience: string;
}

const pageVariants = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
};

export default function OnboardingPage() {
  const [screen, setScreen] = useState<Screen>('input');
  const [formData, setFormData] = useState<OnboardingFormData | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const handleInputNext = (data: OnboardingFormData) => {
    setFormData(data);
    setScreen('briefing');
  };

  const handleStartAnalysis = async () => {
    if (!formData) return;
    setLaunchError(null);

    try {
      // Build seed_urls from websiteUrl
      const seedUrls: string[] = [];
      if (formData.websiteUrl) {
        let url = formData.websiteUrl;
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
          url = `https://${url}`;
        }
        seedUrls.push(url);
      }

      // Build seed_personas from audience text (split by newline or comma)
      const seedPersonas = formData.audience
        ? formData.audience.split(/[,\n]+/).map((s) => s.trim()).filter(Boolean)
        : [];

      const res = await apiPost<{ run_id: string }>(ONBOARDING.start, {
        industry: formData.industry || undefined,
        seed_urls: seedUrls,
        seed_personas: seedPersonas,
      });

      setTaskId(res.run_id);
      setScreen('pipeline');
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : 'Failed to start analysis');
    }
  };

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
              <ScreenInput onNext={handleInputNext} />
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
              <ScreenBriefing onStart={handleStartAnalysis} />
              {launchError && (
                <div className="mt-4 bg-error/10 border border-error/30 text-error text-[13px] rounded-md px-3 py-2">
                  {launchError}
                </div>
              )}
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
              <ScreenPipeline
                taskId={taskId}
                onComplete={() => setScreen('complete')}
              />
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
