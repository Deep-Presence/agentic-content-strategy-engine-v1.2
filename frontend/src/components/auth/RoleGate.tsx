'use client';

/**
 * RoleGate — conditional render based on user role.
 *
 * Usage:
 *   <RoleGate minRole="superuser">
 *     <Button>Invite Team Member</Button>
 *   </RoleGate>
 */

import { useAuth } from '@/hooks/useAuth';
import type { UserRole } from '@/lib/auth/types';

interface RoleGateProps {
  minRole: UserRole;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGate({ minRole, children, fallback = null }: RoleGateProps) {
  const { hasRole } = useAuth();
  return hasRole(minRole) ? <>{children}</> : <>{fallback}</>;
}
