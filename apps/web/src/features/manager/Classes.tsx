import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button, buttonClass } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { createClass, deleteClass, listClasses, listCoaches, updateClass } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import type { ApiGymClass } from '@/data/types'
import type { Lang } from '@/i18n'
import { text } from '@/lib/format'
import { weekdayShort } from '@/lib/dates'
import { cn } from '@/lib/cn'

/** The gym's weekly class schedule. Until decision 50 the only classes were
 * the seed's placeholders, and nothing could change them. */

interface Draft {
  ar: string
  en: string
  coachId: string
  weekdays: number[]
  time: string
  minutes: string
}

const EMPTY: Draft = { ar: '', en: '', coachId: '', weekdays: [], time: '18:00', minutes: '60' }

// Monday first, the way a Lebanese gym's week is written. 0 = Sunday, as
// Date.getDay() and the server both count.
const WEEK = [1, 2, 3, 4, 5, 6, 0]

/** Any date on a known weekday, only for its localized short name. */
const dayName = (weekday: number, lang: Lang) =>
  weekdayShort(new Date(Date.UTC(2026, 0, 4 + weekday, 12)), lang)

function draftOf(c: ApiGymClass): Draft {
  return {
    ar: c.title.ar,
    en: c.title.en,
    coachId: c.coach_id,
    weekdays: c.weekdays,
    time: c.time,
    minutes: String(c.duration_min),
  }
}

function isComplete(d: Draft): boolean {
  const minutes = Number(d.minutes)
  return (
    d.ar.trim().length > 0 &&
    d.en.trim().length > 0 &&
    d.coachId !== '' &&
    d.weekdays.length > 0 &&
    /^([01]\d|2[0-3]):[0-5]\d$/.test(d.time) &&
    Number.isInteger(minutes) &&
    minutes >= 10 &&
    minutes <= 240
  )
}

