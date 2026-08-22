-- rls.sql — standalone verification of the §2.1 Row-Level Security policies.
--
-- Run against a Supabase database (local or cloud) that has the RLS migration
-- applied (supabase/migrations/20260812000000_rls_policies.sql):
--
--     psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/tests/rls.sql
--
-- With ON_ERROR_STOP=1 a single failed assertion aborts with a non-zero exit
-- code, so this script doubles as a CI gate.
--
-- We simulate users via request.jwt.claims (auth.uid() reads that GUC), so no
-- real auth.users rows are required. Every assertion is wrapped in a
-- transaction that is rolled back, leaving the database untouched.

begin;

do $$
declare
  u1 uuid := '11111111-1111-1111-1111-111111111111';
  u2 uuid := '22222222-2222-2222-2222-222222222222';
  aid uuid;
  n int;
begin
  -- 1) anon must NOT see the backend-internal table (RLS denies => 0 rows)
  set local role anon;
  set local "request.jwt.claims" to '{"role":"anon"}';
  select count(*) into n from public.examshield_documents;
  assert n = 0, 'anon was able to read examshield_documents (got ' || n || ' rows)';

  -- 2) authenticated u1 can create and read a public agent they own
  set local role authenticated;
  set local "request.jwt.claims" to json_build_object('sub', u1::text, 'role', 'authenticated')::text;
  insert into public.community_agents (name, visibility, owner_id)
    values ('Agent One', 'public', u1) returning id into aid;
  assert aid is not null, 'owner insert failed';
  select count(*) into n from public.community_agents where id = aid;
  assert n = 1, 'owner cannot read their own agent';

  -- 3) u2 cannot read u1's PRIVATE agent (cross-tenant denial)
  insert into public.community_agents (name, visibility, owner_id)
    values ('Agent Private', 'private', u1) returning id into aid;
  set local "request.jwt.claims" to json_build_object('sub', u2::text, 'role', 'authenticated')::text;
  select count(*) into n from public.community_agents where id = aid;
  assert n = 0, 'cross-tenant read of a private agent was allowed';

  -- 4) u2 CAN read u1's PUBLIC agent (marketplace discovery)
  select count(*) into n from public.community_agents where visibility = 'public';
  assert n >= 1, 'public agent not readable by another user';

  -- 5) u2 cannot UPDATE u1's agent (cross-tenant write denial)
  begin
    update public.community_agents set name = 'hacked' where id = aid;
    assert false, 'cross-tenant UPDATE was allowed';
  exception when insufficient_privilege then
    null; -- expected
  end;

  -- 6) the dedicated backend role can reach the internal table
  set local role app_backend;
  set local "request.jwt.claims" to json_build_object('role', 'app_backend')::text;
  perform count(*) from public.examshield_documents;
  perform count(*) from public.examshield_memory_items;
  perform count(*) from public.community_agents;
  assert true;
end $$;

-- Confirm the policies actually exist (defensive; the asserts above already
-- prove enforcement).
do $$
declare
  c int;
begin
  select count(*) into c from pg_policies
  where schemaname = 'public' and tablename = 'community_agents'
    and policyname in ('community_agents_owner_all', 'community_agents_public_read', 'community_agents_backend');
  assert c = 3, 'expected 3 community_agents policies, found ' || c;

  select count(*) into c from pg_policies
  where schemaname = 'public' and tablename = 'examshield_documents'
    and policyname = 'examshield_documents_backend';
  assert c = 1, 'expected examshield_documents_backend policy, found ' || c;
end $$;

rollback;

-- If we reached here, every assertion passed.
select 'RLS verification OK' as result;
