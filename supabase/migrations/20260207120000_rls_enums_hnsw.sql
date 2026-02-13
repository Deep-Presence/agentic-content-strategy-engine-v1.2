-- Switch vector indexes to HNSW, tighten enums/columns, add RLS/tenant policies, and add partial indexes.

-- Ensure vector extension exists
create extension if not exists "vector";

-- Drop legacy IVFFlat indexes if present (to replace with HNSW)
drop index if exists public.artifacts_embedding_ivfflat_idx;
drop index if exists public.knowledge_chunks_embedding_ivfflat_idx;
drop index if exists public.content_versions_embedding_ivfflat_idx;

-- Create HNSW indexes for embeddings
create index if not exists artifacts_embedding_hnsw_idx on public.artifacts using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);
create index if not exists knowledge_chunks_embedding_hnsw_idx on public.knowledge_chunks using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);
create index if not exists content_versions_embedding_hnsw_idx on public.content_versions using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);

-- Enumerations for roles/statuses
do $$ begin
  if not exists (select 1 from pg_type where typname = 'user_role') then
    create type public.user_role as enum ('owner', 'admin', 'member');
  end if;
  if not exists (select 1 from pg_type where typname = 'user_status') then
    create type public.user_status as enum ('active', 'invited', 'disabled');
  end if;
  if not exists (select 1 from pg_type where typname = 'member_role') then
    create type public.member_role as enum ('owner', 'admin', 'member', 'viewer');
  end if;
  if not exists (select 1 from pg_type where typname = 'member_status') then
    create type public.member_status as enum ('pending', 'active', 'suspended', 'left');
  end if;
  if not exists (select 1 from pg_type where typname = 'site_status') then
    create type public.site_status as enum ('active', 'inactive');
  end if;
  if not exists (select 1 from pg_type where typname = 'audit_status') then
    create type public.audit_status as enum ('pending', 'running', 'completed', 'failed');
  end if;
  if not exists (select 1 from pg_type where typname = 'artifact_status') then
    create type public.artifact_status as enum ('active', 'archived');
  end if;
  if not exists (select 1 from pg_type where typname = 'workflow_status') then
    create type public.workflow_status as enum ('pending', 'running', 'completed', 'failed', 'canceled');
  end if;
  if not exists (select 1 from pg_type where typname = 'agent_run_status') then
    create type public.agent_run_status as enum ('pending', 'running', 'succeeded', 'failed', 'canceled');
  end if;
  if not exists (select 1 from pg_type where typname = 'content_status') then
    create type public.content_status as enum ('draft', 'review', 'approved', 'published', 'archived');
  end if;
  if not exists (select 1 from pg_type where typname = 'cms_job_status') then
    create type public.cms_job_status as enum ('queued', 'running', 'failed', 'succeeded');
  end if;
  if not exists (select 1 from pg_type where typname = 'task_status') then
    create type public.task_status as enum ('queued', 'running', 'failed', 'succeeded', 'canceled');
  end if;
  if not exists (select 1 from pg_type where typname = 'audit_finding_status') then
    create type public.audit_finding_status as enum ('open', 'in_progress', 'resolved', 'wont_fix');
  end if;
end $$;

-- Tighten columns to enums (clean data/defaults before casting)
-- Users
alter table if exists public.users alter column role drop default;
alter table if exists public.users alter column status drop default;
update public.users
  set role = coalesce(nullif(role, '')::text, 'member'),
      status = coalesce(nullif(status, '')::text, 'active');
update public.users
  set role = 'member'
  where role not in ('owner', 'admin', 'member');
update public.users
  set status = 'active'
  where status not in ('active', 'invited', 'disabled');
alter table if exists public.users
  alter column role type public.user_role using role::public.user_role,
  alter column status type public.user_status using status::public.user_status,
  alter column role set default 'member',
  alter column status set default 'active';

-- Company members
alter table if exists public.company_members alter column role drop default;
alter table if exists public.company_members alter column status drop default;
update public.company_members
  set role = coalesce(nullif(role, '')::text, 'member'),
      status = coalesce(nullif(status, '')::text, 'pending');
update public.company_members
  set role = 'member'
  where role not in ('owner', 'admin', 'member', 'viewer');
update public.company_members
  set status = 'pending'
  where status not in ('pending', 'active', 'suspended', 'left');
alter table if exists public.company_members
  alter column role type public.member_role using role::public.member_role,
  alter column status type public.member_status using status::public.member_status,
  alter column role set default 'member',
  alter column status set default 'pending';

