import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/Button'
import { TOUR_STEPS, type TourRole } from './tourSteps'

interface TourContextValue {
  start: (role: TourRole) => void
}

const TourContext = createContext<TourContextValue>({ start: () => {} })

const seenKey = (role: TourRole) => `aigym.tour.${role}.seen`

/** Measures the current step's target element, re-measuring on resize and
 * on DOM mutation (data can still be loading when the tour starts, so the
 * element may not exist yet at the first measurement). */
function useTargetRect(target: string | null): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null)

  useEffect(() => {
    function measure() {
      if (!target) {
        setRect(null)
        return
      }
      const el = document.querySelector<HTMLElement>(`[data-tour="${target}"]`)
      if (!el) {
        setRect(null)
        return
      }
      el.scrollIntoView({ block: 'center' })
      setRect(el.getBoundingClientRect())
    }

    // Deferred to a frame rather than called synchronously in the effect
    // body: the target may still be loading (data fetch not done yet), and
    // scrollIntoView needs layout to have settled first either way.
    const raf = requestAnimationFrame(measure)
    window.addEventListener('resize', measure)
    const observer = new MutationObserver(measure)
    observer.observe(document.body, { childList: true, subtree: true })

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', measure)
      observer.disconnect()
    }
  }, [target])

  return rect
}

/** Hand-rolled walkthrough overlay — no tour library. A spotlight ring
 * around the current step's element plus a tooltip bubble, positioned from
 * real measured pixels (getBoundingClientRect is always physical viewport
 * coordinates regardless of dir, so plain left/top here is correct, not a
 * violation of the ms-/me- rule that governs static Tailwind classes). */
