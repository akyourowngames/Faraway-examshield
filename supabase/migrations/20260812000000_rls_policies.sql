-- Migration: Row-Level Security policies (fixes audit §2.1)
--
-- Apply to existing projects: `supabase db push` or run against the project DB.
-- This mirrors the RLS block appended to supabase/schema.sql so fresh
-- `schema.sql` installs and existing databases stay consistent.
--
-- Ownership model: community agents are owned by the Supabase auth user via
-- `community_agents.owner_id`. Child agent tables inherit ownership through
-- `community_agents`. Backend-internal tables (examshield_documents,
-- examshield_memory_*) have no per-user ownership and are only reachable by
-- the dedicated `app_backend` role (or the bypassing `service_role`).
--
-- The dedicated `app_backend` role has NO BYPASSRLS, so the policies below
-- constrain it. Provision its credential (a JWT with `role: "app_backend"`
-- signed by the project JWT secret) out of band. Never grant it the
-- service_role key.

-- Dedicated least-privilege backend role.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_backend') then
    create role app_backend with login noinherit;
  end if;
end $$;

grant usage on schema public to app_backend;
grant select, insert, update, delete on all tables in schema public to app_backend;
grant usage, select on all sequences in schema public to app_backend;
alter default privileges in schema public
  grant select, insert, update, delete on tables to app_backend;
alter default privileges in schema public
  grant usage, select on sequences to app_backend;

-- Ownership column for community agents.
alter table public.community_agents
  add column if not exists owner_id uuid references auth.users(id) on delete cascade
  default auth.uid();
create index if not exists community_agents_owner_id_idx
  on public.community_agents (owner_id);

-- Helper so policies read cleanly.
create or replace function public.is_app_backend() returns boolean
language sql stable
as $$
  select coalesce(auth.jwt() ->> 'role', '') = 'app_backend'
$$;

-- Community agents
drop policy if exists community_agents_owner_all on public.community_agents;
create policy community_agents_owner_all on public.community_agents
  for all to authenticated
  using (owner_id = auth.uid())
  with check (owner_id = auth.uid());

drop policy if exists community_agents_public_read on public.community_agents;
create policy community_agents_public_read on public.community_agents
  for select to authenticated, anon
  using (visibility = 'public');

drop policy if exists community_agents_backend on public.community_agents;
create policy community_agents_backend on public.community_agents
  for all to app_backend
  using (true) with check (true);

-- Agent child tables: ownership is inherited from the parent agent
drop policy if exists agent_llm_configs_owner on public.agent_llm_configs;
create policy agent_llm_configs_owner on public.agent_llm_configs
  for all to authenticated
  using (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()))
  with check (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()));

drop policy if exists agent_llm_configs_backend on public.agent_llm_configs;
create policy agent_llm_configs_backend on public.agent_llm_configs
  for all to app_backend using (true) with check (true);

drop policy if exists agent_telegram_configs_owner on public.agent_telegram_configs;
create policy agent_telegram_configs_owner on public.agent_telegram_configs
  for all to authenticated
  using (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()))
  with check (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()));

drop policy if exists agent_telegram_configs_backend on public.agent_telegram_configs;
create policy agent_telegram_configs_backend on public.agent_telegram_configs
  for all to app_backend using (true) with check (true);

drop policy if exists agent_knowledge_sources_owner on public.agent_knowledge_sources;
create policy agent_knowledge_sources_owner on public.agent_knowledge_sources
  for all to authenticated
  using (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()))
  with check (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()));

drop policy if exists agent_knowledge_sources_backend on public.agent_knowledge_sources;
create policy agent_knowledge_sources_backend on public.agent_knowledge_sources
  for all to app_backend using (true) with check (true);

drop policy if exists agent_knowledge_chunks_owner on public.agent_knowledge_chunks;
create policy agent_knowledge_chunks_owner on public.agent_knowledge_chunks
  for all to authenticated
  using (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()))
  with check (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()));

drop policy if exists agent_knowledge_chunks_backend on public.agent_knowledge_chunks;
create policy agent_knowledge_chunks_backend on public.agent_knowledge_chunks
  for all to app_backend using (true) with check (true);

drop policy if exists agent_conversations_owner on public.agent_conversations;
create policy agent_conversations_owner on public.agent_conversations
  for all to authenticated
  using (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()))
  with check (exists (
    select 1 from public.community_agents a
    where a.id = agent_id and a.owner_id = auth.uid()));

drop policy if exists agent_conversations_backend on public.agent_conversations;
create policy agent_conversations_backend on public.agent_conversations
  for all to app_backend using (true) with check (true);

-- Backend-internal tables: system role only
drop policy if exists examshield_documents_backend on public.examshield_documents;
create policy examshield_documents_backend on public.examshield_documents
  for all to app_backend using (true) with check (true);

drop policy if exists examshield_memory_items_backend on public.examshield_memory_items;
create policy examshield_memory_items_backend on public.examshield_memory_items
  for all to app_backend using (true) with check (true);

drop policy if exists examshield_memory_correlations_backend on public.examshield_memory_correlations;
create policy examshield_memory_correlations_backend on public.examshield_memory_correlations
  for all to app_backend using (true) with check (true);

-- Storage: dedicated backend role may manage the private buckets.
alter table storage.objects enable row level security;

drop policy if exists evidence_files_backend on storage.objects;
create policy evidence_files_backend on storage.objects
  for all to app_backend
  using (bucket_id = 'evidence-files')
  with check (bucket_id = 'evidence-files');

drop policy if exists agent_knowledge_storage_backend on storage.objects;
create policy agent_knowledge_storage_backend on storage.objects
  for all to app_backend
  using (bucket_id = 'agent-knowledge')
  with check (bucket_id = 'agent-knowledge');