alter table if exists public.sites alter column status drop default;
update public.sites
  set status = coalesce(nullif(status, '')::text, 'active');
update public.sites
  set status = 'active'
  where status not in ('active', 'inactive');
alter table if exists public.sites
  alter column status type public.site_status using status::public.site_status;
alter table if exists public.sites
  alter column status set default 'active';

alter table if exists public.site_audits alter column status drop default;
update public.site_audits
  set status = coalesce(nullif(status, '')::text, 'pending');
update public.site_audits
  set status = 'pending'
  where status not in ('pending', 'running', 'completed', 'failed');
alter table if exists public.site_audits
  alter column status type public.audit_status using status::public.audit_status;
alter table if exists public.site_audits
  alter column status set default 'pending';

alter table if exists public.artifacts alter column status drop default;
update public.artifacts
  set status = coalesce(nullif(status, '')::text, 'active');
update public.artifacts
  set status = 'active'
  where status not in ('active', 'archived');
alter table if exists public.artifacts
  alter column status type public.artifact_status using status::public.artifact_status;
alter table if exists public.artifacts
  alter column status set default 'active';

alter table if exists public.workflows alter column status drop default;
update public.workflows
  set status = coalesce(nullif(status, '')::text, 'pending');
update public.workflows
  set status = 'pending'
  where status not in ('pending', 'running', 'completed', 'failed', 'canceled');
alter table if exists public.workflows
  alter column status type public.workflow_status using status::public.workflow_status;
alter table if exists public.workflows
  alter column status set default 'pending';

alter table if exists public.agent_runs alter column status drop default;
update public.agent_runs
  set status = coalesce(nullif(status, '')::text, 'pending');
update public.agent_runs
  set status = 'pending'
  where status not in ('pending', 'running', 'succeeded', 'failed', 'canceled');
alter table if exists public.agent_runs
  alter column status type public.agent_run_status using status::public.agent_run_status;
alter table if exists public.agent_runs
  alter column status set default 'pending';

alter table if exists public.workflow_steps alter column status drop default;
update public.workflow_steps
  set status = coalesce(nullif(status, '')::text, 'pending');
update public.workflow_steps
  set status = 'pending'
  where status not in ('pending', 'running', 'succeeded', 'failed', 'canceled');
alter table if exists public.workflow_steps
  alter column status type public.agent_run_status using status::public.agent_run_status;
alter table if exists public.workflow_steps
  alter column status set default 'pending';

alter table if exists public.content_assets alter column status drop default;
update public.content_assets
  set status = coalesce(nullif(status, '')::text, 'draft');
update public.content_assets
  set status = 'draft'
  where status not in ('draft', 'review', 'approved', 'published', 'archived');
alter table if exists public.content_assets
  alter column status type public.content_status using status::public.content_status;
alter table if exists public.content_assets
  alter column status set default 'draft';

alter table if exists public.audit_findings alter column status drop default;
update public.audit_findings
  set status = coalesce(nullif(status, '')::text, 'open');
update public.audit_findings
  set status = 'open'
  where status not in ('open', 'in_progress', 'resolved', 'wont_fix');
alter table if exists public.audit_findings
  alter column status type public.audit_finding_status using status::public.audit_finding_status;
alter table if exists public.audit_findings
  alter column status set default 'open';

alter table if exists public.cms_jobs alter column status drop default;
update public.cms_jobs
  set status = coalesce(nullif(status, '')::text, 'queued');
update public.cms_jobs
  set status = 'queued'
  where status not in ('queued', 'running', 'failed', 'succeeded');
alter table if exists public.cms_jobs
  alter column status type public.cms_job_status using status::public.cms_job_status;
alter table if exists public.cms_jobs
  alter column status set default 'queued';

alter table if exists public.task_queue alter column status drop default;
update public.task_queue
  set status = coalesce(nullif(status, '')::text, 'queued');
update public.task_queue
  set status = 'queued'
  where status not in ('queued', 'running', 'failed', 'succeeded', 'canceled');
alter table if exists public.task_queue
  alter column status type public.task_status using status::public.task_status;

-- Add company_id to task_queue if missing (nullable to avoid blocking)
alter table if exists public.task_queue
  add column if not exists company_id uuid references public.companies (id) on delete cascade;

create index if not exists task_queue_company_id_idx on public.task_queue (company_id);

