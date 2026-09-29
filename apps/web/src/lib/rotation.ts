/** Mirrors apps/api/app/domain/rotation.py: which day of a multi-day plan
 * comes next. Used by the mock adapter so the prototype rotates the same
 * way the server does. Decision 53. */
export function nextDay(dayCount: number, lastDay: number | null): number {
  if (dayCount <= 1 || lastDay === null || lastDay < 0 || lastDay >= dayCount) return 0
  return (lastDay + 1) % dayCount
}
