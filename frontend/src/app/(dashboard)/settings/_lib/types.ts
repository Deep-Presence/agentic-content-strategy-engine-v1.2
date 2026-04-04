/**
 * Settings page types — mirrors backend schemas exactly.
 *
 * Backend schemas:
 *   api/schemas/settings.py   (team, profile, pipeline defaults)
 *   api/schemas/cms.py        (CMS connection)
 *   api/schemas/analytics.py  (GA4 analytics)
 */

// ── Team (from api/schemas/settings.py) ─────────────────

export type BackendRole = 'superuser' | 'member' | 'viewer';

export interface TeamMemberAPI {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: BackendRole;
  is_active: boolean;
  created_at: string;
}

export interface TeamListResponseAPI {
  members: TeamMemberAPI[];
  total: number;
}

export interface UpdateUserRequestAPI {
  role?: BackendRole;
  first_name?: string;
  last_name?: string;
  is_active?: boolean;
}

// ── CMS (from api/schemas/cms.py) ───────────────────────

export interface CMSConnectRequestAPI {
  provider: string;
  site_url: string;
  username: string;
  api_key: string;
}

export interface CMSConnectResponseAPI {
  connected: boolean;
  site_name: string;
  site_url: string;
  cms_version: string;
  user_display_name: string;
  error: string | null;
}

export interface CMSConnectionInfoAPI {
  provider: string;
  site_url: string;
  site_name: string;
  cms_version: string;
  user_display_name: string;
  is_active: boolean;
  last_sync_at: string | null;
  sync_post_count: number;
}

// ── GA4 Analytics (from api/schemas/analytics.py) ───────

export interface GA4AuthorizeResponseAPI {
  authorization_url: string;
}

export interface GA4ConnectionResponseAPI {
  provider: string;
  ga4_property_id: string;
  ga4_property_name: string;
  ga4_account_id: string;
  is_active: boolean;
  connected_at: string | null;
  last_sync_at: string | null;
  last_sync_status: string;
}

export interface GA4PropertyItemAPI {
  property_id: string;
  display_name: string;
  account_id: string;
  account_display_name: string;
}

export interface GA4PropertiesResponseAPI {
  properties: GA4PropertyItemAPI[];
}

export interface GA4SelectPropertyRequestAPI {
  property_id: string;
  property_name: string;
  account_id: string;
}

export interface GA4DisconnectResponseAPI {
  disconnected: boolean;
  data_purged: boolean;
  error: string | null;
}

export interface GA4SyncResponseAPI {
  run_id: string;
  pipeline: string;
  status: string;
  company_slug: string;
}

// ── Frontend display types ──────────────────────────────

export type FrontendRole = 'admin' | 'editor' | 'viewer';

export interface TeamMemberDisplay {
  id: string;
  name: string;
  email: string;
  role: FrontendRole;
  backendRole: BackendRole;
  status: 'active' | 'inactive';
  createdAt: string;
}

export type IntegrationStatus = 'connected' | 'disconnected' | 'pending' | 'coming_soon';

export type IntegrationCategory = 'cms' | 'crm' | 'analytics';

export interface IntegrationDef {
  id: string;
  name: string;
  description: string;
  domain: string;
  category: IntegrationCategory;
  available: boolean;
}