-- Partial indexes for common queries
create index if not exists agent_runs_workflow_active_idx
  on public.agent_runs (workflow_id, status)
  where status in ('pending', 'running', 'failed');

create index if not exists task_queue_ready_idx
  on public.task_queue (status, priority desc, scheduled_at)
  where status in ('queued', 'running');

-- Tenant helper
create or replace function public.is_company_member(target_company uuid)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.company_members cm
    where cm.company_id = target_company
      and cm.user_id = auth.uid()
      and cm.status = 'active'
  );
$$;

comment on function public.is_company_member is 'Checks if auth.uid() is an active member of the given company.';

-- RLS policies (enable and scope to tenant)
alter table public.companies enable row level security;
create policy companies_select on public.companies
  for select using (public.is_company_member(id));
create policy companies_modify on public.companies
  for insert with check (auth.uid() is not null);
create policy companies_update on public.companies
  for update using (public.is_company_member(id)) with check (public.is_company_member(id));
create policy companies_delete on public.companies
  for delete using (public.is_company_member(id));

alter table public.company_members enable row level security;
create policy company_members_all on public.company_members
  for all using (public.is_company_member(company_id))
  with check (public.is_company_member(company_id) or auth.uid() = user_id);

alter table public.sites enable row level security;
create policy sites_all on public.sites
  for all using (public.is_company_member(company_id))
  with check (public.is_company_member(company_id));

alter table public.site_audits enable row level security;
create policy site_audits_all on public.site_audits
  for all using (
    exists (
      select 1 from public.sites s
      where s.id = site_audits.site_id
        and public.is_company_member(s.company_id)
    )
  )
  with check (
    exists (
      select 1 from public.sites s
      where s.id = site_audits.site_id
        and public.is_company_member(s.company_id)
    )
  );

alter table public.artifacts enable row level security;
create policy artifacts_all on public.artifacts
  for all using (public.is_company_member(company_id))
  with check (public.is_company_member(company_id));

alter table public.knowledge_chunks enable row level security;
create policy knowledge_chunks_all on public.knowledge_chunks
  for all using (
    exists (
      select 1 from public.artifacts a
      where a.id = knowledge_chunks.artifact_id
        and public.is_company_member(a.company_id)
    )
  )
  with check (
    exists (
      select 1 from public.artifacts a
      where a.id = knowledge_chunks.artifact_id
        and public.is_company_member(a.company_id)
    )
  );

alter table public.workflows enable row level security;
create policy workflows_all on public.workflows
  for all using (
    exists (
      select 1
      from public.sites s
      where s.id = workflows.site_id
        and public.is_company_member(coalesce(workflows.company_id, s.company_id))
    )
    or (workflows.company_id is not null and public.is_company_member(workflows.company_id))
  )
  with check (
    exists (
      select 1
      from public.sites s
      where s.id = workflows.site_id
        and public.is_company_member(coalesce(workflows.company_id, s.company_id))
    )
    or (workflows.company_id is not null and public.is_company_member(workflows.company_id))
  );

alter table public.workflow_steps enable row level security;
create policy workflow_steps_all on public.workflow_steps
  for all using (
    exists (
      select 1
      from public.workflows w
      left join public.sites s on s.id = w.site_id
      where w.id = workflow_steps.workflow_id
        and (
          (w.company_id is not null and public.is_company_member(w.company_id))
          or (s.company_id is not null and public.is_company_member(s.company_id))
        )
    )
  )
  with check (
    exists (
      select 1
      from public.workflows w
      left join public.sites s on s.id = w.site_id
      where w.id = workflow_steps.workflow_id
        and (
          (w.company_id is not null and public.is_company_member(w.company_id))
          or (s.company_id is not null and public.is_company_member(s.company_id))
        )
    )
  );

alter table public.agent_runs enable row level security;
create policy agent_runs_all on public.agent_runs
  for all using (
    public.is_company_member(company_id)
    or exists (select 1 from public.sites s where s.id = agent_runs.site_id and public.is_company_member(s.company_id))
    or exists (select 1 from public.workflows w left join public.sites s on s.id = w.site_id where w.id = agent_runs.workflow_id and public.is_company_member(coalesce(w.company_id, s.company_id)))
    or exists (select 1 from public.artifacts a where a.id = agent_runs.artifact_id and public.is_company_member(a.company_id))
  )
  with check (
    public.is_company_member(company_id)
    or exists (select 1 from public.sites s where s.id = agent_runs.site_id and public.is_company_member(s.company_id))
    or exists (select 1 from public.workflows w left join public.sites s on s.id = w.site_id where w.id = agent_runs.workflow_id and public.is_company_member(coalesce(w.company_id, s.company_id)))
    or exists (select 1 from public.artifacts a where a.id = agent_runs.artifact_id and public.is_company_member(a.company_id))
  );

