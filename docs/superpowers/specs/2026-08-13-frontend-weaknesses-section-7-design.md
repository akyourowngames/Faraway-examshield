# Frontend Weaknesses — Audit §7 — Design Spec

**Date:** 2026-08-13
**Source:** `docs/PROJECT_WEAKNESSES_AUDIT.md` §7 (Frontend Weaknesses)
**Goal:** Resolve all six §7 findings with concrete, test-backed changes; verify via Vitest + `vitest-axe` + `npm run lint` + `next build`.

## Scope decisions (confirmed with user)
- **i18n:** scaffold + translate a representative Hindi slice (nav, login/signup, dashboard headings). No route/locale-segment changes.
- **Dependencies:** add `sonner` (toasts) and `vitest-axe` (a11y tests). i18n is a lightweight custom dictionary (React context) — no `next-intl`, no routing change.
- **Verification:** automated only (Vitest component/unit/axe tests + lint + `next build`). No manual browser run.

## Guiding principle
Lightweight, test-backed fixes that close each gap; no architectural rework; follow existing Tailwind + Testing Library patterns; every change ships with a test.

---

## §7.2 — Loading & error states
**Problem:** no global `error.tsx`/`loading.tsx`; `/api/*` failures have no consistent boundary.

**Changes**
- `web/src/app/error.tsx` (client) — segment error boundary; accessible `role="alert"` message + "Try again" button calling `reset()`.
- `web/src/app/global-error.tsx` (client) — root-layout error boundary (includes `<html>/<body>`).
- `web/src/app/loading.tsx` — route-level loading skeleton (`aria-busy`, spinner).
- `web/src/app/dashboard/error.tsx` and `web/src/app/dashboard/loading.tsx` — dashboard-scoped fallback + skeleton.

**Tests**
- `web/src/app/error.test.tsx` — renders error UI with a passed `error`; clicking "Try again" invokes `reset`.
- `web/src/app/loading.test.tsx` — renders skeleton, exposes `aria-busy`.

## §7.4 — Animations / `prefers-reduced-motion`
**Problem:** `framer-motion` used in ~20 components with no observed reduced-motion guard.

**Changes**
- `web/src/lib/use-prefers-reduced-motion.ts` — SSR-safe `matchMedia('(prefers-reduced-motion: reduce)')` hook; subscribes to change events; returns boolean (false on server/first paint).
- `web/src/components/Motion.tsx` — `FadeIn` wrapper over `framer-motion` that drops transform/transition (sets `initial={false}`, zero-duration) when reduced motion is on.
- Apply `FadeIn` to the most prominent animated surfaces: `components/sections/Hero.tsx` and dashboard page-enter wrappers. Remaining ~18 framer-motion sites documented as follow-up.

**Tests**
- `web/src/lib/use-prefers-reduced-motion.test.ts` — mocked `matchMedia` returns `true`/`false`; hook reflects value + updates on event.
- `web/src/components/Motion.test.tsx` — with reduced motion on, `FadeIn` renders children without an offset transform; with it off, applies the enter animation.

## §7.1 — Accessibility (focus / contrast)
**Problem:** [INFERRED] limited focus management / contrast checks; no a11y audit.

**Changes**
- `web/src/app/globals.css`:
  - `:focus-visible { outline: 2px solid <accent>; outline-offset: 2px; }`
  - `@media (prefers-reduced-motion: reduce)` block neutralizing non-essential transitions/animations.
- `web/src/components/SkipLink.tsx` — visually-hidden skip-to-content link, visible on focus, targets `#main-content`.
- `web/src/app/layout.tsx` — add `<main id="main-content">` landmark; set `lang` on `<html>`; mount `SkipLink` + `I18nProvider` + `Toaster`.
- `web/src/components/layout/Navbar.tsx` — `aria-label` on icon-only buttons.
- New `web/src/lib/a11y.test.tsx` — `axe()` over rendered login page + an empty dashboard; assert zero violations.

**Out of scope (residual):** full manual WCAG audit, color-contrast pass across every theme token.

## §7.5 — UX (toasts + empty states)
**Problem:** no toasts system (no `sonner`/`react-toastify`); no guided empty states.

