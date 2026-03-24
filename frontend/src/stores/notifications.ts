import { create } from 'zustand';
import type { Notification } from '@/types';

interface NotificationState {
  items: Notification[];
  unreadCount: number;
  add: (notification: Notification) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  items: [],
  unreadCount: 0,
  add: (notification) => set((s) => ({
    items: [notification, ...s.items],
    unreadCount: s.unreadCount + 1,
  })),
  markRead: (id) => set((s) => ({
    items: s.items.map((n) => n.id === id ? { ...n, read: true } : n),
    unreadCount: Math.max(0, s.unreadCount - 1),
  })),
  markAllRead: () => set((s) => ({
    items: s.items.map((n) => ({ ...n, read: true })),
    unreadCount: 0,
  })),
}));