alter table public.content_assets enable row level security;
create policy content_assets_all on public.content_assets
  for all using (public.is_company_member(company_id))
  with check (public.is_company_member(company_id));

alter table public.content_versions enable row level security;
create policy content_versions_all on public.content_versions
  for all using (
    exists (
      select 1
      from public.content_assets ca
      where ca.id = content_versions.content_asset_id
        and public.is_company_member(ca.company_id)
    )
  )
  with check (
    exists (
      select 1
      from public.content_assets ca
      where ca.id = content_versions.content_asset_id
        and public.is_company_member(ca.company_id)
    )
  );

alter table public.agent_metrics enable row level security;
create policy agent_metrics_all on public.agent_metrics
  for all using (
    exists (
      select 1
      from public.agent_runs ar
      where ar.id = agent_metrics.agent_run_id
        and (
          public.is_company_member(ar.company_id)
          or exists (select 1 from public.sites s where s.id = ar.site_id and public.is_company_member(s.company_id))
        )
    )
  )
  with check (
    exists (
      select 1
      from public.agent_runs ar
      where ar.id = agent_metrics.agent_run_id
        and (
          public.is_company_member(ar.company_id)
          or exists (select 1 from public.sites s where s.id = ar.site_id and public.is_company_member(s.company_id))
        )
    )
  );

alter table public.sandbox_results enable row level security;
create policy sandbox_results_all on public.sandbox_results
  for all using (
    exists (
      select 1
      from public.workflows w
      left join public.sites s on s.id = w.site_id
      where w.id = sandbox_results.workflow_id
        and public.is_company_member(coalesce(w.company_id, s.company_id))
    )
    or exists (
      select 1
      from public.content_assets ca
      where ca.id = sandbox_results.content_asset_id
        and public.is_company_member(ca.company_id)
    )
  )
  with check (
    exists (
      select 1
      from public.workflows w
      left join public.sites s on s.id = w.site_id
      where w.id = sandbox_results.workflow_id
        and public.is_company_member(coalesce(w.company_id, s.company_id))
    )
    or exists (
      select 1
      from public.content_assets ca
      where ca.id = sandbox_results.content_asset_id
        and public.is_company_member(ca.company_id)
    )
  );

alter table public.cms_jobs enable row level security;
create policy cms_jobs_all on public.cms_jobs
  for all using (
    exists (
      select 1
      from public.content_assets ca
      where ca.id = cms_jobs.content_asset_id
        and public.is_company_member(ca.company_id)
    )
  )
  with check (
    exists (
      select 1
      from public.content_assets ca
      where ca.id = cms_jobs.content_asset_id
        and public.is_company_member(ca.company_id)
    )
  );

alter table public.llm_usage_log enable row level security;
create policy llm_usage_log_all on public.llm_usage_log
  for all using (
    exists (
      select 1
      from public.agent_runs ar
      where ar.id = llm_usage_log.agent_run_id
        and (
          public.is_company_member(ar.company_id)
          or exists (select 1 from public.sites s where s.id = ar.site_id and public.is_company_member(s.company_id))
        )
    )
  )
  with check (
    exists (
      select 1
      from public.agent_runs ar
      where ar.id = llm_usage_log.agent_run_id
        and (
          public.is_company_member(ar.company_id)
          or exists (select 1 from public.sites s where s.id = ar.site_id and public.is_company_member(s.company_id))
        )
    )
  );

alter table public.audit_findings enable row level security;
create policy audit_findings_all on public.audit_findings
  for all using (
    exists (
      select 1
      from public.site_audits sa
      join public.sites s on s.id = sa.site_id
      where sa.id = audit_findings.site_audit_id
        and public.is_company_member(s.company_id)
    )
  )
  with check (
    exists (
      select 1
      from public.site_audits sa
      join public.sites s on s.id = sa.site_id
      where sa.id = audit_findings.site_audit_id
        and public.is_company_member(s.company_id)
    )
  );

alter table public.task_queue enable row level security;
create policy task_queue_all on public.task_queue
  for all using (public.is_company_member(company_id))
  with check (public.is_company_member(company_id));
