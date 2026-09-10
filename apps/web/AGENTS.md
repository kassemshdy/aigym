# apps/web — React app

Vite + React 19 + TypeScript + Tailwind v4. No Next.js. Phase 1: mock data only.

## Layout

```
src/
├── main.tsx            entry — router, i18n, styles
├── App.tsx             the whole route tree
├── index.css           @theme tokens; the only place colours are defined
├── i18n/               ar.json (write first), en.json, index.ts (sets <html dir>)
├── lib/                format.ts (usd, dates, mmss), whatsapp.ts, cn.ts
├── mocks/              types.ts + data.ts — replaced by API calls in Phase 2
├── components/
│   ├── ui/             the design system — check here before writing a component
│   └── AppShell.tsx    header, language toggle, role switcher, bottom tabs
└── features/
    ├── manager/        Home, Members, MemberDetail, AddMember, Plans, Payments
    ├── coach/          Queue, MemberCard, Session, AiDrafts
    └── member/         Login, Today, Food, Chat, Photos, Videos, Progress, Profile
```

`src/state/store.tsx` holds prototype state (sign-in, food log, progress photos, chat
transcripts). Components read it through `useStore()` rather than touching mocks, so
Phase 2 can swap the implementation for the API plus the offline outbox without touching
a screen.

`src/mocks/agents.ts` is the stand-in for the two assistants. The authority boundary lives
there and in the store: a reply may carry `food` (log it) or `draft` (escalate to the
coach), never a program change.

## Conventions

- One screen per file, exported as a named component; routes are wired only in `App.tsx`.
- Bilingual content in mocks is `{ ar, en }` and read as `field[lang]`.
- `lang` comes from `i18n.language as Lang`. Use it to pick **content**, never to pick a
  side or a direction — see `.agents/skills/i18n-rtl`.
- Money renders through `usd()` in `lib/format.ts`. Never format a currency inline.
- WhatsApp messages go through `waLink()` with a `t('whatsapp.*')` template. Never build a
  `wa.me` URL by hand.
- Anything a member writes or photographs goes through `useStore()` actions. Do not add a
  second place that mutates food entries, photos, or chat.
- New progress-photo code starts from `sharedWithCoach: false`. If you find yourself
  writing a default that shares, stop and read decision 11.

## Before committing

```bash
npm run verify
```

If you touched layout, also run `scripts/shots.mjs` (see `.agents/skills/setup-dev`) — it
catches direction and overflow regressions that typecheck cannot.

## Phase 2 boundary

When the API arrives, `src/mocks/` is replaced by a data layer; components keep their
props. Do not add `fetch` calls to feature components — that is what makes the offline
outbox impossible to add later.
