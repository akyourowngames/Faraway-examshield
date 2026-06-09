create table if not exists public.examshield_documents (
  collection text not null,
  document_key text not null,
  payload jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (collection, document_key)
);

alter table public.examshield_documents enable row level security;

insert into storage.buckets (id, name, public)
values ('evidence-files', 'evidence-files', false)
on conflict (id) do nothing;
