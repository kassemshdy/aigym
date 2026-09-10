---
name: i18n-rtl
description: Adding user-facing text, or building any layout with a direction. Arabic is the default language and RTL the default direction.
---

# Arabic first, RTL first

Arabic is the product's primary language. English is a translation of it. Write the
Arabic string first, in **plain Levantine Arabic** — how a gym manager in Beirut talks,
not Modern Standard translated from an English software phrase. "مين جاي اليوم", not
"لوحة تحكم الحضور".

## Adding a string

1. Add the key to `src/i18n/ar.json`.
2. Add the same key to `src/i18n/en.json`. Both files must have identical key sets.
3. Use it: `const { t } = useTranslation()` → `t('coach.queue.title')`.

Never put user-facing text directly in JSX. Check parity any time you touch either file:

```bash
node -e "
const k=o=>Object.entries(o).flatMap(([a,b])=>typeof b==='object'?k(b).map(x=>a+'.'+x):[a]);
const ar=k(require('./src/i18n/ar.json')), en=k(require('./src/i18n/en.json'));
console.log('only in ar:', ar.filter(x=>!en.includes(x)));
console.log('only in en:', en.filter(x=>!ar.includes(x)));
"
```

## Direction

`src/i18n/index.ts` sets `<html lang>` and `<html dir>` on load and on every language
change. **Nothing else in the app reads the language to decide a side.** If you find
yourself writing `lang === 'ar' ? 'right' : 'left'`, you are working around the layout
instead of writing it.

Use logical utilities only:

| Never | Always |
|---|---|
| `ml-2` / `mr-2` | `ms-2` / `me-2` |
| `pl-4` / `pr-4` | `ps-4` / `pe-4` |
| `left-0` / `right-0` | `start-0` / `end-0` |
| `text-left` / `text-right` | `text-start` / `text-end` |
| `border-l` / `border-r` | `border-s` / `border-e` |

`npm run rtl` fails the build on physical utilities inside class strings. It ignores
English prose in comments and data, so "left-shoulder injury" is fine.

## Mixed Arabic and numbers — the bug that looks like a typo

Putting an Arabic label inside `dir="ltr"` reorders the whole run and produces
nonsense like `4 × 8-10 · 60 آخر مرةkg`.

Wrap **only the numeric run**, and use `<bdi>`:

```tsx
// Wrong — the Arabic label is dragged into the LTR run
<p dir="ltr">{sets} × {reps} · {t('coach.session.lastTime')} {weight}kg</p>

// Right — each numeric run is isolated, the Arabic stays in the page direction
<p>
  <bdi className="tnum">{sets} × {reps}</bdi>
  {' · '}{t('coach.session.lastTime')}{' '}
  <bdi className="tnum">{weight} {t('common.kg')}</bdi>
</p>
```

Phone numbers, clock times, and money are pure-Latin runs and take plain `dir="ltr"`.

Charts stay left-to-right in both languages — a time axis that flips with the UI language
is harder to read, not easier. `Sparkline` handles this itself.
