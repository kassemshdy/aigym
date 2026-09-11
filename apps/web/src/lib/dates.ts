import type { Lang } from '@/i18n'

/** Hand-rolled rather than pulling in a date library — see .agents/skills/perf-budget. */

export const isoDay = (d: Date) => d.toISOString().slice(0, 10)

export const addDays = (d: Date, n: number) => {
  const out = new Date(d)
  out.setDate(out.getDate() + n)
  return out
}

/** Fourteen days starting today — the window a member actually plans within. */
export const nextDays = (count: number, from = new Date()) =>
  Array.from({ length: count }, (_, i) => addDays(from, i))

export const weekdayShort = (d: Date, lang: Lang) =>
  d.toLocaleDateString(lang === 'ar' ? 'ar-LB' : 'en-GB', { weekday: 'short' })

export const dayLabel = (d: Date, lang: Lang) =>
  d.toLocaleDateString(lang === 'ar' ? 'ar-LB' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'short' })

export const isToday = (d: Date) => isoDay(d) === isoDay(new Date())
