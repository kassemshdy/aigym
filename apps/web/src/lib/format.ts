import type { Lang } from '@/i18n'

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
