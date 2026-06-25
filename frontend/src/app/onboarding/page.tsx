'use client';

import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LocusLogo } from '@/components/ui';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { useAuth } from '@/hooks/useAuth';
import { ScreenInput } from './_components/ScreenInput';
import { ScreenModelConfig } from './_components/ScreenModelConfig';
import { ScreenBriefing } from './_components/ScreenBriefing';
import { ScreenPipeline } from './_components/ScreenPipeline';
import { ScreenComplete } from './_components/ScreenComplete';

type Screen = 'input' | 'models' | 'briefing' | 'pipeline' | 'complete';

interface OnboardingFormData {
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
  return (
    <AuthGuard>
      <OnboardingFlow />
    </AuthGuard>
  );
}

function OnboardingFlow() {
  const {
    activeWorkspaceSlug,
    companyName,
    companyDomain,
    hasRole,
  } = useAuth();
  const [screen, setScreen] = useState<Screen>('input');
  const [formData, setFormData] = useState<OnboardingFormData | null>(null);

  const startPayload = useMemo(() => {
    const audience = formData?.audience.trim();
    return {
      workspace_slug: activeWorkspaceSlug,
      industry: formData?.industry || null,
      seed_personas: audience ? [audience] : [],
      language: 'en',
    };
  }, [activeWorkspaceSlug, formData]);

  const handleInputNext = (data: OnboardingFormData) => {
    setFormData(data);
    setScreen('models');
  };

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Top bar with compact logo */}
      <div className="px-6 py-4">
        <LocusLogo variant="compact" />
      </div>

      {/* Content */}
      <div className="flex-1 flex items-start justify-center px-6 py-8">
        <AnimatePresence mode="wait">
          {screen === 'input' && (
            <motion.div
              key="input"
              className="w-full"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <ScreenInput
                initialCompanyName={companyName}
                initialWebsiteUrl={companyDomain}
                onNext={handleInputNext}
              />
            </motion.div>
          )}

          {screen === 'models' && (
            <motion.div
              key="models"
              className="w-full"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <ScreenModelConfig
                workspaceSlug={activeWorkspaceSlug}
                canManageModels={hasRole('superuser')}
                onContinue={() => setScreen('briefing')}
              />
            </motion.div>
          )}

          {screen === 'briefing' && (
            <motion.div
              key="briefing"
              className="w-full"
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
              className="w-full"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <ScreenPipeline
                workspaceSlug={activeWorkspaceSlug}
                startPayload={startPayload}
                onBackToConfig={() => setScreen('models')}
                onComplete={() => setScreen('complete')}
              />
            </motion.div>
          )}

          {screen === 'complete' && (
            <motion.div
              key="complete"
              className="w-full"
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
        {(['input', 'models', 'briefing', 'pipeline', 'complete'] as Screen[]).map((s) => (
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
