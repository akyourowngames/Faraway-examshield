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
