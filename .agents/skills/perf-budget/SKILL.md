---
name: perf-budget
description: Adding a dependency, or anything that ships JavaScript. The budget is a product requirement, not a preference.
---

# 200 KB gzipped, enforced

```bash
npm run build && npm run budget
```

Fails the build over 200 KB of gzipped JS. Current usage is ~115 KB, so roughly 85 KB of
headroom exists — spend it deliberately.

## Why this is a product requirement

Members and managers are on mid-range Android phones on congested mobile networks, often
on generator power. A 500 KB bundle is a five-second blank screen, and a five-second blank
screen is a gym owner who goes back to the notebook. Target: first contentful paint under
2s at 4× CPU slowdown on slow 4G.

## Before adding a dependency

Ask, in order:

1. **Can existing code do it?** `Sparkline` is ~400 bytes of hand-written SVG. Recharts is
   ~90 KB gzipped — most of the remaining budget for one chart.
2. **Can 30 lines do it?** `cn()`, `Stepper`, and `Icon` all replace a package.
3. **Does it tree-shake?** Check the real cost: `npm run build && npm run budget`,
   before and after.

Icons in particular: `Icon.tsx` holds a hand-picked set of path strings. Add a path to it
rather than installing an icon package.

## If you are over budget

Do not raise the limit. In order of preference: drop the dependency, replace it with local
code, or lazy-load the route that needs it with `React.lazy`. Raising `LIMIT_KB` in
`scripts/check-budget.mjs` requires a line in `docs/DECISIONS.md` explaining what the
users get in exchange.
