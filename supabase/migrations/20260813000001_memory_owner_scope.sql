-- Per-user (owner-scoped) unified threat memory.
-- Fixes a cross-user data leak under open signup: previously examshield_memory_*
-- carried no owner_id and were only readable by the backend role (using(true)),
-- so one open-signup user could read another's memory/search matches/alerts.
-- We add owner_id + RLS (defense-in-depth for direct clients) AND the backend
-- filters by owner_id in application code (see examshield_ai/memory.py).

alter table public.examshield_memory_items
  add column if not exists owner_id uuid references auth.users(id) on delete cascade;

alter table public.examshield_memory_correlations
  add column if not exists owner_id uuid references auth.users(id) on delete cascade;

create index if not exists examshield_memory_items_owner_id_idx
  on public.examshield_memory_items (owner_id);

create index if not exists examshield_memory_correlations_owner_id_idx
  on public.examshield_memory_correlations (owner_id);

-- Direct-client defense-in-depth: a signed-in user only sees/owns their own rows.
-- The backend keeps its existing app_backend using(true) policy (reads/writes all)
-- and additionally filters by owner_id in application code before returning data.
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

-- Scope the vector search RPC by owner. NULL owner_id returns all rows (used by
-- the single local/offline backend role, which passes owner_id = null).
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
