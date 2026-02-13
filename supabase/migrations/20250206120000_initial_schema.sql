-- Core extensions
create extension if not exists "pgcrypto";
create extension if not exists "vector";
-- Enumerated types for strongly-typed fields
do $$
begin
  if not exists (select 1 from pg_type where typname = 'artifact_type') then
    create type public.artifact_type as enum ('company_context', 'persona', 'guidelines', 'research', 'other');
  end if;
end$$;
do $$
begin
  if not exists (select 1 from pg_type where typname = 'content_asset_type') then
    create type public.content_asset_type as enum ('brief', 'draft', 'image', 'meta_description', 'other');
  end if;
end$$;
do $$
begin
  if not exists (select 1 from pg_type where typname = 'workflow_type') then
    create type public.workflow_type as enum ('onboarding', 'campaign', 'refresh');
  end if;
end$$;
-- Ensure public.users has the expected shape (prefer altering existing table)
do $$
declare
  users_reg regclass := to_regclass('public.users');
begin
  if users_reg is null then
    create table public.users (
      id uuid primary key references auth.users (id) on delete cascade,
      email text not null unique,
      role text not null default 'member',
      status text not null default 'active',
      profile_meta jsonb not null default '{}'::jsonb,
      created_at timestamptz not null default now()
    );
  else
    if not exists (
      select 1 from information_schema.columns
      where table_schema = 'public' and table_name = 'users' and column_name = 'id'
    ) then
      alter table public.users add column id uuid;
    end if;
    if not exists (
      select 1 from information_schema.columns
      where table_schema = 'public' and table_name = 'users' and column_name = 'email'
    ) then
      alter table public.users add column email text;
    end if;
    if not exists (
      select 1 from information_schema.columns
      where table_schema = 'public' and table_name = 'users' and column_name = 'role'
    ) then
      alter table public.users add column role text;
    end if;
    if not exists (
      select 1 from information_schema.columns
      where table_schema = 'public' and table_name = 'users' and column_name = 'status'
    ) then
      alter table public.users add column status text;
    end if;
    if not exists (
      select 1 from information_schema.columns
      where table_schema = 'public' and table_name = 'users' and column_name = 'profile_meta'
    ) then
      alter table public.users add column profile_meta jsonb;
    end if;
    if not exists (
      select 1 from information_schema.columns
      where table_schema = 'public' and table_name = 'users' and column_name = 'created_at'
    ) then
      alter table public.users add column created_at timestamptz;
    end if;

    update public.users set role = coalesce(role, 'member');
    update public.users set status = coalesce(status, 'active');
    update public.users set profile_meta = coalesce(profile_meta, '{}'::jsonb);
    update public.users set created_at = coalesce(created_at, now());

    alter table public.users
      alter column role set default 'member',
      alter column role set not null,
      alter column status set default 'active',
      alter column status set not null,
      alter column profile_meta set default '{}'::jsonb,
      alter column profile_meta set not null,
      alter column created_at set default now(),
      alter column created_at set not null;

    alter table public.users alter column email set not null;
    if not exists (
      select 1 from pg_constraint
      where conrelid = users_reg
        and conname = 'users_email_key'
    ) then
      alter table public.users add constraint users_email_key unique (email);
    end if;

    if not exists (
      select 1 from pg_constraint
      where conrelid = users_reg
        and contype = 'p'
    ) then
      alter table public.users add primary key (id);
    end if;

    if not exists (
      select 1
      from pg_constraint c
      join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any (c.conkey)
      where c.conrelid = users_reg
        and c.contype in ('p','u')
        and a.attname = 'id'
    ) then
      create unique index users_id_key on public.users (id);
    end if;

    if not exists (
      select 1 from pg_constraint
      where conrelid = users_reg
        and conname = 'users_id_fkey'
    ) then
      alter table public.users
        add constraint users_id_fkey foreign key (id) references auth.users (id) on delete cascade;
    end if;
  end if;
