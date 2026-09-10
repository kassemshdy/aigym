---
name: design-system
description: Adding or restyling any component. Covers tokens, touch targets, the reserved colour meanings, and the existing component inventory.
---

# Design system

Tokens live in `apps/web/src/index.css` under `@theme`. Use token utilities
(`bg-surface`, `text-muted`, `border-line`) — never a raw hex or an arbitrary value.

## Colour has meaning here

| Token | Utility | Meaning |
|---|---|---|
| `--color-ink` | `bg-ink` `text-ink` | Primary actions, active nav, avatars |
| `--color-muted` | `text-muted` | Secondary text |
| `--color-line` | `border-line` | Borders, dividers |
| `--color-surface` / `--color-canvas` | `bg-surface` / `bg-canvas` | Cards / page background |
| `--color-paid` + `-bg` | `text-paid` `bg-paid-bg` | **Paid. Reserved.** |
| `--color-soon` + `-bg` | `text-soon` `bg-soon-bg` | **Ending soon / warning. Reserved.** |
| `--color-due` + `-bg` | `text-due` `bg-due-bg` | **Payment due. Reserved.** |

Green, amber and red mean payment state and nothing else. A coach glancing at an iPad from
two metres away reads the colour before the word — if green ever means "success" somewhere
decorative, that glance becomes unreliable. The brand accent is ink (near-black), which is
why primary buttons are black.

## The bottom tab bar covers content unless you measure it properly

The bar is `4rem` **plus** `env(safe-area-inset-bottom)` — the home indicator on a notched
phone, and Safari's bottom chrome. Use the `--nav-total` custom property in `index.css`,
which is that whole sum:

```css
padding-bottom: calc(var(--nav-total) + 1.5rem);  /* content clearing the bar */
bottom: var(--nav-total);                          /* something pinned above the bar */
```

Never hard-code `4rem` or `--spacing(nav)` for this. **Headless browsers report the inset as
`0`**, so an overlap looks perfect in the screenshot suite and only appears on a real handset.
`scripts/shots.mjs` now fakes a 34px inset on phone screens and fails if the last piece of
content is hidden behind the bar — that check exists because this shipped once.

## Back navigation

Use `BackLink` (`components/ui/BackLink.tsx`). Never write a literal `←`: that character does
not mirror, so it points *forward* in Arabic. `BackLink` rotates a chevron with
`rotate-180 rtl:rotate-0` and is a full 48px tap target.

## Touch targets

`--spacing-tap` = 48px (phone minimum), `--spacing-tap-lg` = 56px (coach iPad). Use
`min-h-tap` / `min-h-tap-lg`. Nothing interactive goes below 44px — the coach taps this
with chalky hands, at arm's length, on a rack.

## Component inventory — check before writing a new one

`src/components/ui/`

| Component | Use for |
|---|---|
| `Button` / `buttonClass()` | Actions. `buttonClass()` gives an `<a>` or `<Link>` the same look without faking a button |
| `Card` / `CardTitle` | Every grouped block |
| `StatusBadge` | Dues state. Never build a second payment chip |
| `Chip` | Filters |
| `Avatar` | Member identity — initials, no image loading |
| `Stepper` | Any number the coach enters during a session |
| `Segmented` | Any field with a known set of answers — the default over a text input |
| `Field` / `Input` / `Row` | Forms and label/value lists |
| `Sparkline` | Trends. Do not install a chart library |
| `Icon` | Icons. Add a path, do not install a package |
| `Page` / `Empty` | Screen wrapper and empty states |

## Typography and numbers

System font stack, IBM Plex Sans Arabic first if available. Put `tnum` on any number that
changes in place (weights, reps, timers, money) so it does not jitter.

Western digits everywhere, including in Arabic: gym owners and coaches read `60 kg`
faster than `٦٠`, and the whole fitness world writes weights this way.
