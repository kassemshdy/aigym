import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-muted mb-1.5 block text-sm font-semibold">{label}</span>
      {children}
    </label>
  )
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        'min-h-tap w-full rounded-xl border border-line bg-surface px-4 text-base',
        'outline-none focus:border-ink',
        props.className,
      )}
    />
  )
}

/** Pick-don't-type: the default input for anything with a known set of answers. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  columns = 2,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  columns?: 2 | 3 | 4
}) {
  return (
    <div className={cn('grid gap-2', { 2: 'grid-cols-2', 3: 'grid-cols-3', 4: 'grid-cols-4' }[columns])}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            'min-h-tap rounded-xl px-3 text-sm font-semibold',
            value === o.value
              ? 'bg-ink text-white'
              : 'border border-line bg-surface text-ink active:bg-canvas',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 last:border-0">
      <span className="text-muted text-sm">{label}</span>
      <span className="text-end text-sm font-semibold">{value}</span>
    </div>
  )
}