end$$;
-- Companies (tenants)
create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  industry text,
  hq_location text,
  size text,
  supabase_org_id text,
  plan_tier text not null default 'free',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint companies_supabase_org_id_unique unique (supabase_org_id)
);
create table if not exists public.company_members (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies (id) on delete cascade,
  user_id uuid not null references public.users (id) on delete cascade,
  role text not null,
  invited_by uuid references public.users (id),
  status text not null default 'pending',
  permission_overrides jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint company_members_unique_member unique (company_id, user_id)
);
create index if not exists company_members_company_id_idx on public.company_members (company_id);
create index if not exists company_members_user_id_idx on public.company_members (user_id);
-- Sites owned by companies
create table if not exists public.sites (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies (id) on delete cascade,
  domain text not null,
  crawl_seed_url text,
  cms_type text,
  language text,
  status text not null default 'active',
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint sites_company_domain_unique unique (company_id, domain)
);
create index if not exists sites_company_id_idx on public.sites (company_id);
-- Agents registry
create table if not exists public.agents (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text not null,
  description text,
  default_model text,
  fallback_policy jsonb not null default '{}'::jsonb,
  enabled boolean not null default true,
  config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint agents_name_unique unique (name)
);
-- Site audits
create table if not exists public.site_audits (
  id uuid primary key default gen_random_uuid(),
  site_id uuid not null references public.sites (id) on delete cascade,
  initiated_by_user_id uuid references public.users (id),
  initiated_by_agent_id uuid references public.agents (id),
  status text not null default 'pending',
  score_overall numeric(5,2),
  tech_score numeric(5,2),
  content_score numeric(5,2),
  accessibility_score numeric(5,2),
  issues jsonb not null default '[]'::jsonb,
  raw_report_path text,
  created_at timestamptz not null default now(),
  constraint site_audits_initiator_check check (
    initiated_by_user_id is not null or initiated_by_agent_id is not null
  )
);
create index if not exists site_audits_site_id_idx on public.site_audits (site_id);
-- Artifacts (living documents)
create table if not exists public.artifacts (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies (id) on delete cascade,
  type public.artifact_type not null,
  title text not null,
  status text not null default 'active',
  version integer not null default 1,
  content jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  source text not null default 'manual',
  last_regenerated_by uuid references public.agents (id),
  created_at timestamptz not null default now()
);
create index if not exists artifacts_company_id_idx on public.artifacts (company_id);
create index if not exists artifacts_embedding_ivfflat_idx on public.artifacts using ivfflat (embedding vector_cosine_ops) with (lists = 100);
-- Knowledge chunks (for retrieval)
create table if not exists public.knowledge_chunks (
  id uuid primary key default gen_random_uuid(),
  artifact_id uuid not null references public.artifacts (id) on delete cascade,
  chunk_text text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  token_count integer,
  created_at timestamptz not null default now()
);
create index if not exists knowledge_chunks_artifact_id_idx on public.knowledge_chunks (artifact_id);
create index if not exists knowledge_chunks_embedding_ivfflat_idx on public.knowledge_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);
-- Workflows (end-to-end runs)
create table if not exists public.workflows (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies (id) on delete set null,
  site_id uuid references public.sites (id) on delete set null,
  type public.workflow_type not null,
  status text not null default 'pending',
  entry_artifact_id uuid references public.artifacts (id) on delete set null,
  north_star_score numeric(6,3),
  threshold_passed boolean,
  started_at timestamptz,
  completed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists workflows_company_id_idx on public.workflows (company_id);
create index if not exists workflows_site_id_idx on public.workflows (site_id);
-- Agent runs (execution traces)
create table if not exists public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents (id) on delete cascade,
  company_id uuid references public.companies (id) on delete set null,
  site_id uuid references public.sites (id) on delete set null,
  artifact_id uuid references public.artifacts (id) on delete set null,
  workflow_id uuid references public.workflows (id) on delete set null,
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending',
  latency_ms integer,
  token_usage_prompt integer,
  token_usage_completion integer,
  cost_usd numeric(12,6),
  error_detail text,
  created_at timestamptz not null default now()
);
create index if not exists agent_runs_agent_id_idx on public.agent_runs (agent_id);
create index if not exists agent_runs_workflow_id_idx on public.agent_runs (workflow_id);
-- Workflow steps (ordered steps per workflow)
create table if not exists public.workflow_steps (
  id uuid primary key default gen_random_uuid(),
  workflow_id uuid not null references public.workflows (id) on delete cascade,
  agent_id uuid references public.agents (id) on delete set null,
  sequence_no integer not null,
  depends_on_step_id uuid references public.workflow_steps (id),
  status text not null default 'pending',
  input_snapshot jsonb not null default '{}'::jsonb,
  output_snapshot jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint workflow_steps_sequence_unique unique (workflow_id, sequence_no)
);
create index if not exists workflow_steps_workflow_id_idx on public.workflow_steps (workflow_id);
-- Content assets (briefs, drafts, etc.)
create table if not exists public.content_assets (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies (id) on delete cascade,
  site_id uuid references public.sites (id) on delete set null,
  type public.content_asset_type not null,
  title text not null,
  status text not null default 'draft',
  current_version_id uuid,
  target_url text,
  topic_cluster text,
  metadata jsonb not null default '{}'::jsonb,
  cms_payload jsonb,
  created_at timestamptz not null default now()
);
create index if not exists content_assets_company_id_idx on public.content_assets (company_id);
create index if not exists content_assets_site_id_idx on public.content_assets (site_id);
-- Content versions (version history)
create table if not exists public.content_versions (
  id uuid primary key default gen_random_uuid(),
  content_asset_id uuid not null references public.content_assets (id) on delete cascade,
  version_no integer not null,
  created_by_user_id uuid references public.users (id),
  created_by_agent_id uuid references public.agents (id),
  body jsonb,
  summary text,
  embedding vector(1536),
  quality_score numeric(6,3),
  approved_by uuid references public.users (id),
  created_at timestamptz not null default now(),
  constraint content_versions_creator_check check (
    created_by_user_id is not null or created_by_agent_id is not null
  ),
  constraint content_versions_version_unique unique (content_asset_id, version_no)
);
create index if not exists content_versions_content_asset_id_idx on public.content_versions (content_asset_id);
create index if not exists content_versions_embedding_ivfflat_idx on public.content_versions using ivfflat (embedding vector_cosine_ops) with (lists = 100);
alter table public.content_assets
  add constraint content_assets_current_version_id_fkey
  foreign key (current_version_id) references public.content_versions (id);
