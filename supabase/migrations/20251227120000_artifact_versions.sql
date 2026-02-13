-- Artifact version history (for filesystem-first + Supabase mirror)
-- Stores immutable snapshots of artifact bodies for audit + rollback.

-- Ensure tenant helper exists (this function is also defined in later migrations).
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

create table if not exists public.artifact_versions (
  id uuid primary key default gen_random_uuid(),
  artifact_id uuid not null references public.artifacts (id) on delete cascade,
  version_no integer not null,
  body_md text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_by_user_id uuid references public.users (id),
  created_by_agent_id uuid references public.agents (id),
  created_at timestamptz not null default now(),
  constraint artifact_versions_unique unique (artifact_id, version_no)
);

create index if not exists artifact_versions_artifact_id_idx on public.artifact_versions (artifact_id);
create index if not exists artifact_versions_created_at_idx on public.artifact_versions (created_at desc);

-- RLS: tie access to the parent artifact's company_id
alter table public.artifact_versions enable row level security;

create policy artifact_versions_all on public.artifact_versions
  for all using (
    exists (
      select 1
      from public.artifacts a
      where a.id = artifact_versions.artifact_id
        and public.is_company_member(a.company_id)
    )
  )
  with check (
    exists (
      select 1
      from public.artifacts a
      where a.id = artifact_versions.artifact_id
        and public.is_company_member(a.company_id)
    )
  );


