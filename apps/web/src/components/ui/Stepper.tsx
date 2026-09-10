import { cn } from '@/lib/cn'

/**
 * Tap-only numeric entry. The coach never opens a keyboard mid-session:
 * the value starts at last session's number and moves in one-tap increments.
 */
export function Stepper({
  value,
  step,
  min = 0,
  suffix,
  onChange,
  size = 'md',
}: {
  value: number
  step: number
  min?: number
  suffix?: string
  onChange: (next: number) => void
  size?: 'md' | 'lg'
}) {
  const btn = size === 'lg' ? 'size-14 text-2xl' : 'size-12 text-xl'
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        aria-label="-"
        onClick={() => onChange(Math.max(min, +(value - step).toFixed(2)))}
        className={cn('rounded-xl border border-line bg-surface font-bold active:bg-canvas', btn)}
      >
        −
      </button>
      <div
        className={cn(
          'tnum min-w-16 text-center font-bold',
          size === 'lg' ? 'text-2xl' : 'text-lg',
        )}
      >
        {value}
        {suffix ? <span className="text-muted text-sm"> {suffix}</span> : null}
      </div>
      <button
        type="button"
        aria-label="+"
        onClick={() => onChange(+(value + step).toFixed(2))}
        className={cn('rounded-xl border border-line bg-surface font-bold active:bg-canvas', btn)}
      >
        +
      </button>
    </div>
  )
}
