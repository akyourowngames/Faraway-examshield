# ExamShield Hackathon — Master Plan (LIVING DOCUMENT)

> Edit freely. Update "Last updated" each revision.
>
> **Last updated:** 2026-08-22 (v4 — detailed per-member contribution plans §4.1–§4.6; task-first dual-track model)
> **Original (hackathon base):** `akyourowngames/Faraway-examshield` · **Our copy/submission:** `risuhfoundry/Exam_shield`

---

## 0. TL;DR

1. Our copy has **180 commits on main** = original's 71 + **109 extra commits**. The extras are NOT junk — they're high-quality security/CI/test work, almost all authored by Krish (`animeit158@gmail.com`). Do not bulk-delete them.
2. **v3: organizer tasks are the primary graded deliverable.** History work is capped at ~3 hours; ~80% of the clock goes to task implementation (§6 dual-track model).
3. Real eval risks: (a) 51 bot-authored base commits, (b) Rishab has only 2 commits despite being Integrations lead, (c) Rai/Nikhil/Virat zero evidence. All three are fixed by the squash + task-sprint attribution — not by rewriting Krish's work.
4. Chosen approach: **Option D — Foundation + Sprint.** Squash inherited bot history once (§3), build a retroactive issue→fix trace from the audit doc (~30 min), then every member earns attribution through organizer-task PRs that build on the foundation (§6.5 intake template).

---

## 1. Deep Analysis Findings (verified 2026-08-22, cloned both repos)

### 1.1 Repo comparison

| Item | Original `akyourowngames/Faraway-examshield` | Copy `risuhfoundry/Exam_shield` |
|---|---|---|
| main commits | 71 | **180** (= 71 inherited + 109 new) |
| relationship | base | original tip `663d4fd` is direct ancestor ✓ |
| extra branches | `codex/ocr-pipeline` (merged) | `perf-audit-fixes`, `feat/frontend-weaknesses-section-7`, `feat/telegram-pairing` — **all 3 fully merged into main** |
| PRs | #1, #2 | #1, #2, #3 — all merged |
| diff scope | — | 250 files changed, +36,415 / −3,970 lines |

### 1.2 Authorship audit — copy `main` (the eval-critical table)

| Identity | Email | Commits | Assessment |
|---|---|---|---|
| akyourowngames / Krish (same person, same email) | animeit158@gmail.com | **127** (19 in base + 108 of the extras) | Real work, strong record ✓ |
| ExamShield Dev | dev@examshield.ai | 51 (all in inherited base) | 🚩 AI-agent identity — no GitHub member owns these |
| risuhfoundry (Rishab) | risuhfoundry@gmail.com | **2** (`db458ff` initial commit, `f495b22` docs) | 🚩 Named Integrations lead but nearly invisible |
| Rai / Nikhil / Virat | — | **0** | 🚩 No evidence at all |

### 1.3 What the 109 extra commits actually are (quality check)

Genuine engineering, well-messaged conventional commits tied to audit sections:
- **Security:** per-user data isolation (fail-closed), Supabase RLS + dedicated `app_backend` role, encrypted agent LLM keys at rest, JWT verification via JWKS (ES256/HS256), cross-account cache-leak fix, prompt-injection guards
- **Backend:** HTTP→FastAPI/uvicorn migration, authenticated backend API, OCR pool load-shedding
- **Frontend:** audit §7 fixes (a11y, error/loading states, reduced-motion, toasts, code-splitting, i18n)
- **Quality infra:** GitHub Actions CI gate, Vitest frontend suite, pytest/ruff alignment, offline smoke tests
- **Features:** Telegram pairing + per-user bots, voice investigator (Sarvam), multi-tenant orgs + SMTP invites, KILO vision transcription

➡️ **Conclusion: "remove unnecessary stuff" should mean cruft files + bot-history compression, NOT deleting this work.**

### 1.4 Team roster (already documented in-repo: `teamwork-intro.md`)

