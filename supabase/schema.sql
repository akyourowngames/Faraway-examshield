create table if not exists public.examshield_documents (
  collection text not null,
  document_key text not null,
  payload jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (collection, document_key)
);

alter table public.examshield_documents enable row level security;

create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

create table if not exists public.examshield_memory_items (
  id uuid primary key default extensions.gen_random_uuid(),
  memory_type text not null,
  source text not null default 'examshield',
  source_ref text not null,
  source_evidence_id text,
  content text not null,
  content_hash text not null,
  fingerprint_hash text not null,
  embedding extensions.vector(384),
  severity text not null default 'low',
  status text not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  owner_id uuid references auth.users(id) on delete cascade,
  unique (source_ref)
);

create table if not exists public.examshield_memory_correlations (
  id uuid primary key default extensions.gen_random_uuid(),
  correlation_key text not null unique,
  trigger_memory_id uuid references public.examshield_memory_items(id) on delete set null,
  memory_ids uuid[] not null default '{}'::uuid[],
  evidence_ids text[] not null default '{}'::text[],
  source_count int not null default 0,
  max_similarity double precision not null default 0,
  severity text not null default 'medium',
  status text not null default 'open',
  alert_id text,
  summary text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  owner_id uuid references auth.users(id) on delete cascade
);

alter table public.examshield_memory_items enable row level security;
alter table public.examshield_memory_correlations enable row level security;

create index if not exists examshield_memory_items_embedding_hnsw
  on public.examshield_memory_items
  using hnsw (embedding vector_cosine_ops)
  where embedding is not null;

create index if not exists examshield_memory_items_source_evidence_id_idx
  on public.examshield_memory_items (source_evidence_id);

create index if not exists examshield_memory_items_hash_idx
  on public.examshield_memory_items (content_hash, fingerprint_hash);

create index if not exists examshield_memory_items_status_severity_idx
  on public.examshield_memory_items (status, severity);

create index if not exists examshield_memory_correlations_status_idx
  on public.examshield_memory_correlations (status, severity);

create index if not exists examshield_memory_items_owner_id_idx
  on public.examshield_memory_items (owner_id);

create index if not exists examshield_memory_correlations_owner_id_idx
  on public.examshield_memory_correlations (owner_id);

create or replace function public.match_examshield_memory (
  query_embedding extensions.vector(384),
  match_threshold double precision default 0.76,
  match_count int default 10,
  exclude_source_ref text default null,
  min_created_at timestamptz default null,
  p_owner_id uuid default null
)
returns table (
  id uuid,
  memory_type text,
  source text,
  source_ref text,
  source_evidence_id text,
  content text,
  severity text,
  status text,
  metadata jsonb,
  similarity double precision,
  created_at timestamptz
)
language sql stable
as $$
  select
    item.id,
    item.memory_type,
    item.source,
    item.source_ref,
    item.source_evidence_id,
    item.content,
    item.severity,
    item.status,
    item.metadata,
    1 - (item.embedding <=> query_embedding) as similarity,
    item.created_at
  from public.examshield_memory_items item
  where item.embedding is not null
    and item.status = 'active'
    and (p_owner_id is null or item.owner_id = p_owner_id)
    and (exclude_source_ref is null or item.source_ref <> exclude_source_ref)
    and (min_created_at is null or item.created_at >= min_created_at)
    and 1 - (item.embedding <=> query_embedding) >= match_threshold
  order by item.embedding <=> query_embedding asc
  limit match_count;
$$;

insert into storage.buckets (id, name, public)
values ('evidence-files', 'evidence-files', false)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('agent-knowledge', 'agent-knowledge', false)
on conflict (id) do nothing;

-- ─────────────────────────────────────────────────────────────────────
-- Community Agents
-- ─────────────────────────────────────────────────────────────────────

