import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function Card({
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { children: ReactNode }) {
  return (
    <div className={cn('rounded-2xl border border-line bg-surface', className)} {...rest}>
      {children}
    </div>
  )
}

export function CardTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
      <h2 className="text-[15px] font-bold">{children}</h2>
      {action}
    </div>
  )
}
