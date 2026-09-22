import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { BackLink } from '@/components/ui/BackLink'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { createBooking, listCoaches, listMyBookings } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { addDays, dayLabel, isoDay, nextDays, weekdayShort } from '@/lib/dates'
import { text } from '@/lib/format'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'

const SLOTS = ['17:00', '18:00', '19:00', '20:00']

export function MemberBook() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const navigate = useNavigate()
  const coaches = useAsync(listCoaches, [])
  const bookings = useAsync(listMyBookings, [])

  const [anchor] = useState(() => new Date())
  const [coachId, setCoachId] = useState<string | null>(null)
  const [date, setDate] = useState(() => isoDay(addDays(anchor, 1)))
  const [time, setTime] = useState('18:00')
  const [kind, setKind] = useState<'intro' | 'private' | null>(null)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  const days = useMemo(() => nextDays(14, anchor), [anchor])

  if (coaches.loading || bookings.loading) {
    return (
      <Page>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }
  if (coaches.error || !coaches.data || bookings.error || !bookings.data) {
    return (
      <Page>
        <Empty>{t('common.error')}</Empty>
      </Page>
    )
  }

  const pickedCoachId = coachId ?? coaches.data[0]?.id ?? null
  const coach = coaches.data.find((c) => c.id === pickedCoachId)
  // The first session with the gym is free; after that a private session is paid.
  const alreadyBooked = bookings.data.length > 0
  const pickedKind = kind ?? (alreadyBooked ? 'private' : 'intro')

  if (done) {
    return (
      <Page>
        <Card className="space-y-4 p-6 text-center">
          <span className="bg-brand text-chrome mx-auto flex size-16 items-center justify-center rounded-full">
            <Icon name="check" size={32} />
          </span>
          <h1 className="text-lg font-extrabold">{t('book.done')}</h1>
          <p className="font-semibold">
            {t('book.summary', {
              coach: coach ? text(coach.name, lang) : '',
              day: dayLabel(new Date(date), lang),
              time,
            })}
          </p>
          <Button full size="lg" onClick={() => navigate('/member/calendar')}>
            {t('common.done')}
          </Button>
        </Card>
      </Page>
    )
  }

  return (
    <Page title={t('book.title')}>
      <BackLink to="/member/calendar" />

      <Card>
        <CardTitle>{t('book.pickCoach')}</CardTitle>
        <div className="space-y-2 p-4">
          {coaches.data.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setCoachId(c.id)}
              className={cn(
                'min-h-tap-lg flex w-full items-center gap-3 rounded-xl px-4 text-start',
                pickedCoachId === c.id ? 'bg-ink text-white' : 'border border-line bg-surface',
              )}
            >
              <span className="min-w-0 flex-1">
                <span className="block font-bold">{text(c.name, lang)}</span>
                <span className={cn('block text-xs', pickedCoachId === c.id ? 'text-white/70' : 'text-muted')}>
                  {text(c.speciality, lang)}
                </span>
              </span>
              {pickedCoachId === c.id ? <Icon name="check" size={18} /> : null}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <CardTitle>{t('book.pickDay')}</CardTitle>
        <div className="-mx-0 flex gap-2 overflow-x-auto p-4">
          {days.map((d) => {
            const key = isoDay(d)
            return (
              <button
                key={key}
                type="button"
                onClick={() => setDate(key)}
                className={cn(
                  'min-h-tap-lg w-14 shrink-0 rounded-xl border text-center',
                  date === key ? 'border-ink bg-ink text-white' : 'border-line bg-surface',
                )}
              >
                <span className="block text-[11px] font-semibold opacity-70">
                  {weekdayShort(d, lang)}
                </span>
                <span className="tnum block text-lg font-extrabold leading-tight">{d.getDate()}</span>
              </button>
            )
          })}
        </div>
      </Card>

      <Card>
        <CardTitle>{t('book.pickTime')}</CardTitle>
        <div className="grid grid-cols-4 gap-2 p-4">
          {SLOTS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setTime(s)}
              className={cn(
                'tnum min-h-tap rounded-xl text-sm font-bold',
                time === s ? 'bg-ink text-white' : 'border border-line bg-surface',
              )}
              dir="ltr"
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <CardTitle>{t('book.kind')}</CardTitle>
        <div className="grid grid-cols-2 gap-2 p-4">
          {(['intro', 'private'] as const).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={cn(
                'min-h-tap-lg rounded-xl px-3 text-sm font-bold',
                pickedKind === k ? 'bg-ink text-white' : 'border border-line bg-surface',
              )}
            >
              {k === 'intro' ? t('calendar.intro') : t('calendar.private')}
            </button>
          ))}
        </div>
        {pickedKind === 'intro' ? (
          <p className="text-muted px-4 pb-4 text-xs">{t('book.introNote')}</p>
        ) : null}
      </Card>

      <Button
        variant="brand"
        full
        size="lg"
        disabled={saving || !pickedCoachId}
        onClick={() => {
          if (!pickedCoachId) return
          setSaving(true)
          void createBooking({ coach_id: pickedCoachId, date, time, kind: pickedKind })
            .then(() => setDone(true))
            .finally(() => setSaving(false))
        }}
      >
        {t('book.confirm')}
      </Button>
    </Page>
  )
}