create table if not exists public.community_agents (
  id uuid primary key default extensions.gen_random_uuid(),
  name text not null,
  description text not null default '',
  category text not null default 'general',
  visibility text not null default 'private',
  status text not null default 'draft',
  avatar text not null default '',
  author text not null default '',
  model text not null default 'gpt-4o',
  system_prompt text not null default '',
  response_style text not null default 'balanced',
  citation_mode boolean not null default true,
  tags text[] not null default '{}'::text[],
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agent_llm_configs (
  id uuid primary key default extensions.gen_random_uuid(),
  agent_id uuid not null references public.community_agents(id) on delete cascade,
  provider text not null,
  model text not null default '',
  api_key_encrypted text not null default '',
  endpoint_url text not null default '',
  extra_headers jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (agent_id)
);

create table if not exists public.agent_telegram_configs (
  id uuid primary key default extensions.gen_random_uuid(),
  agent_id uuid not null references public.community_agents(id) on delete cascade,
  bot_token text not null default '',
  bot_username text not null default '',
  bot_verified boolean not null default false,
  privacy_mode_disabled boolean not null default false,
  added_to_group boolean not null default false,
  promoted_admin boolean not null default false,
  message_reading_enabled boolean not null default false,
  webhook_url text not null default '',
  deployment_status text not null default 'disconnected',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (agent_id)
);

create table if not exists public.agent_knowledge_sources (
  id uuid primary key default extensions.gen_random_uuid(),
  agent_id uuid not null references public.community_agents(id) on delete cascade,
  name text not null,
  source_type text not null default 'document',
  status text not null default 'queued',
  file_count int not null default 0,
  chunk_count int not null default 0,
  total_chars int not null default 0,
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agent_knowledge_chunks (
  id uuid primary key default extensions.gen_random_uuid(),
  source_id uuid not null references public.agent_knowledge_sources(id) on delete cascade,
  agent_id uuid not null references public.community_agents(id) on delete cascade,
  content text not null,
  content_hash text not null default '',
  embedding extensions.vector(384),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.agent_conversations (
  id uuid primary key default extensions.gen_random_uuid(),
  agent_id uuid not null references public.community_agents(id) on delete cascade,
  user_message text not null,
  agent_response text not null default '',
  sources jsonb not null default '[]'::jsonb,
  latency_ms int not null default 0,
  status text not null default 'completed',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.community_agents enable row level security;
alter table public.agent_llm_configs enable row level security;
alter table public.agent_telegram_configs enable row level security;
alter table public.agent_knowledge_sources enable row level security;
alter table public.agent_knowledge_chunks enable row level security;
alter table public.agent_conversations enable row level security;

create index if not exists community_agents_status_idx on public.community_agents (status);
create index if not exists community_agents_category_idx on public.community_agents (category);
create index if not exists community_agents_visibility_idx on public.community_agents (visibility);
create index if not exists agent_knowledge_sources_agent_id_idx on public.agent_knowledge_sources (agent_id);
create index if not exists agent_knowledge_chunks_agent_id_idx on public.agent_knowledge_chunks (agent_id);
create index if not exists agent_knowledge_chunks_source_id_idx on public.agent_knowledge_chunks (source_id);
create index if not exists agent_conversations_agent_id_idx on public.agent_conversations (agent_id);

create index if not exists agent_knowledge_chunks_embedding_hnsw
  on public.agent_knowledge_chunks
  using hnsw (embedding vector_cosine_ops)
  where embedding is not null;

create or replace function public.match_agent_knowledge (
  query_embedding extensions.vector(384),
  p_agent_id uuid,
  match_threshold double precision default 0.7,
  match_count int default 8
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity double precision
)
language sql stable
as $$
  select
    chunk.id,
    chunk.content,
    chunk.metadata,
    1 - (chunk.embedding <=> query_embedding) as similarity
  from public.agent_knowledge_chunks chunk
  where chunk.embedding is not null
    and chunk.agent_id = p_agent_id
    and 1 - (chunk.embedding <=> query_embedding) >= match_threshold
  order by chunk.embedding <=> query_embedding asc
  limit match_count;
$$;

-- ─────────────────────────────────────────────────────────────────────
-- Row-Level Security policies (fixes audit §2.1)
--
-- Ownership model: community agents are owned by the Supabase auth user,
-- captured in `community_agents.owner_id` (FK to auth.users). Child agent
-- tables inherit ownership through `community_agents`. The backend-internal
-- tables (examshield_documents, examshield_memory_*) carry no per-user
-- ownership — they are system data and are only reachable by the dedicated
-- `app_backend` role (or the bypassing `service_role`). `anon`/`authenticated`
-- are denied by default everywhere they are not explicitly granted.
--
-- All DDL here is idempotent (if not exists / drop policy if exists) so this
-- file can be reapplied. The same content is mirrored in
-- supabase/migrations/20260812000000_rls_policies.sql for existing projects.
-- ─────────────────────────────────────────────────────────────────────

-- Dedicated least-privilege backend role. It does NOT have BYPASSRLS, so the
-- policies below actually constrain it. Its credential is a JWT whose `role`
-- claim is "app_backend", signed by the project JWT secret — provision that
-- out of band (see docs/PROJECT_WEAKNESSES_AUDIT.md §2.1). Never grant this
-- role the service_role key.
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

-- Ownership column for community agents (default to the caller for user-scoped
-- inserts; null for service_role/system inserts — which still work because
-- service_role bypasses RLS).
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

-- Community agents ───────────────────────────────────────────────────────
drop policy if exists community_agents_owner_all on public.community_agents;
create policy community_agents_owner_all on public.community_agents
  for all to authenticated
  using (owner_id = auth.uid())
  with check (owner_id = auth.uid());

-- Public agents are discoverable by anyone (marketplace browsing); private
-- agents are not. This is the only anon/authenticated grant on agent data.
drop policy if exists community_agents_public_read on public.community_agents;
create policy community_agents_public_read on public.community_agents
  for select to authenticated, anon
  using (visibility = 'public');

drop policy if exists community_agents_backend on public.community_agents;
create policy community_agents_backend on public.community_agents
  for all to app_backend
  using (true) with check (true);

-- Agent child tables: ownership is inherited from the parent agent ─────────
-- llm configs (hold provider secrets — owner only, no public read)
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

-- telegram configs (hold bot tokens — owner only, no public read)
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

-- knowledge sources (owner CRUD, no public read)
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

-- knowledge chunks (owner CRUD, no public read)
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

-- conversations (owner CRUD, no public read)
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

-- Backend-internal tables: system role only (no per-user ownership) ────────
drop policy if exists examshield_documents_backend on public.examshield_documents;
create policy examshield_documents_backend on public.examshield_documents
  for all to app_backend using (true) with check (true);

drop policy if exists examshield_memory_items_backend on public.examshield_memory_items;
create policy examshield_memory_items_backend on public.examshield_memory_items
  for all to app_backend using (true) with check (true);

drop policy if exists "memory items owner read" on public.examshield_memory_items;
create policy "memory items owner read"
  on public.examshield_memory_items for select
  to authenticated, anon
  using (owner_id = auth.uid());

drop policy if exists "memory items owner write" on public.examshield_memory_items;
create policy "memory items owner write"
  on public.examshield_memory_items for all
  to authenticated, anon
  using (owner_id = auth.uid())
  with check (owner_id = auth.uid());

drop policy if exists examshield_memory_correlations_backend on public.examshield_memory_correlations;
create policy examshield_memory_correlations_backend on public.examshield_memory_correlations
  for all to app_backend using (true) with check (true);

drop policy if exists "memory correlations owner read" on public.examshield_memory_correlations;
create policy "memory correlations owner read"
  on public.examshield_memory_correlations for select
  to authenticated, anon
  using (owner_id = auth.uid());

drop policy if exists "memory correlations owner write" on public.examshield_memory_correlations;
create policy "memory correlations owner write"
  on public.examshield_memory_correlations for all
  to authenticated, anon
  using (owner_id = auth.uid())
  with check (owner_id = auth.uid());

-- Storage: the dedicated backend role may manage the private buckets;
-- anon/authenticated remain denied by Supabase's default private-bucket
-- policies. (Owner-scoped folder access for agent-knowledge is a follow-up.)
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