**Changes**
- Add `sonner`; mount `<Toaster richColors position="top-right" />` in root `layout.tsx`.
- `web/src/components/ui/EmptyState.tsx` — icon + title + description + optional action button; used in a representative empty list (alerts or memory page).
- Wire one real toast on the evidence-upload failure path so the system is exercised, not decorative.

**Tests**
- `web/src/components/ui/EmptyState.test.tsx` — renders title/description; action button fires onClick.
- `web/src/lib/toast.test.tsx` — mounting `<Toaster />` + calling `toast('msg')` shows the message.

## §7.3 — Responsiveness / performance (heavy libs)
**Problem:** `react-simple-maps` + `recharts` heavy on low-end devices; no code-splitting observed.

**Changes**
- Wrap `web/src/components/sections/ThreatMap.tsx` (and any recharts usage) in `next/dynamic({ ssr:false })` with a skeleton fallback so they lazy-load off the initial bundle.

**Tests**
- `web/src/components/sections/LazyThreatMap.test.tsx` — wrapper mounts and shows the loading fallback (then resolves the component under `findBy`).

**Out of scope:** real-device performance budgeting, bundle-size CI gate.

## §7.6 — i18n (scaffold + Hindi slice)
**Problem:** [INFERRED] UI English-only for a product targeting Indian exam boards (NEET/JEE).

**Changes**
- `web/src/lib/i18n/index.tsx` — `I18nProvider` (React context) + `useI18n()` → `{ locale, setLocale, t }`; default `en`; persist `locale` to `localStorage`; `t(key)` falls back to `en` then to the key.
- `web/src/lib/i18n/dictionaries/en.ts`, `hi.ts` — nested key/value dictionaries.
- `web/src/components/LanguageSwitcher.tsx` — EN / हिंदी toggle in `Navbar`.
- Translate a representative slice: nav labels (Dashboard, Evidence, Alerts, Memory, Registry, Threats, Settings, Community Agents), login/signup headings + primary buttons, dashboard page headings.
- Apply `I18nProvider` in root `layout.tsx`; consume `t()` in the translated components.

**Tests**
- `web/src/lib/i18n/i18n.test.tsx` — provider `t()` returns EN then HI after `setLocale('hi')`; `LanguageSwitcher` toggles + persists to `localStorage`.

## Files created
- `web/src/app/error.tsx`, `global-error.tsx`, `loading.tsx`
- `web/src/app/dashboard/error.tsx`, `dashboard/loading.tsx`
- `web/src/lib/use-prefers-reduced-motion.ts`
- `web/src/components/Motion.tsx`
- `web/src/components/SkipLink.tsx`
- `web/src/components/ui/EmptyState.tsx`
- `web/src/components/LanguageSwitcher.tsx`
- `web/src/lib/i18n/index.tsx`, `dictionaries/en.ts`, `dictionaries/hi.ts`
- Tests: `error.test.tsx`, `loading.test.tsx`, `use-prefers-reduced-motion.test.ts`, `Motion.test.tsx`, `a11y.test.tsx`, `EmptyState.test.tsx`, `toast.test.tsx`, `LazyThreatMap.test.tsx`, `i18n.test.tsx`

## Files modified
- `web/src/app/globals.css` (focus-visible, reduced-motion block)
- `web/src/app/layout.tsx` (SkipLink, main landmark, providers, Toaster)
- `web/src/components/layout/Navbar.tsx` (aria-labels, LanguageSwitcher, i18n nav labels)
- `web/src/components/sections/Hero.tsx` (FadeIn)
- `web/src/components/sections/ThreatMap.tsx` (dynamic wrapper)
- `web/src/app/login/page.tsx`, `signup/page.tsx` (i18n strings)
- `web/src/app/dashboard/*` headings (i18n strings)
- `web/package.json` (add `sonner`, `vitest-axe`)

## Verification
1. `cd web && npm install` (pulls `sonner`, `vitest-axe`).
2. `npm run test` — all new component/unit/axe tests pass.
3. `npm run lint` — 0 errors.
4. `npm run build` — production build succeeds (validates `error.tsx`/`loading.tsx`/`next/dynamic`/i18n compile).

## Residual / explicitly out of scope
- Full Hindi translation of every string.
- Manual WCAG / color-contrast audit.
- Real-device performance budgeting + bundle-size CI gate.
- Onboarding wizard (only empty states + toasts delivered).
- Applying `FadeIn` to the remaining ~18 framer-motion sites (documented, not blocked).
