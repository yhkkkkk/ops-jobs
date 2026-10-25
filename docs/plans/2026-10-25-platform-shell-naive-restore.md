# Platform Shell Naive Restore — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans (or superpowers:executing-plans) to implement this plan task-by-task.

**Goal:** Restore job / ops platform shells to old Arco density and behavior, implemented with Naive UI + Lucide and native collapsed menus (no `compact-nav`).

**Design:** `docs/plans/2026-10-25-platform-shell-naive-restore-design.md`

**Constraints:**

- Scope: `Layout.vue`, `OpsLayout.vue`, `layoutShell.test.ts` only
- Keep Naive + Lucide; no Arco; no `compactNavItems` / `compact-nav`
- Keep mobile drawer at `MOBILE_BREAKPOINT = 520`
- Job shell keeps `workspaceMode` auto-collapse + restore
- Do not extract `PlatformShell`; do not change business pages / routes / auth model
- Work in the **current dirty checkout** (Naive migration WIP). A clean worktree from HEAD would reintroduce Arco layouts and drop required App/main Naive providers.

**Architecture (required behavior):**

- Two shells, readable structure (not minified one-liners)
- Desktop: sider 200 / collapsed 64, Naive `n-menu` `:collapsed`
- Mobile: hide sider, left drawer with full menu
- Menu selection via `menuConfig` + route watch; clear `openKeys` when collapsed

---

### Task 1: Strengthen shell contract tests (TDD)

**Files:**

- Modify: `frontend/src/views/__tests__/layoutShell.test.ts`

**Behavior:**

- Keep existing Naive / no-Arco / no-`compactNavItems` / drawer / breakpoint assertions
- Add job-shell-only checks: `workspaceMode`, `content--workspace`, `previousCollapsedState`
- Add both-shell checks for readable structure markers (multi-line friendly): `class="layout"`, brand titles `作业平台` / `运维台`, `collapsed-width="64"` or `:collapsed-width="64"`
- Add OpsLayout platform switch: `切换到作业平台`; job: `切换到运维台`

**Validation:**

```bash
cd frontend && pnpm exec vitest run src/views/__tests__/layoutShell.test.ts
```

**Expected:** Fail on new assertions that current minified shells miss (e.g. `workspaceMode` string may already pass on Layout; tighten until at least one intentional gap fails, or proceed if already green then Task 2 still rewrites for readability/density).

**Acceptance:** Test file encodes design contract; suite is the gate for Tasks 2–3.

---

### Task 2: Rewrite `Layout.vue` (job platform)

**Files:**

- Modify: `frontend/src/views/Layout.vue`
- Reference: `git show HEAD:frontend/src/views/Layout.vue` (behavior/visual intent)

**Behavior:**

- Readable SFC: template / script / scoped style as separate blocks (no single-line script dump)
- Template: `n-layout has-sider` → sider (desktop) + drawer (mobile) + header + `content` / `content--workspace`
- Sider: width 200, collapsed-width 64, logo brand J / 作业平台 / Ops Job, `n-menu` with options + icons
- Header: collapse/mobile toggle, breadcrumb, superuser ops switch, user dropdown logout
- Script: same `menuConfig` routes as today; `workspaceMode` watch; mobile resize; logout / platform switch semantics unchanged
- Style: port old density (logo 68, header 64, content 28/16, menu 40/36, accent soft selected) via `:deep(.n-*)` — no compact-nav rules

**Validation:**

```bash
cd frontend && pnpm exec vitest run src/views/__tests__/layoutShell.test.ts
```

**Acceptance:** Job shell matches contract; collapsed uses Naive menu only; workspace mode still present.

---

### Task 3: Rewrite `OpsLayout.vue` (ops console)

**Files:**

- Modify: `frontend/src/views/OpsLayout.vue`
- Reference: `git show HEAD:frontend/src/views/OpsLayout.vue`

**Behavior:**

- Same shell patterns as Task 2 (readable structure, drawer, Naive collapsed menu, density CSS)
- Brand O / 运维台 / Ops Console; ops `menuConfig` / menu options unchanged
- No `workspaceMode`
- Header always shows switch to job platform (as current Naive WIP; keep consistent with existing ops shell behavior in WIP)
- Longest-prefix `findMenuInfo` sort retained for agent sub-routes

**Validation:**

```bash
cd frontend && pnpm exec vitest run src/views/__tests__/layoutShell.test.ts
```

**Acceptance:** Ops shell matches contract; parity with job shell UX except workspace/brand/menu content.

---

### Task 4: Verify and smoke

**Files:** none new

**Validation:**

```bash
cd frontend && pnpm exec vitest run src/views/__tests__/layoutShell.test.ts src/views/__tests__/jobPlatformShell.test.ts
```

Optional if time: `pnpm type-check` (only if project script exists and is fast enough).

**Acceptance:**

- Shell tests green
- No Arco / compact-nav in either layout
- Manual spot-check (when browser available): expand/collapse, menu navigate, mobile drawer, workspace route collapses sider

**Out of scope for commit:** Do not commit unless user asks. Leave WIP with other migration files.

---

## Execution notes

- Prefer editing current files in place; do not reset/checkout HEAD versions of other migration files.
- If Vitest baseline fails for unrelated migration files, record and ignore; only shell tests are required green for this plan.
- YAGNI: no shared shell component, no theme rewrite, no E2E in this batch.
