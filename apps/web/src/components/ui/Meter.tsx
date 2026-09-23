/**
 * A rate drawn as a filled bar — one div inside another, for the same
 * reason Sparkline is hand-rolled SVG: a charting library costs ~90 KB
 * against a 200 KB budget (.agents/skills/perf-budget).
 *
 * Neutral ink on purpose. Green/amber/red are reserved for a member's
 * payment state and yellow is identity, so neither may carry a value here
 * — a gym-wide collection rate is a number, not a status badge.
 *
 * No physical direction anywhere: the fill is an ordinary block child, so
 * it grows from the inline start and mirrors itself in Arabic.
 */
export function Meter({ value, label }: { value: number | null; label: string }) {
  // `null` means nothing fell due, which is not the same as 0% — an empty
  // track says "no data" where a zero-width fill would claim a measured
  // total failure.
  const pct = value === null ? null : Math.round(Math.min(Math.max(value, 0), 1) * 100)

  return (
    <div
      role="img"
      aria-label={label}
      className="bg-canvas border-line h-3 w-full overflow-hidden rounded-full border"
    >
      {pct === null ? null : (
        <div className="bg-ink h-full rounded-full" style={{ width: `${pct}%` }} />
      )}
    </div>
  )
}
