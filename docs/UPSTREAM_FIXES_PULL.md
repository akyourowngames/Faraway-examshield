# Upstream Fixes Pull — Cherry-Pick Summary

This document records the commits pulled from the original repository
(`risuhfoundry/Exam_shield`) onto the `fix/pull-upstream-selected` branch.

## Scope

The pull was surgical rather than a full fast-forward. Only bug, model, and
security fixes were cherry-picked. The frontend accessibility/i18n feature
commits were intentionally skipped because they introduced a larger UI change
with a dependency chain unrelated to the requested fixes.

## Source branches

- `upstream/perf-audit-fixes`
- `upstream/feat/frontend-weaknesses-section-7`

## Cherry-picked commits

### Model fixes

- `544877d` — feat: per-agent Telegram polling, Kilo reasoning streaming fix, chat formatting
- `4f18406` — feat: encrypt agent LLM keys at rest + RAG embedding/planner fixes

### Security fixes

- `e347518` — feat: add performance caches + prompt-injection/rate-limit guards
- `f50fc1a` — feat: wire §5 performance caches into request path + frontend
- `79e3517` — feat: authenticate backend API (audit §2.2) + frontend validation/tests
- `0010f57` — fix(security): enforce least-privilege RLS + dedicated app_backend role (audit §2.1)
- `45c136e` (re-applied as `7054384`) — fix(backend): replace cgi.FieldStorage + harden HTTP server (audit weakness #1/#2)

### Bug and test fixes

- `2ffb98a` — perf(workers): bound OCR pool with load-shedding; resolve §5 audit block
- `7da209b` — feat: §5 performance wiring, grounding/budget/hallucination modules + tests
- `5050de6` — fix: align ocr/tests with ruff + updated signatures so CI is green
- `9cb06d0` — fix(ci): add frontend Vitest suite + wire into CI; resolve audit §15/§17
- `6911ab7` — feat(ci): add GitHub Actions lint/test/build gate + fix lint blockers

### Supporting documentation

- `8d76211` — docs: fix AI service setup path and document community agent Telegram bots
- `4e36d46` — docs: add project analysis, tech-stack architecture, and learning roadmap
- `a5cfb05` — docs: rewrite README and add ai-service tests
- `eec54ee` — docs(audit): remove completed §2.1 RLS items instead of marking resolved

### Local reconciliation

- `211f134` — fix: resolve normalize/server import mismatch after cherry-picks

This final commit restores `apps/ai-service/examshield_ai/server.py` to the
authoritative hardened version and adds the `normalize` boundary helper module,
which was introduced by an intermediate commit that was skipped during the
cherry-pick.

## Intentionally skipped

- `9af9ea4` — frontend a11y/i18n feature (large UI change, not a bug/model/security fix)
- `f730377` — frontend test files dependent on the a11y/i18n feature
- `fac9a77` — locale initializer refactor dependent on the a11y/i18n feature

## Validation

All checks pass locally:

- Backend: `186 passed, 2 skipped`
- Core: `23 passed`
- Web: `32 passed`
- Ruff: `All checks passed`
- Web production build: passes with CI placeholder Supabase env vars
