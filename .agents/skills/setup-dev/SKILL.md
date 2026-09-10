---
name: setup-dev
description: Get the project running locally and verify a change before committing. Read this on first run or when a command fails.
---

# Setting up

```bash
cd apps/web
npm install
npm run dev
```

Opens on `http://localhost:5173`, in Arabic. The `EN`/`ع` button in the header switches
language and writes the choice to `localStorage` under `aigym.lang`.

The header also carries a prototype-only role switcher (الإدارة / الكوتش / المشترك). It
exists so one browser can walk all three surfaces without three logins; it disappears in
Phase 2 when real auth arrives.

## Before you commit

```bash
npm run verify
```

That is `typecheck` → `rtl` → `build` → `budget`. All four must pass. If `budget` fails,
read `.agents/skills/perf-budget`.

## Screenshotting every screen

```bash
npm run build
npx vite preview --port 4173 &
node scripts/shots.mjs ./shots
```

Renders 11 screens × 2 languages and fails on a wrong `dir`, horizontal overflow, or any
console error. Use it as a regression test after layout work, not just to look at pictures.

Chromium is at `/opt/pw-browsers/chromium` in the cloud environment; override with
`CHROMIUM_PATH` elsewhere.

## Phase 1 has no backend

There is no API, no database, no auth. All data is in `src/mocks/data.ts` and all writes
are component state that resets on reload. That is deliberate — do not add a server until
Phase 2 starts.
