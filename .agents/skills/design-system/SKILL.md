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

## The shell is a fixed-height column — nothing is positioned

```
h-dvh flex flex-col
  header  flex-none
  main    flex-1 min-h-0 overflow-y-auto
  nav     flex-none + pb-[env(safe-area-inset-bottom)]
```

`dvh`, not `h-full`: Safari's address bar collapses on scroll and changes the visual
viewport, while `height:100%` resolves against the stale value. `min-h-0` on `main` or the
flex child grows instead of scrolling, and then the *page* scrolls and carries the header
away.

**Do not make the tab bar `fixed`.** It was, and it floated mid-screen on a real iPhone with
white space beneath it. As a flex child it cannot be mis-positioned, and no page needs
bottom padding to clear it. `scripts/shots.mjs` asserts the page does not scroll and the
bar's bottom equals the viewport bottom.

## Brand: Triple A Gym

Black (`bg-chrome`) and high-vis yellow (`--color-brand: #f9e54c`, sampled from the gym's
own flyers). The chrome — header and tab bar — is black with yellow for the active state;
yellow on black clears contrast comfortably, yellow on white does not.

**Yellow is identity, never status.** Chrome, the logo, and the single most important action
on a screen (`<Button variant="brand">` — the flyers spend yellow exactly this way). Green,
amber and red still mean payment state and nothing else; spreading yellow around dilutes the
glance and edges it toward the amber that means "ending soon".

The logo lives at `public/logo.png` (and `apple-touch-icon.png`).

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
