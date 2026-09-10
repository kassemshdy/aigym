import { initials } from '@/lib/format'
import { cn } from '@/lib/cn'

export function Avatar({ name, size = 'md' }: { name: string; size?: 'md' | 'lg' }) {
  return (
    <div
      aria-hidden
      className={cn(
        'flex shrink-0 items-center justify-center rounded-full bg-ink font-bold text-white',
        size === 'lg' ? 'size-16 text-xl' : 'size-11 text-sm',
      )}
    >
      {initials(name)}
    </div>
  )
}