| Member | Claimed role | Git reality today | Gap to close in 24h |
|---|---|---|---|
| Krish Verma (@akyourowngames?) | Core Architect / AI Engine | 127 commits ✓ | Confirm username mapping; keep shipping |
| Rishab (@risuhfoundry) | Integrations (AI↔Telegram↔models) | 2 commits 🚩 | Needs 5+ substantive integration PRs NOW |
| Nikhil | Backend | 0 commits 🚩 | Small backend fixes/docs PRs |
| Virat | Frontend | 0 commits 🚩 | Small web/ fixes PRs |
| Rai | Pitch & Demo Lead | 0 commits 🚩 | Docs/demo-script/presentation PRs |

Also found: `docs/hackathon/` already contains per-member demo scripts + Q&A prep — reuse these; ensure they match final code.

### 1.5 Cleanup targets (verified present)

- [x] All 3 feature branches fully merged → safe to delete after backup tag
- [ ] `.cursor/` directory at root (reveals AI tooling) — keep/delete decision needed
- [ ] `todo2.txt` at root — delete
- [ ] `docs/superpowers/` internal AI-planning specs/plans — decide: keep (transparency) or remove before submission
- [ ] `teamwork-intro.md` lacks GitHub usernames — add them so evaluators can map names→accounts
- [ ] Secrets scan: ✅ no `.env` files committed (only `.env.example`) — still run `gitleaks` once before final push
- [ ] README badges point at mixed URLs (some `risuhfoundry`, some `akyourowngames`) — normalize

---

## 2. Strategy Decision

> **v3 update: organizer TASKS are the primary graded deliverable.** Commit hygiene is evidence, not the product. Everything below is restructured around a dual-track model (see §6.5).

### Option A — Keep all 180 commits as-is ❌
Bot-authored history stays visible; 4/5 members invisible.

### Option B — Full reset to single baseline ❌
Destroys Krish's excellent 109-commit record — our best eval asset.

### Option C — Thematic re-split of the 109 commits into PR waves ❌
1–2h of risky rebase choreography on interdependent commits (RLS/FastAPI span many files), zero task progress, and evaluators can tell retro-grouped PRs anyway. Rejected on time-cost alone now that tasks dominate.

### Option D — Dual-track "Foundation + Sprint" ✅ (CHOSEN)
Land existing work ONCE, cheaply; spend ~80% of remaining hours on organizer tasks; attribute members through task PRs that build ON the foundation:

- **Track 1 — Foundation (H0–3, one-time):** surgical squash (§3) → clean main containing ALL existing security/bug fixes. No further history work ever.
- **Track 1b — Trace layer (~30 min):** convert `docs/PROJECT_WEAKNESSES_AUDIT.md` sections into retroactive themed issues, each listing its implementing commit range. Creates the issue→fix trace without touching git.
- **Track 2 — Task sprint (H2–22):** every organizer task becomes issue(s) → owner → branch → PR → cross-review. Member attribution comes FROM task PRs, not from rewriting old work. Task PRs explicitly reference foundation commits they leverage ("extends abc123 per-user isolation").

**Decision:** ☐ A ☐ B ☐ C ☑ D

---

## 3. Surgical Squash — Exact Procedure (Phase 0)

Safe because the baseline will carry the *exact tree* of old-tip `663d4fd` → rebase replays conflict-free.

```bash
# 0. safety net first
git branch backup-main-180 && git push origin backup-main-180

# 1. build orphan baseline commit with identical tree to old tip 663d4fd8281f...
NEWBASE=$(git commit-tree 663d4fd8281f478873c8a770fc7b9ad91a1d10ec^{tree} \
  -m "chore: inherit upstream ExamShield MVP baseline (pre-team)")

# 2. replay the 109 team commits onto it (linearized)
git checkout -b clean-main
git rebase --onto $NEWBASE 663d4fd8281f478873c8a770fc7b9ad91a1d10ec main

# 3. verify BEFORE swapping
git log --oneline | wc -l          # expect ~110
git shortlog -sne                  # no more dev@examshield.ai
git diff backup-main-180 clean-main  # MUST be empty
cd web && npm ci && npm run build && cd ..   # app builds

# 4. swap (only after diff check passes)
git branch -M clean-main main && git push -f origin main
```

