"""DB-gated verification of the §2.1 Row-Level Security policies.

This test exercises the *real* Postgres policies defined in
``supabase/schema.sql`` / ``supabase/migrations/20260812000000_rls_policies.sql``.
It is skipped unless a live Supabase Postgres URL is provided via
``EXAMSHIELD_TEST_DATABASE_URL`` (no local Postgres is available in CI, so the
test stays green there). When the URL *is* provided it:

  1. applies the schema via ``psql`` (if ``psql`` is on PATH) so the policies
     exist, and
  2. asserts that RLS actually enforces tenancy: anon/authenticated users are
     denied cross-tenant access, owners can manage their own rows, public
     agents are discoverable, and the dedicated ``app_backend`` role can reach
     the system tables.

Run manually against a Supabase DB:

    EXAMSHIELD_TEST_DATABASE_URL=postgresql://... pytest apps/ai-service/tests/test_rls.py
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

DATABASE_URL = os.environ.get("EXAMSHIELD_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="EXAMSHIELD_TEST_DATABASE_URL is not set (needs a live Supabase Postgres)",
)

SCHEMA_SQL = (
    pathlib.Path(__file__).resolve().parents[3] / "supabase" / "schema.sql"
)


def _connect() -> "psycopg.Connection":
    return psycopg.connect(DATABASE_URL, autocommit=True)


@pytest.fixture(scope="module")
def db() -> "psycopg.Connection":
    conn = _connect()
    _apply_schema(conn)
    yield conn
    conn.close()


def _apply_schema(conn: "psycopg.Connection") -> None:
    """Best-effort: load the schema via psql if available.

    If ``psql`` is missing we assume the target database already has the RLS
    migration applied (e.g. a Supabase local dev instance applies migrations on
    start) and rely on the policy-existence assertion in the tests to catch a
    missing schema.
    """
    psql = shutil.which("psql")
    if psql and SCHEMA_SQL.exists():
        result = subprocess.run(
            [psql, DATABASE_URL, "-v", "ON_ERROR_STOP=1", "-f", str(SCHEMA_SQL)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(
                f"psql failed to apply schema.sql (rc={result.returncode}): "
                f"{result.stderr[-500:]}"
            )


def _as(conn: "psycopg.Connection", role: str, sub: uuid.UUID | None = None) -> "psycopg.Cursor":
    cur = conn.cursor()
    cur.execute(f"set role {role}")  # session-level; each test sets its own role
    claims: dict = {"role": role}
    if sub is not None:
        claims["sub"] = str(sub)
    cur.execute('set "request.jwt.claims" to %s', (json.dumps(claims),))
    return cur


class TestRlsEnforcement:
    def test_anon_cannot_read_backend_table(self, db: "psycopg.Connection") -> None:
        cur = _as(db, "anon")
        cur.execute("select count(*) from public.examshield_documents")
        assert cur.fetchone()[0] == 0, "anon must not read examshield_documents"

    def test_policies_exist(self, db: "psycopg.Connection") -> None:
        cur = db.cursor()
        cur.execute(
            "select count(*) from pg_policies "
            "where schemaname = 'public' and tablename = 'community_agents'"
        )
        assert cur.fetchone()[0] >= 3, "community_agents RLS policies missing"

    def test_owner_can_manage_own_agent(self, db: "psycopg.Connection") -> None:
        u1 = uuid.uuid4()
        cur = _as(db, "authenticated", u1)
        cur.execute(
            "insert into public.community_agents (name, visibility, owner_id) "
            "values ('A', 'public', %s) returning id",
            (str(u1),),
        )
        aid = cur.fetchone()[0]
        try:
            cur.execute("select count(*) from public.community_agents where id = %s", (aid,))
            assert cur.fetchone()[0] == 1
        finally:
            cur.execute("delete from public.community_agents where id = %s", (aid,))

    def test_cross_tenant_read_and_write_denied(self, db: "psycopg.Connection") -> None:
        u1, u2 = uuid.uuid4(), uuid.uuid4()
        owner = _as(db, "authenticated", u1)
        owner.execute(
            "insert into public.community_agents (name, visibility, owner_id) "
            "values ('P', 'private', %s) returning id",
            (str(u1),),
        )
        aid = owner.fetchone()[0]
        try:
            other = _as(db, "authenticated", u2)
            other.execute("select count(*) from public.community_agents where id = %s", (aid,))
            assert other.fetchone()[0] == 0, "cross-tenant read of private agent allowed"
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                other.execute(
                    "update public.community_agents set name = 'x' where id = %s", (aid,)
                )
        finally:
            owner.execute("delete from public.community_agents where id = %s", (aid,))

    def test_public_agent_discoverable_by_other_user(self, db: "psycopg.Connection") -> None:
        u1, u2 = uuid.uuid4(), uuid.uuid4()
        owner = _as(db, "authenticated", u1)
        owner.execute(
            "insert into public.community_agents (name, visibility, owner_id) values ('Pub', 'public', %s)",
            (str(u1),),
        )
        try:
            other = _as(db, "authenticated", u2)
            other.execute("select count(*) from public.community_agents where visibility = 'public'")
            assert other.fetchone()[0] >= 1
        finally:
            owner.execute("delete from public.community_agents where owner_id = %s", (str(u1),))

    def test_backend_role_reaches_internal_tables(self, db: "psycopg.Connection") -> None:
        cur = _as(db, "app_backend")
        cur.execute("select count(*) from public.examshield_documents")
        cur.fetchone()  # must not raise
        cur.execute("select count(*) from public.examshield_memory_items")
        cur.fetchone()
        cur.execute("select count(*) from public.community_agents")
        cur.fetchone()
