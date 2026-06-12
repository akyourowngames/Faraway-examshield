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
  updated_at timestamptz not null default now()
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

create or replace function public.match_examshield_memory (
  query_embedding extensions.vector(384),
  match_threshold double precision default 0.76,
  match_count int default 10,
  exclude_source_ref text default null
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
    and (exclude_source_ref is null or item.source_ref <> exclude_source_ref)
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