Post-squash cleanup PRs:
- Delete stale branches `perf-audit-fixes`, `feat/frontend-weaknesses-section-7`, `feat/telegram-pairing`
- Remove `todo2.txt`; decide `.cursor/` and `docs/superpowers/`
- Add `.env.example` coverage check, issue templates, `CONTRIBUTING.md`

---

## 4. Per-Member Contribution Plans (detailed)

> v4: full member-by-member playbook. Warm-up PRs happen H1–2; once organizer tasks land, each member claims sub-tasks of those tasks via §6.5 intake — the warm-up list is fallback only.
>
> **Universal workflow for every member:**
> 1. One-time git setup: `git config user.name "<GitHub username>"` + `user.email "<GitHub noreply email>"` (use the GitHub noreply format `ID+username@users.noreply.github.com` so commits link to profiles)
> 2. Work loop: pick issue → `git checkout -b feat/task-N-slug` → small commits (`feat:`/`fix:`/`docs:`/`test:` prefixes) → push YOUR branch → open PR (`Closes #N`) → request review from a different member → merge via board
> 3. Never push `main`; never commit under someone else's account; every author can explain 100% of their diff

---

### 4.1 Krish Verma — Core Architect / AI Engine · @akyourowngames *(confirm username)*

**Foundation relationship:** author of the 109 landed commits — his history IS the foundation layer. His job now shifts from producing commits to multiplying the team.

| When | Work | Output |
|---|---|---|
| H0–1 | Executes §3 squash surgery + verifies tree-diff empty | clean main |
| H1–3 | Writes the ~8 retroactive trace issues from audit doc w/ commit ranges | issue trail |
| Task sprint | Reviews/approves EVERY PR (review trail = eval evidence for all); takes hardest task sub-parts only (algorithmic/security core) | 15+ reviews, 2–3 PRs |
| H18–21 | Integration debugging on demo path | fixes as needed |

- **Target:** 2–3 own PRs + reviews on all others. His commit count is already strong (127) — adding more is optional, reviewing is mandatory.
- **Eval talking points:** explain RLS isolation design, JWKS verification, OCR fallback chain — he owns the "how it works" questions.

### 4.2 Rishab — Integrations Lead · @risuhfoundry *(biggest gap: 2 commits vs claimed role)*

**Foundation relationship:** the 109 commits contain his lane's material (Telegram pairing `d1ea9df`, FastAPI migration `3d874b0`, model routing). His task-sprint work WIREs and EXTENDS these — each PR naturally cites them ("builds on f9575ac").

| When | Work | Why it counts |
|---|---|---|
| H0–1 | Verifies squash (diff-empty check, build) | co-owner of Phase 0 |
| H1–2 | Warm-up PR #1: health/readiness endpoint for ai-service; PR #2: fix Telegram webhook retry/backoff | visible integration evidence immediately |
| Task sprint | Claims integration sub-tasks of EVERY organizer task: wiring new features into ai-service/telegram/web glue, API contract alignment, end-to-end tests | 5–7 substantive PRs |
| H18–21 | Runs end-to-end demo path with Virat; fixes integration breaks | demo owner |

- **Warm-up backlog (if tasks not yet released):** model-fallback chain config, pairing-flow integration test, token-refresh edge case, `/api/plan` proxy hardening, request-ID logging across services.
- **Target:** 5–7 merged PRs minimum — this is the number that repairs the role-vs-history gap.
- **Eval talking points:** walk through any integration PR end-to-end (which service calls what, where auth tokens flow).

### 4.3 Nikhil — Backend · @______ *(new user — small but real)*

**Foundation relationship:** builds on Krish's backend work without touching its core. Takes bounded, low-risk slices of task features.

| When | Work | Why it's safe for a new user |
|---|---|---|
| H1–2 | Warm-up PR #1: `CONTRIBUTING.md` + issue/PR templates; PR #2: standardize API error responses (one helper, applied to 2–3 routes) | config/docs = zero blast radius; still real code in #2 |
| Task sprint | For each organizer task, claims: input validation layer, DB migration file if needed, backend README section for that feature, unit tests | well-bounded sub-tasks of graded work |
| Ongoing | Reviews Rishab's/Virat's PRs | review evidence |

