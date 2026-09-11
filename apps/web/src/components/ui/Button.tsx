import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

type Variant = 'primary' | 'brand' | 'secondary' | 'ghost' | 'danger'
type Size = 'md' | 'lg'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-ink text-white active:bg-ink-soft',
  /*
   * The gym's signature: high-vis yellow, black text. Used for the ONE action that
   * matters most on a screen — the flyers spend yellow the same way. Overusing it makes
   * it stop meaning anything, and edges it toward the amber that means "ending soon".
   */
  brand: 'bg-brand text-chrome active:bg-brand-dim',
  secondary: 'bg-surface text-ink border border-line active:bg-canvas',
  ghost: 'bg-transparent text-ink active:bg-line/60',
  danger: 'bg-due text-white active:opacity-90',
}

/** md = 48px, lg = 56px. Never smaller: the coach taps this with the iPad on a rack. */
const SIZES: Record<Size, string> = {
  md: 'min-h-tap px-4 text-[15px]',
  lg: 'min-h-tap-lg px-6 text-base',
}

/** Same look, for anchors and router links that must stay real links. */
export function buttonClass(variant: Variant = 'primary', size: Size = 'md', full = false) {
  return cn(
    'inline-flex items-center justify-center gap-2 rounded-xl font-semibold',
    'transition-[background-color,opacity]',
    VARIANTS[variant],
    SIZES[size],
    full && 'w-full',
  )
}

export function Button({
  variant = 'primary',
  size = 'md',
  full,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
  full?: boolean
  children: ReactNode
}) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl font-semibold',
        'transition-[background-color,opacity] disabled:opacity-40',
        VARIANTS[variant],
        SIZES[size],
        full && 'w-full',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