-- Agent metrics (KPI per agent run)
create table if not exists public.agent_metrics (
  id uuid primary key default gen_random_uuid(),
  agent_run_id uuid not null references public.agent_runs (id) on delete cascade,
  metric_name text not null,
  metric_value double precision not null,
  unit text,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists agent_metrics_agent_run_id_idx on public.agent_metrics (agent_run_id);
-- Sandbox results (virtual evaluation outputs)
create table if not exists public.sandbox_results (
  id uuid primary key default gen_random_uuid(),
  workflow_id uuid references public.workflows (id) on delete set null,
  content_asset_id uuid references public.content_assets (id) on delete set null,
  agent_run_id uuid references public.agent_runs (id) on delete set null,
  llm_query text,
  predicted_visibility_score numeric(6,3),
  citation_prob numeric(6,3),
  confidence_interval jsonb,
  recommendation text,
  raw_log_path text,
  created_at timestamptz not null default now()
);
create index if not exists sandbox_results_workflow_id_idx on public.sandbox_results (workflow_id);
create index if not exists sandbox_results_content_asset_id_idx on public.sandbox_results (content_asset_id);
-- CMS jobs (publishing queue)
create table if not exists public.cms_jobs (
  id uuid primary key default gen_random_uuid(),
  content_asset_id uuid references public.content_assets (id) on delete cascade,
  cms_type text,
  target_endpoint text,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued',
  error_detail text,
  attempts integer not null default 0,
  scheduled_at timestamptz,
  published_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists cms_jobs_content_asset_id_idx on public.cms_jobs (content_asset_id);
-- LLM usage log (billing/governance)
create table if not exists public.llm_usage_log (
  id uuid primary key default gen_random_uuid(),
  agent_run_id uuid references public.agent_runs (id) on delete cascade,
  provider text,
  model text,
  tokens_prompt integer,
  tokens_completion integer,
  cost_usd numeric(12,6),
  latency_ms integer,
  cache_hit boolean,
  response_hash text,
  created_at timestamptz not null default now()
);
create index if not exists llm_usage_log_agent_run_id_idx on public.llm_usage_log (agent_run_id);
-- Audit findings (issues from site audits)
create table if not exists public.audit_findings (
  id uuid primary key default gen_random_uuid(),
  site_audit_id uuid not null references public.site_audits (id) on delete cascade,
  category text,
  severity text,
  description text,
  evidence text,
  recommendation text,
  status text not null default 'open',
  assigned_to uuid references public.users (id),
  resolved_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists audit_findings_site_audit_id_idx on public.audit_findings (site_audit_id);
-- Task queue (relational mirror)
create table if not exists public.task_queue (
  id uuid primary key default gen_random_uuid(),
  task_type text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued',
  priority integer not null default 0,
  agent_id uuid references public.agents (id) on delete set null,
  scheduled_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  error_detail text,
  created_at timestamptz not null default now()
);
create index if not exists task_queue_agent_id_idx on public.task_queue (agent_id);
create index if not exists task_queue_status_idx on public.task_queue (status);