- **Target:** 2–3 merged code PRs + 1 docs PR + 3+ reviews.
- **Guardrail:** each PR ≤ ~150 lines changed — learnable, explainable, honest.
- **Eval talking points:** explain validation flow and why error responses are standardized.

### 4.4 Virat — Frontend · @______ *(new user — small but real)*

**Foundation relationship:** extends audit §7 frontend work (a11y, loading/error states) already in the 109. UI polish of TASK features is his sprint niche.

| When | Work | Why it's safe |
|---|---|---|
| H1–2 | Warm-up PR #1: dashboard loading-state bug fix; PR #2: README screenshots + badge URL normalization | visual, verifiable, no backend risk |
| Task sprint | For each organizer task, claims: its UI screen/component, form validation UX, empty/loading/error states, mobile responsiveness check | every feature needs UI — guaranteed sub-task supply |
| Ongoing | Reviews Rai's/Nikhil's PRs | review evidence |

- **Target:** 2–3 merged code PRs + screenshots/docs PR + 3+ reviews.
- **Eval talking points:** demo the UI he built live and explain state handling.

### 4.5 Rai — Pitch & Demo Lead · @______ *(new user — docs/story lane)*

**Foundation relationship:** converts engineering into eval-visible narrative. Docs PRs tied to task deliverables count fully as contribution.

| When | Work | Why it counts |
|---|---|---|
| H1–2 | Warm-up PR #1: rewrite `teamwork-intro.md` with GitHub usernames + per-member PR links; PR #2: sync `docs/hackathon/*` scripts with current UI | makes the WHOLE team legible to evaluators |
| Task intake (30 min) | Writes the "Demo line" for every task issue (§6.5 template field) | forces clarity before code starts |
| Task sprint | For each delivered task: user-facing docs section, demo script update, screenshots/GIF | 2–3 docs PRs mapped to graded features |
| H21–24 | Leads rehearsal: each member presents THEIR OWN PRs | eval-readiness |

- **Target:** 3–4 merged docs PRs + owns release notes mapping tasks→PRs→members.
- **Eval talking points:** product story, architecture overview at whiteboard level, who-built-what table.

---

### 4.6 Contribution summary grid (post-squash targets)

| Member | Own PRs | Reviews given | Commits (approx) | Evidence type |
|---|---|---|---|---|
| Krish | 2–3 | 15+ (all) | 130+ total | foundation + review leadership |
| Rishab | 5–7 | 4+ | 25–40 | integration depth |
| Nikhil | 3–4 | 3+ | 8–15 | bounded backend slices |
| Virat | 3–4 | 3+ | 8–15 | UI states of task features |
| Rai | 3–4 | 2+ | 6–10 | docs/narrative of task features |

Anti-spam guardrails (evaluators detect these): no whitespace-only/rename-bulk commits; no co-authored-by dumps of AI output under human names without understanding; every author must explain their own diffs verbally if asked; light members' PRs must touch real task features, not just `README.md` ten times.

---

## 5. Documents To Produce / Update

| Doc | Owner | Status |
|---|---|---|
| `docs/BUILD_PLAN.md` (distilled §6 below) | Rishab | create |
| `docs/PRODUCT_DESIGN.md` (personas, flows: upload→OCR→watermark→attribution→alert; architecture diagram; API table; security model) | Nikhil + Rai | create (source material exists in `docs/TECH_STACK_ARCHITECTURE.md`, `PROJECT_STRENGTHS.md`, audit doc) |
| `teamwork-intro.md` update (add GitHub usernames, link PRs per member) | Rai | update |
| `README.md` (normalize badges/URLs to one org, screenshots, honest hackathon positioning) | Virat | update |
| `CONTRIBUTING.md` + issue/PR templates | Nikhil | create |

---

## 6. 24-Hour Build Plan (v3 — task-first)

> Rule of thumb: history work ends by H3. From H3 on, every merged PR should trace to an organizer task or a foundation-trace issue. No standalone busywork.

