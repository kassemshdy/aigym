/**
 * Hand-rolled SVG instead of a charting library: ~400 bytes against ~90 KB for Recharts,
 * which is most of our entire JS budget. See .agents/skills/perf-budget.
 *
 * Always rendered left-to-right, even in Arabic — a time axis that flips direction with
 * the UI language is harder to read, not easier.
 */
export function Sparkline({
  values,
  width = 160,
  height = 44,
}: {
  values: number[]
  width?: number
  height?: number
}) {
  if (values.length < 2) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const dx = width / (values.length - 1)
  const points = values.map((v, i) => [i * dx, height - ((v - min) / span) * (height - 6) - 3])
  const d = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')
  const last = points[points.length - 1]

  return (
    // Wrapped rather than dir-attributed: SVG elements do not take `dir`.
    <span dir="ltr" className="inline-block">
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r="3" fill="currentColor" />
    </svg>
    </span>
  )
}
