import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { attendance, classes, currentMemberId, findCoach } from '@/mocks/data'
import { useStore } from '@/state/store'
import { addDays, dayLabel, isoDay, nextDays, weekdayShort } from '@/lib/dates'
import { text } from '@/lib/format'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'

export function MemberCalendar() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const { state } = useStore()

  // Anchor "now" once per mount — reading the clock during render is non-deterministic.
  const [anchor] = useState(() => new Date())
  const today = isoDay(anchor)
  // A week back and two forward: enough to see what you did and what is coming.
  const days = useMemo(() => nextDays(21, addDays(anchor, -7)), [anchor])
  const [selected, setSelected] = useState(today)
  const stripRef = useRef<HTMLDivElement>(null)

  // The strip starts a week in the past, so today would otherwise be off-screen.
  useEffect(() => {
    stripRef.current
      ?.querySelector('[data-today]')
      ?.scrollIntoView({ inline: 'center', block: 'nearest' })
  }, [])

  const day = days.find((d) => isoDay(d) === selected) ?? anchor
  const dow = day.getDay()

  const dayClasses = classes.filter((c) => c.weekdays.includes(dow))
  const dayBookings = state.bookings.filter(
    (b) => b.memberId === currentMemberId && b.date === selected && b.status !== 'cancelled',
  )
  const trained = attendance.some((a) => a.memberId === currentMemberId && a.date === selected)
  const past = selected < today

  return (
    <Page title={t('calendar.title')}>
      {/* Week strip — scrolls horizontally, today highlighted in brand yellow */}
      <div ref={stripRef} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {days.map((d) => {
          const key = isoDay(d)
          const active = key === selected
          const wasThere = attendance.some((a) => a.memberId === currentMemberId && a.date === key)
          return (
            <button
              key={key}
              type="button"
              data-today={key === today ? '' : undefined}
              onClick={() => setSelected(key)}
              className={cn(
                'min-h-tap-lg w-14 shrink-0 rounded-xl border text-center',
                active ? 'border-ink bg-ink text-white' : 'border-line bg-surface',
              )}
            >
              <span className="block text-[11px] font-semibold opacity-70">
                {weekdayShort(d, lang)}
              </span>
              <span className="tnum block text-lg font-extrabold leading-tight">{d.getDate()}</span>
              <span
                className={cn(
                  'mx-auto block size-1.5 rounded-full',
                  wasThere ? 'bg-paid' : isoDay(d) === today ? 'bg-brand' : 'bg-transparent',
                )}
              />
            </button>
          )
        })}
      </div>

      <h2 className="text-sm font-bold">{dayLabel(day, lang)}</h2>

      {trained ? (
        <p className="bg-paid-bg text-paid flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-bold">
          <Icon name="check" size={18} />
          {t('calendar.trained')}
        </p>
      ) : null}

      {dayBookings.length > 0 ? (
        <Card>
          <CardTitle>{t('calendar.private')}</CardTitle>
          {dayBookings.map((b) => {
            const coach = findCoach(b.coachId)
            return (
              <div key={b.id} className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0">
                <span className="bg-brand text-chrome flex size-11 shrink-0 items-center justify-center rounded-xl">
                  <Icon name="dumbbell" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">
                    {b.kind === 'intro' ? t('calendar.intro') : t('calendar.private')}
                  </span>
                  <span className="text-muted block text-sm">
                    {t('calendar.with')} {coach ? text(coach.name, lang) : ''}
                  </span>
                </span>
                <span className="tnum font-bold" dir="ltr">{b.time}</span>
              </div>
            )
          })}
        </Card>
      ) : null}

      {dayClasses.length > 0 ? (
        <Card>
          <CardTitle>{t('calendar.class')}</CardTitle>
          {dayClasses.map((c) => {
            const coach = findCoach(c.coachId)
            return (
              <div key={c.id} className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0">
                <span className="bg-canvas text-ink flex size-11 shrink-0 items-center justify-center rounded-xl">
                  <Icon name="users" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{text(c.title, lang)}</span>
                  <span className="text-muted block text-sm">
                    {t('calendar.with')} {coach ? text(coach.name, lang) : ''} ·{' '}
                    {t('calendar.minutes', { count: c.durationMin })}
                  </span>
                </span>
                <span className="tnum font-bold" dir="ltr">{c.time}</span>
              </div>
            )
          })}
        </Card>
      ) : null}

      {!trained && dayBookings.length === 0 && dayClasses.length === 0 ? (
        <Empty>{t('calendar.noPlans')}</Empty>
      ) : null}

      {!past ? (
        <Link to="/member/book" className={buttonClass('brand', 'lg', true)}>
          <Icon name="dumbbell" />
          {t('calendar.book')}
        </Link>
      ) : null}
    </Page>
  )
}