**Phase 0 — Foundation surgery (H0–1)** · Krish executes, Rishab verifies
Run §3 squash + cleanup PRs + board creation in parallel with Phase 0.5. Acceptance: diff-empty check green, build green, `git shortlog` clean.

**Phase 0.5 — Trace layer + warm-up (H1–2, parallel)** · Rai, Nikhil, Virat
- Convert `docs/PROJECT_WEAKNESSES_AUDIT.md` → ~8 retroactive themed issues, each listing its implementing commit range (`Fixed by: abc123..def456`) → close each via a one-line docs PR referencing it
- Board columns + automation live; `teamwork-intro.md` updated w/ usernames
- Each light member ships 1 small warm-up PR (docs/config/copy) to have evidence flowing before tasks land
- Acceptance: trace issues exist, every member ≥1 merged PR

**Phase 1 — Task intake (on release, budget 30 min max)** · Rishab triages, all input
Use the intake template (§6.5). Map each task to existing foundation features + gap work + owner. Acceptance: every task has an issue, owner, and leverage note before any code starts.

**Phase 2 — Task sprint (H2–18, the core)** · all per matrix §4
- Heavy implementation: Krish + Rishab; Nikhil/Virat/Rai take well-bounded sub-tasks OF THE ORGANIZER TASKS (validation layer, UI states, test data, docs/demo assets for that feature) — never unrelated chores
- Cross-review everything; CI green; task PRs cite foundation commits they build on
- Checkpoint H10: if a task is >50% incomplete, descope ruthlessly (demo path first)
- Acceptance: ≥70% of organizer tasks merged; ≥12 PRs total across tracks

**Phase 3 — Integration + demo path (H18–21)** · Rishab + Virat
End-to-end: login → dashboard → upload evidence → OCR/vision → attribution → alert → Telegram DM — now including whatever the tasks added. Deploy checks (Vercel + Render). Demo scripts updated to match final state.

**Phase 4 — Freeze + eval-readiness (H21–24)** · All
Tag `v1.0-hackathon`, release notes mapping tasks→PRs→members. Final audit: `git shortlog -sne` shows all 5 accounts; Insights→Contributors populated; every member rehearses explaining their own task PRs. Acceptance: task coverage ≥ agreed scope; contribution matrix met or consciously waived.

### 6.5 Task Intake Template (apply within 30 min of task release)

```markdown
## TASK-{n}: <organizer task title>
Organizer source: <exact wording / link>
Acceptance criteria (demo-verifiable): 
- [ ] ...
Existing foundation leverage: <e.g., "per-user RLS isolation (f9575ac) already covers auth scoping — extend to X">
Gap work (the only new code needed):
- [ ] sub-task → owner @member → branch feat/task-n-<slug>
Demo line: <one sentence this contributes to the pitch>
```

Rules:
- One organizer task may split into 2–4 sub-issue PRs so multiple members earn attribution from ONE deliverable (e.g., Virat does its UI states, Nikhil its API validation, Rai its docs/demo script).
- If a task is already satisfied by foundation code, the "gap work" is wiring/exposing/testing it — still real PRs, still attributed.
- Descope order when time runs short: correctness of demo path > breadth of tasks > polish.

---

## 7. Board Setup

- GitHub Projects → columns `Backlog · In Progress · In Progress (Review) · Done`
- Automation: PR opened→In Review; PR merged→Done; issue closed→Done
- Branch protection on `main`: require 1 approving review (not author), passing CI
- Every card links an issue; every issue links its closing PR

---

## 8. Open Questions

- [ ] **Organizer task list — get it / confirm release time ASAP; everything in Phase 2 hangs on this**
- [ ] Krish's GitHub username? (history email = animeit158@gmail.com; account shown = akyourowngames — confirm same person/account)
- [ ] GitHub usernames for Nikhil, Virat, Rai (+ do they have accounts yet?)
- [ ] `.cursor/`: keep or delete?
- [ ] `docs/superpowers/`: keep or delete?
- [ ] License mismatch (MIT badge vs Proprietary notice in README) — pick one
- [ ] Confirm Option D squash with whole team before force-push (backup branch makes it reversible)
