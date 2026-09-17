import type { Lang } from '@/i18n'

/**
 * Content is either a plain string (a member typed it, so it is already in their
 * language) or a bilingual pair from seed data. `text()` resolves both.
 */
export type Text = string | { ar: string; en: string }

export const text = (value: Text, lang: Lang) =>
  typeof value === 'string' ? value : value[lang]

/** Arabic separates list items with an Arabic comma, not a Latin one. */
export const listSep = (lang: Lang) => (lang === 'ar' ? '، ' : ', ')

/** USD only — one currency, no rate, no conversion. See docs/DECISIONS.md. */
export const usd = (n: number) => `$${n.toLocaleString('en-US')}`

export const shortDate = (iso: string, lang: Lang) =>
  new Date(iso).toLocaleDateString(lang === 'ar' ? 'ar-LB' : 'en-GB', {
    day: 'numeric',
    month: 'short',
  })

export const daysUntil = (iso: string) =>
  Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000)

export const initials = (name: string) =>
  name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')

export const mmss = (total: number) =>
  `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`

/** Live check-ins carry a full ISO timestamp; mock check-ins are seeded as
 * a bare "HH:MM" display string already. Pass either through unchanged. */
export const hhmm = (value: string) => {
  if (!value.includes('T')) return value
  const d = new Date(value)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
