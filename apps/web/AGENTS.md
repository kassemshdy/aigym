# apps/web — React app

Vite + React 19 + TypeScript + Tailwind v4. No Next.js. Every surface runs on the API when
`VITE_API_URL` is set and on mocks when it isn't — manager (Phase 2), coach (Phase 3),
member (Phase 4), and the AI screens (Phase 5). The mock fallback is not legacy: it is how
this app stays demoable without a backend, so every query function keeps both branches.

## Layout

```
src/
├── main.tsx          entry — router, i18n, styles, service worker registration
├── App.tsx           the whole route tree
├── index.css         @theme tokens; the only place colours are defined
├── vite-env.d.ts     types import.meta.env.VITE_API_URL
├── i18n/             en.json (default), ar.json, index.ts (sets <html lang/dir>)
├── lib/              format.ts (usd, dates, mmss, hhmm), whatsapp.ts, cn.ts
├── mocks/            types.ts + data.ts — member screens' only data source, and what
│                     data/mockAdapter.ts's mock fallback is built from
├── data/             manager + coach data layer (Phase 2/3 boundary, see below)
│   ├── client.ts       the only place `fetch` appears — bearer auth, Idempotency-Key,
│   │                   one silent refresh-and-retry on 401, offlineFetch() for floor
│   │                   writes (see offline/ below)
│   ├── types.ts        shapes the live API and the mock adapter both return
│   ├── mockAdapter.ts  adapts mocks/data.ts into those same shapes
│   ├── queries.ts      the functions feature components actually call
│   └── useAsync.ts     thin read-side hook — no TanStack Query, see decisions
├── offline/          the Phase 3 outbox — see .agents/skills/offline-sync
│   ├── db.ts            hand-rolled IndexedDB wrapper, one object store
│   ├── outbox.ts        enqueue/listPending/replay — one ordered queue, oldest-first
│   └── OfflineProvider.tsx  tracks connectivity + pending count, replays on reconnect
├── gym/
│   └── GymProvider.tsx  the gym's own name and logo, fetched once from GET /gyms/me and
│                      read by every screen through useGym()/useGymName(). Nothing may
│                      import the `gym` const from `src/mocks/data` — that const is now
│                      only the mock adapter's seed, and importing it elsewhere is how
│                      this product was hard-coded to one tenant
├── components/
│   ├── ui/           the design system — check here before writing a component
│   └── AppShell.tsx  header (gym name + logo, sync badge reads OfflineProvider), language
│                      toggle, role switcher, bottom tabs
└── features/
    ├── manager/      Home, Members, MemberDetail, AddMember, Payments, Lapsed, Staff,
    │                 Login, Plans (the gym's own prices — they feed every dues figure),
    │                 Settings (its name and logo), Import (a notebook export, parsed
    │                 server-side — nothing here parses a CSV, see decision 37), Insights
    │                 (the owner dashboard — the numbers the GTM guarantee is settled on,
    │                 served by GET /analytics/summary)
    ├── coach/        Queue, CheckIn, MemberCard, Session, AiDrafts (the approval inbox —
    │                 decision 10), GenerateAiButton (asks for a draft — decision 31)
    ├── programs/     ProgramEditor — plan assign/edit, shared by manager and coach,
    │                 mounted at both /manager/programs/:id and /coach/programs/:id so
    │                 AppShell's tab bar shows the right surface
    └── member/       Login, Today, Food, Chat, Photos, Videos, Progress, Profile
```

`src/state/store.tsx` holds member-app prototype state (sign-in, food log, progress
photos, chat transcripts) — member screens read it through `useStore()`. Manager and coach
screens do not use it; their state is `src/data/queries.ts` reads/writes plus local
component state, since there is nothing member-app-specific to share a reducer with.
(Coach's session/effort feedback used to write here too — removed once `CoachSession`
started persisting `effort_band` through the real API in Phase 3; nothing ever read the
mock copy.)

`src/mocks/agents.ts` is the stand-in for the two assistants. The authority boundary lives
there and in the store: a reply may carry `food` (log it) or `draft` (escalate to the
coach), never a program change.

## Conventions

- One screen per file, exported as a named component; routes are wired only in `App.tsx`.
- Bilingual content in mocks is `{ ar, en }`, read through `text(value, lang)` from
  `lib/format.ts` — which also accepts a plain string for anything a member typed.
- `lang` comes from `i18n.language as Lang`. Use it to pick **content**, never to pick a
  side or a direction — see `.agents/skills/i18n-rtl`.
- Money renders through `usd()` in `lib/format.ts`. Never format a currency inline.
- WhatsApp messages go through `waLink()` with a `t('whatsapp.*')` template. Never build a
  `wa.me` URL by hand.
- Anything a member writes or photographs goes through `useStore()` actions. Do not add a
  second place that mutates food entries, photos, or chat.
- New progress-photo code starts from `sharedWithCoach: false`. If you find yourself
  writing a default that shares, stop and read decision 11.