export function TourProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const [role, setRole] = useState<TourRole | null>(null)
  const [stepIndex, setStepIndex] = useState(0)

  const steps = role ? TOUR_STEPS[role] : []
  const step = steps[stepIndex] ?? null
  const rect = useTargetRect(step?.target ?? null)

  // Memoized deliberately, unlike stop/next/back below: this is a context
  // Provider value's only ingredient, and an unmemoized start() gave the
  // Provider a fresh { start } object on every render (every step change,
  // every rect measurement) — useTourAutostart's effect depends on start,
  // so it kept tearing down and rescheduling its 500ms timer. That timer
  // firing mid-tour (whenever the user paused on a step for half a second)
  // called start(role) again and reset stepIndex to 0, which looked like
  // clicking Next sent the tour backward. start() itself has no external
  // dependencies beyond the two stable useState setters, so useCallback
  // with an empty array is safe here (unlike next(), which the React
  // Compiler already rejected memoizing because it reads steps.length).
  const start = useCallback((r: TourRole) => {
    setRole(r)
    setStepIndex(0)
  }, [])

  function stop() {
    if (role) localStorage.setItem(seenKey(role), '1')
    setRole(null)
    setStepIndex(0)
  }

  function next() {
    if (stepIndex + 1 >= steps.length) stop()
    else setStepIndex((i) => i + 1)
  }

  function back() {
    setStepIndex((i) => Math.max(0, i - 1))
  }

  // A ref rather than `stop` itself in the deps below: `stop` closes over
  // `role` and is recreated every render (this codebase has no
  // useCallback convention — it leans on the React Compiler instead, which
  // rejects manually memoizing a callback built from a plain derived
  // value like steps.length). The ref always calls the latest version
  // without the effect needing to re-subscribe on every render.
  const stopRef = useRef(stop)
  useEffect(() => {
    stopRef.current = stop
  })

  useEffect(() => {
    if (!role) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') stopRef.current()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [role])

  const contextValue = useMemo(() => ({ start }), [start])

  return (
    <TourContext.Provider value={contextValue}>
      {children}
      {role && step
        ? createPortal(
            <TourOverlay
              rect={rect}
              title={t(step.titleKey)}
              body={t(step.bodyKey)}
              stepIndex={stepIndex}
              total={steps.length}
              onNext={next}
              onBack={stepIndex > 0 ? back : undefined}
              onSkip={stop}
            />,
            document.body,
          )
        : null}
    </TourContext.Provider>
  )
}

export function useTour() {
  return useContext(TourContext)
}

/** Auto-starts a role's tour the first time its home screen mounts, once
 * ever per browser (localStorage) — replaying it afterward is a deliberate
 * action from the header, never automatic again. */
export function useTourAutostart(role: TourRole) {
  const { start } = useTour()
  useEffect(() => {
    if (localStorage.getItem(seenKey(role))) return
    const id = window.setTimeout(() => start(role), 500)
    return () => window.clearTimeout(id)
  }, [role, start])
}

function TourOverlay({
  rect,
  title,
  body,
  stepIndex,
  total,
  onNext,
  onBack,
  onSkip,
}: {
  rect: DOMRect | null
  title: string
  body: string
  stepIndex: number
  total: number
  onNext: () => void
  onBack?: () => void
  onSkip: () => void
}) {
  const { t } = useTranslation()
  const isLast = stepIndex === total - 1
  const pad = 8
  const bubbleWidth = 288
  // A generous estimate, not a measurement: the real height depends on how
  // long the translated title/body run. Only used to clamp the bubble
  // inside the viewport, so slight over/under-estimating just means the
  // bubble sits a little higher or lower than ideal — never off-screen,
  // which is what actually broke (see below).
  const bubbleHeightEstimate = 240
  const margin = 16

  const spotStyle: React.CSSProperties = rect
    ? {
        top: rect.top - pad,
        left: rect.left - pad,
        width: rect.width + pad * 2,
        height: rect.height + pad * 2,
      }
    : { display: 'none' }

  // Always clamped to the viewport, regardless of the target's own size —
  // a target taller than the viewport (e.g. the coach queue with many
  // check-ins) used to push the bubble's "below" position past the bottom
  // edge, making Next unclickable (Playwright caught this: "element is
  // outside of the viewport").
  const bubbleStyle: React.CSSProperties = rect
    ? (() => {
        const left = Math.min(Math.max(rect.left, margin), window.innerWidth - bubbleWidth - margin)
        const belowTop = rect.bottom + pad + 8
        const aboveTop = rect.top - pad - 8 - bubbleHeightEstimate
        const fitsBelow = belowTop + bubbleHeightEstimate <= window.innerHeight - margin
        const top = fitsBelow
          ? Math.max(belowTop, margin)
          : Math.min(Math.max(aboveTop, margin), window.innerHeight - bubbleHeightEstimate - margin)
        return { left, top, width: bubbleWidth }
      })()
    : { top: '50%', left: '50%', width: bubbleWidth, transform: 'translate(-50%, -50%)' }

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label={t('tour.skip')}
        className="absolute inset-0 bg-black/60"
        onClick={onSkip}
      />
      {rect ? (
        <div
          className="ring-brand pointer-events-none absolute rounded-xl ring-4 transition-[top,left,width,height]"
          style={spotStyle}
        />
      ) : null}
      <div className="bg-surface absolute rounded-2xl p-4 shadow-xl" style={bubbleStyle}>
        <p className="text-[15px] font-bold">{title}</p>
        <p className="text-muted mt-1 text-sm">{body}</p>
        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="tnum text-muted text-xs">
            {stepIndex + 1}/{total}
          </span>
          <div className="flex items-center gap-2">
            {onBack ? (
              <Button variant="secondary" onClick={onBack} className="px-3 text-sm">
                {t('tour.back')}
              </Button>
            ) : (
              <button type="button" onClick={onSkip} className="text-muted px-2 text-sm font-semibold">
                {t('tour.skip')}
              </button>
            )}
            <Button variant="brand" onClick={onNext} className="px-4 text-sm">
              {isLast ? t('tour.done') : t('tour.next')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
