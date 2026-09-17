import { useState } from 'react'
import { Icon } from '@/components/ui/Icon'

/** A small "?" affordance for the one or two things on a screen that are
 * genuinely non-obvious — most of this product explains itself through
 * plain labels (the whole point of "no jargon"), so this is deliberately
 * used sparingly, not on every control. */
export function HelpTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false)

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label={text}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="text-muted border-line bg-surface flex size-9 shrink-0 items-center justify-center rounded-full border"
      >
        <Icon name="help" size={16} />
      </button>
      {open ? (
        <>
          <button
            type="button"
            aria-label={text}
            tabIndex={-1}
            className="fixed inset-0 z-30 cursor-default"
            onClick={() => setOpen(false)}
          />
          <span
            role="tooltip"
            className="border-line bg-surface absolute end-0 top-full z-40 mt-2 w-64 rounded-xl border p-3 text-start text-sm font-medium shadow-lg"
          >
            {text}
          </span>
        </>
      ) : null}
    </span>
  )
}