export function ManagerClasses() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const classes = useAsync(listClasses, [])
  const coaches = useAsync(listCoaches, [])

  const [editingId, setEditingId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)

  function close() {
    setEditingId(null)
    setAdding(false)
    setConfirmingId(null)
    setDraft(EMPTY)
    setError(false)
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(false)
    try {
      await action()
      classes.reload()
      close()
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  if (classes.loading || coaches.loading) {
    return <Page title={t('manager.classes.title')}><Empty>{t('common.loading')}</Empty></Page>
  }
  if (classes.error || coaches.error || !classes.data || !coaches.data) {
    return <Page title={t('manager.classes.title')}><Empty>{t('common.error')}</Empty></Page>
  }
  const coachList = coaches.data
  const coachName = (id: string) => {
    const coach = coachList.find((c) => c.id === id)
    return coach ? text(coach.name, lang) : t('manager.classes.noCoach')
  }

  const form = (
    <Card className="space-y-4 p-4">
      <Field label={t('manager.classes.nameEn')}>
        <Input
          value={draft.en}
          onChange={(e) =>
            setDraft((d) => ({
              ...d,
              en: e.target.value,
              // Mirrored while the Arabic still matches, as on Plans.
              ar: d.ar === d.en ? e.target.value : d.ar,
            }))
          }
          dir="ltr"
          placeholder="Cardio & Abs"
          autoFocus
        />
      </Field>
      <Field label={t('manager.classes.nameAr')}>
        <Input
          value={draft.ar}
          onChange={(e) => setDraft((d) => ({ ...d, ar: e.target.value }))}
          dir="rtl"
          placeholder="كارديو وبطن"
        />
      </Field>

      <div>
        <span className="text-muted mb-1.5 block text-sm font-semibold">
          {t('manager.classes.coach')}
        </span>
        <div className="space-y-2">
          {coachList.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setDraft((d) => ({ ...d, coachId: c.id }))}
              className={cn(
                'min-h-tap flex w-full items-center rounded-xl px-4 text-start font-semibold',
                draft.coachId === c.id ? 'bg-ink text-white' : 'border-line bg-surface border',
              )}
            >
              {text(c.name, lang)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <span className="text-muted mb-1.5 block text-sm font-semibold">
          {t('manager.classes.days')}
        </span>
        <div className="grid grid-cols-4 gap-2">
          {WEEK.map((day) => {
            const on = draft.weekdays.includes(day)
            return (
              <button
                key={day}
                type="button"
                aria-pressed={on}
                onClick={() =>
                  setDraft((d) => ({
                    ...d,
                    weekdays: on ? d.weekdays.filter((x) => x !== day) : [...d.weekdays, day],
                  }))
                }
                className={cn(
                  'min-h-tap rounded-xl text-xs font-bold',
                  on ? 'bg-ink text-white' : 'border-line bg-surface border',
                )}
              >
                {dayName(day, lang)}
              </button>
            )
          })}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label={t('manager.classes.time')}>
          <Input
            type="time"
            value={draft.time}
            onChange={(e) => setDraft((d) => ({ ...d, time: e.target.value }))}
            dir="ltr"
            className="tnum"
          />
        </Field>
        <Field label={t('manager.classes.minutes')}>
          <Input
            value={draft.minutes}
            onChange={(e) => setDraft((d) => ({ ...d, minutes: e.target.value }))}
            inputMode="numeric"
            dir="ltr"
            className="tnum"
          />
        </Field>
      </div>

      {error ? (
        <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
          {t('common.error')}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button variant="secondary" size="lg" onClick={close}>
          {t('common.cancel')}
        </Button>
        <Button
          full
          size="lg"
          disabled={busy || !isComplete(draft)}
          onClick={() =>
            void run(async () => {
              const body = {
                title: { ar: draft.ar.trim(), en: draft.en.trim() },
                coach_id: draft.coachId,
                weekdays: draft.weekdays,
                time: draft.time,
                duration_min: Number(draft.minutes),
              }
              if (editingId) await updateClass(editingId, body)
              else await createClass(body)
            })
          }
        >
          {t('common.save')}
        </Button>
      </div>
    </Card>
  )

  return (
    <Page title={t('manager.classes.title')} sub={t('manager.classes.sub')}>
      {coachList.length === 0 ? (
        // A class needs someone to run it, and the coaches are the gym's
        // coach accounts — so the way forward is Staff, not this screen.
        <Card className="space-y-3 p-4">
          <p className="font-semibold">{t('manager.classes.needCoach')}</p>
          <Link to="/manager/staff" className={buttonClass('secondary', 'lg', true)}>
            <Icon name="user" />
            {t('manager.staff.title')}
          </Link>
        </Card>
      ) : null}

      {classes.data.length === 0 && !adding ? (
        <Empty>{t('manager.classes.empty')}</Empty>
      ) : null}

      <div className="space-y-3">
        {classes.data.map((c) => {
          if (editingId === c.id) return <div key={c.id}>{form}</div>
          const title = text(c.title, lang)
          return (
            <Card key={c.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="font-bold">{title}</h2>
                  <p className="text-muted text-sm">
                    {coachName(c.coach_id)} ·{' '}
                    {WEEK.filter((d) => c.weekdays.includes(d))
                      .map((d) => dayName(d, lang))
                      .join(' ')}
                  </p>
                </div>
                <p className="tnum shrink-0 text-end font-extrabold">
                  <bdi dir="ltr">{c.time}</bdi>
                  <span className="text-muted block text-xs font-semibold">
                    {t('calendar.minutes', { count: c.duration_min })}
                  </span>
                </p>
              </div>

              {confirmingId === c.id ? (
                <div className="mt-3 space-y-2">
                  <p className="text-sm font-semibold">
                    {t('manager.classes.confirmDelete', { name: title })}
                  </p>
                  <div className="flex gap-2">
                    <Button variant="secondary" onClick={close}>
                      {t('common.cancel')}
                    </Button>
                    {/* Black, not red: red is payment state only. */}
                    <Button full disabled={busy} onClick={() => void run(() => deleteClass(c.id))}>
                      {t('common.remove')}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      close()
                      setDraft(draftOf(c))
                      setEditingId(c.id)
                    }}
                  >
                    {t('manager.plans.edit')}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      close()
                      setConfirmingId(c.id)
                    }}
                  >
                    {t('common.remove')}
                  </Button>
                </div>
              )}
            </Card>
          )
        })}
      </div>

      {coachList.length > 0 ? (
        adding ? (
          form
        ) : (
          <Button
            variant="brand"
            full
            size="lg"
            onClick={() => {
              close()
              setDraft({ ...EMPTY, coachId: coachList[0].id })
              setAdding(true)
            }}
          >
            <Icon name="add" size={18} />
            {t('manager.classes.add')}
          </Button>
        )
      ) : null}
    </Page>
  )
}
