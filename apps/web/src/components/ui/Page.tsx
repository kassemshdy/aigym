import type { ReactNode } from 'react'

export function Page({ title, sub, children }: { title?: string; sub?: string; children: ReactNode }) {
  return (
    <div className="space-y-4 p-4 pb-[calc(--spacing(nav)+--spacing(6))]">
      {title ? (
        <div>
          <h1 className="text-xl font-extrabold">{title}</h1>
          {sub ? <p className="text-muted text-sm">{sub}</p> : null}
        </div>
      ) : null}
      {children}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-muted rounded-2xl border border-dashed border-line p-6 text-center text-sm">{children}</p>
}
