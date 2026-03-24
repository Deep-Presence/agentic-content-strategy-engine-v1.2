'use client';

import { useState } from 'react';
import { Button, Toggle, Toast } from '@/components/ui';

interface NotificationPref {
  id: string;
  event: string;
  description: string;
  email: boolean;
  inApp: boolean;
}

const initialPrefs: NotificationPref[] = [
  { id: 'pipeline', event: 'Pipeline Complete', description: 'When a research or content pipeline finishes', email: true, inApp: true },
  { id: 'hitl', event: 'HITL Review Ready', description: 'When content is ready for human review', email: true, inApp: true },
  { id: 'published', event: 'Content Published', description: 'When content goes live on your site', email: false, inApp: true },
  { id: 'citation', event: 'New Citation Gained', description: 'When your content is cited by an AI engine', email: true, inApp: true },
  { id: 'alert', event: 'System Alert', description: 'Critical system notifications', email: true, inApp: true },
  { id: 'weekly', event: 'Weekly Digest', description: 'Weekly summary of citations and performance', email: true, inApp: false },
  { id: 'team', event: 'Team Activity', description: 'When team members make changes', email: false, inApp: true },
  { id: 'billing', event: 'Billing Events', description: 'Payment receipts and plan changes', email: true, inApp: false },
];

export function NotificationsTab() {
  const [prefs, setPrefs] = useState(initialPrefs);
  const [toast, setToast] = useState({ open: false, message: '' });

  const togglePref = (id: string, channel: 'email' | 'inApp') => {
    setPrefs(prefs.map((p) => (p.id === id ? { ...p, [channel]: !p[channel] } : p)));
  };

  const handleSave = () => {
    setToast({ open: true, message: 'Notification preferences saved' });
  };

  return (
    <div className="space-y-4">
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[16px] font-semibold text-text-primary mb-4">
          Notification Preferences
        </h3>
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-left py-[8px] px-[10px] border-b border-border">Event</th>
                <th className="text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-center py-[8px] px-[10px] border-b border-border w-[80px]">Email</th>
                <th className="text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-center py-[8px] px-[10px] border-b border-border w-[80px]">In-App</th>
              </tr>
            </thead>
            <tbody>
              {prefs.map((pref) => (
                <tr key={pref.id} className="hover:bg-accent-subtle transition-colors h-[44px]">
                  <td className="py-[10px] px-[10px] border-b border-border-subtle">
                    <div className="text-[13px] text-text-primary font-medium">{pref.event}</div>
                    <div className="text-[12px] text-text-tertiary">{pref.description}</div>
                  </td>
                  <td className="py-[10px] px-[10px] border-b border-border-subtle text-center">
                    <div className="flex justify-center">
                      <Toggle checked={pref.email} onChange={() => togglePref(pref.id, 'email')} />
                    </div>
                  </td>
                  <td className="py-[10px] px-[10px] border-b border-border-subtle text-center">
                    <div className="flex justify-center">
                      <Toggle checked={pref.inApp} onChange={() => togglePref(pref.id, 'inApp')} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-5">
          <Button onClick={handleSave} className="w-full">Save Preferences</Button>
        </div>
      </div>

      <Toast open={toast.open} onClose={() => setToast({ ...toast, open: false })} variant="success" message={toast.message} />
    </div>
  );
}
