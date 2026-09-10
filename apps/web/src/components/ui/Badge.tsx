import { useTranslation } from 'react-i18next'
import type { DuesStatus } from '@/mocks/types'
import { cn } from '@/lib/cn'

/** Green/amber/red are reserved for payment state and used nowhere else in the app. */
const TONE: Record<DuesStatus, string> = {
  paid: 'bg-paid-bg text-paid',
  soon: 'bg-soon-bg text-soon',
  due: 'bg-due-bg text-due',
}

export function StatusBadge({ status, big }: { status: DuesStatus; big?: boolean }) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center rounded-full font-bold',
        big ? 'px-4 py-2 text-base' : 'px-2.5 py-1 text-xs',
        TONE[status],
      )}
    >
      {t(`status.${status}`)}
    </span>
  )
}

export function Chip({
  active,
  onClick,
  children,
}: {
  active?: boolean
  onClick?: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'min-h-11 shrink-0 rounded-full px-4 text-sm font-semibold',
        active ? 'bg-ink text-white' : 'border border-line bg-surface text-muted',
      )}
    >
      {children}
    </button>
  )
}
