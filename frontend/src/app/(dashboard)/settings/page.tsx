'use client';

import { useSearchParams, useRouter } from 'next/navigation';
import { Suspense } from 'react';
import { TabBar } from '@/components/ui';
import { TeamTab } from './_components/TeamTab';
import { ProfileTab } from './_components/ProfileTab';
import { PipelineDefaultsTab } from './_components/PipelineDefaultsTab';
import { ModelsTab } from './_components/ModelsTab';
import { IntegrationsTab } from './_components/IntegrationsTab';
import { BillingTab } from './_components/BillingTab';
import { NotificationsTab } from './_components/NotificationsTab';

const tabs = [
  { id: 'team', label: 'Team' },
  { id: 'profile', label: 'Profile' },
  { id: 'pipeline', label: 'Pipeline Defaults' },
  { id: 'models', label: 'Models & API Keys' },
  { id: 'integrations', label: 'Integrations' },
  { id: 'billing', label: 'Billing' },
  { id: 'notifications', label: 'Notifications' },
];

function SettingsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeTab = searchParams.get('tab') || 'team';

  const handleTabClick = (id: string) => {
    router.push(`/settings?tab=${id}`);
  };

  return (
    <div className="space-y-5">
      <TabBar tabs={tabs} activeTab={activeTab} onTabClick={handleTabClick} className="text-[13px]" />
      {activeTab === 'team' && <TeamTab />}
      {activeTab === 'profile' && <ProfileTab />}
      {activeTab === 'pipeline' && <PipelineDefaultsTab />}
      {activeTab === 'models' && <ModelsTab />}
      {activeTab === 'integrations' && <IntegrationsTab />}
      {activeTab === 'billing' && <BillingTab />}
      {activeTab === 'notifications' && <NotificationsTab />}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense>
      <SettingsContent />
    </Suspense>
  );
}