- Manager and coach reads go through `src/data/useAsync.ts` (`const { data, loading, error
  } = useAsync(fn, deps)`); writes go through `src/data/queries.ts` functions, which attach
  an `Idempotency-Key` automatically (`client.ts`'s `newIdempotencyKey()`) — never call
  `apiFetch` for a POST/PATCH/DELETE without going through one of those functions.
- A **floor write** — workout sessions/sets, nutrition logs, check-in status — goes through
  `offlineFetch()` in `client.ts`, not `apiFetch()` directly, and its `queries.ts` function
  takes a `localEcho` built from the input so the UI has something to show immediately even
  when the write is queued, not sent. Manager writes (members/plans/payments) stay on
  `apiFetch()` — that scope line is decision 23 in `docs/DECISIONS.md`, not an oversight.

## Before committing

```bash
npm run verify
```

If you touched layout, also run `scripts/shots.mjs` (see `.agents/skills/setup-dev`) — it
catches direction and overflow regressions that typecheck cannot.

## How this is served in production

`Dockerfile` (Node builds → Caddy serves `dist/`) and `Caddyfile` sit in this directory, and
Railway's service root directory points here. Two rules when touching either:

- **Never remove `try_files {path} /index.html`.** Every route except `/` is client-side;
  without it a refresh or a pasted link 404s.
- **Never cache the HTML.** `/assets/*` is content-hashed and immutable; everything else is
  `no-cache` — `dist/sw.js` included, since it isn't under `/assets/` either, which is
  exactly what a service worker needs: the browser must always revalidate it to notice a
  new version. A stale shell after a redeploy points at assets that no longer exist.

Test both without Docker: `npm run build`, then
`PORT=8080 caddy run --config Caddyfile --adapter caddyfile`, then curl a deep link. See
`docs/DEPLOY.md`.

## The public landing page

`/` is the marketing page (`src/features/public/Landing.tsx`), not a redirect into
`/manager` — see decision 39. It lives outside `AppShell`, so none of the shell's rules
(`h-dvh`, the tab bar, the role switcher) apply to it; it is an ordinary scrolling
document with its own header and language toggle.

Its screenshots are the real app, one set per language, committed under `public/landing/`:

```bash
npm run build
npx vite preview --port 4173 &
node scripts/landing-shots.mjs      # writes public/landing/*.webp
```

Run it against a build with **no `VITE_API_URL`**, so the shots carry the seeded gym
rather than whatever is in a real database. The page covers **most of the app** — the
script's `SHOTS` list is the authoritative inventory, so read it rather than this
paragraph — in two tiers: seven narrative sections rendered large, and three galleries
(front desk, floor, member's phone) rendered small and encoded small to match. A gallery
of full-size screenshots is most of a megabyte a phone on a congested network pays for
and cannot see.

**Regenerate after changing any screen in that list** — otherwise the landing page is
advertising a version of the product that no longer exists. Adding a screen means a row
in `SHOTS`, a `landing.tiles.<stem>` caption in both `en.json` and `ar.json`, and the
stem in `GALLERIES` in `Landing.tsx`.

Do not confuse it with `scripts/shots.mjs`. That one is a test: it scrolls `main` to the
bottom to prove the tab bar stays put, which is the wrong frame to sell with.

`VITE_CONTACT_PHONE` is optional. Set it and the hero grows a WhatsApp call-to-action;
leave it unset and that button does not render, because a dead contact link is worse than
no contact link.

## Recording the demo video

`scripts/demo.mjs` drives the real app and records a captioned walkthrough.

```bash
npm run build
npx vite preview --port 4173 &
node scripts/demo.mjs en ./out       # or: ar
ffmpeg -i out/*.webm -vf "scale=1080:-2,fps=30" -c:v libx264 -crf 23 \
  -pix_fmt yuv420p -movflags +faststart demo-en.mp4
```

**The transcode is not optional.** Playwright's bundled ffmpeg is VP8-only, and a `.webm`
will not play on an iPhone or forward through WhatsApp on iOS.

## Phase 2/3 boundary

`src/data/` (plus `src/offline/` for floor writes) is the only place `fetch` appears —
never add one to a feature component; that boundary is exactly what made adding the
offline outbox in Phase 3 possible without touching every screen. Manager and coach
components import functions from `src/data/queries.ts`, never from `src/mocks/data` and
never `@/data/client` directly. `VITE_API_URL` unset ⇒ `queries.ts` calls the mock adapter
instead of the API; every function returns the identical shape either way, so a screen
does not know or care which path it is on.

Adding a new manager or coach read or write: add the live call to `queries.ts` (through
`apiFetch` — or `offlineFetch` if it's a floor write, see Conventions above — in
`client.ts`), add the matching mock implementation to `mockAdapter.ts` returning the exact
same shape, and only then wire the component. A `queries.ts` function with no mock branch
breaks `main`'s mock-only build — see the "must stay deployable" invariant in
`docs/DECISIONS.md`.

Every surface has now crossed this boundary, so there is no "still on mocks" list left to
consult — but the rule above is unchanged and still the thing that breaks the build when
skipped.

The Phase 5 AI calls are the same pattern with one wrinkle: mock mode has no model to call,
so `mockSendChatMessage` falls back to `mocks/agents.ts`'s regex `replyTo()`,
`mockEstimateFoodEntry` picks from `mocks/data.ts`'s `foodGuesses`, and
`mockGenerateAiDraft` writes a canned bilingual draft. They are stand-ins for a model, not
for a network layer — the shape they return is exactly what the API returns.
