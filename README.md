# AIGym

Gym management for Lebanese gyms. Three surfaces — manager, coach on an iPad, and member —
plus an AI layer that drafts training and nutrition plans for a coach to approve.

Arabic first, works offline, USD, WhatsApp reminders, and light enough for a cheap Android
phone.

## Status

Phase 1: clickable prototype, mock data, no backend. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Run it

```bash
cd apps/web
npm install
npm run dev
```

Opens on http://localhost:5173 in Arabic. The `EN` button switches language; the
الإدارة / الكوتش / المشترك switcher in the header walks the three surfaces (prototype only
— real auth arrives in Phase 2).

## Docs

- [ROADMAP.md](docs/ROADMAP.md) — the six phases
- [DECISIONS.md](docs/DECISIONS.md) — what was decided and what it costs to reverse
- [MARKET.md](docs/MARKET.md) — competitor research
- [DATA_MODEL.md](docs/DATA_MODEL.md) — target schema
- [AGENTS.md](AGENTS.md) — how to work on this repo
