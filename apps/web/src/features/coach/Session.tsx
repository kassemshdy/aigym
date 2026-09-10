import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { Button, buttonClass } from '@/components/ui/Button'
import { Stepper } from '@/components/ui/Stepper'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { findMember, memberName, planForMember } from '@/mocks/data'
import type { LoggedSet } from '@/mocks/types'
import { mmss, text } from '@/lib/format'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'

const REST_SECONDS = 90

export function CoachSession() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const member = findMember(id)
  const plan = planForMember(id)
  const exercises = useMemo(() => plan?.exercises ?? [], [plan])

  const [idx, setIdx] = useState(0)
  const [logged, setLogged] = useState<LoggedSet[]>([])
  const [rest, setRest] = useState(0)
  const [finished, setFinished] = useState(false)

  const current = exercises[idx]
  const [weight, setWeight] = useState(current?.lastWeightKg ?? 20)
  const [reps, setReps] = useState(10)

  /** Moving between exercises resets the weight to what this member lifted last time. */
  const goTo = (next: number) => {
    setIdx(next)
    setWeight(exercises[next]?.lastWeightKg ?? 20)
  }

  useEffect(() => {
    if (rest <= 0) return
    const id = setInterval(() => setRest((r) => Math.max(0, r - 1)), 1000)
    return () => clearInterval(id)
  }, [rest])

  if (!member || !plan || !current) {
    return <Page><Empty>{t('coach.card.noPlan')}</Empty></Page>
  }

  const doneForCurrent = logged.filter((s) => s.exerciseId === current.id)
  const totalVolume = logged.reduce((sum, s) => sum + s.reps * s.weightKg, 0)

  if (finished) {
    return (
      <Page title={t('coach.session.summary')} sub={memberName(member, lang)}>
        <div className="grid grid-cols-2 gap-3">
          <Card className="p-4">
            <p className="tnum text-3xl font-extrabold">{logged.length}</p>
            <p className="text-muted mt-1 text-xs font-semibold">{t('coach.session.totalSets')}</p>
          </Card>
          <Card className="p-4">
            <p className="tnum text-3xl font-extrabold">
              {totalVolume.toLocaleString('en-US')}
              <span className="text-muted text-base"> {t('common.kg')}</span>
            </p>
            <p className="text-muted mt-1 text-xs font-semibold">{t('coach.session.totalVolume')}</p>
          </Card>
        </div>

        <Card>
          <CardTitle>{t('coach.session.title')}</CardTitle>
          {exercises.map((e) => {
            const sets = logged.filter((s) => s.exerciseId === e.id)
            if (!sets.length) return null
            return (
              <div key={e.id} className="border-line border-b px-4 py-3 last:border-0">
                <p className="font-semibold">{e.name[lang]}</p>
                <p className="tnum text-muted text-sm" dir="ltr">
                  {sets.map((s) => `${s.reps}×${s.weightKg}kg`).join('  ·  ')}
                </p>
              </div>
            )
          })}
        </Card>

        <Link to="/coach" className={buttonClass('primary', 'lg', true)}>
          {t('common.done')}
        </Link>
      </Page>
    )
  }

  return (
    <Page>
      <div className="flex items-center justify-between gap-3">
        <BackLink to={`/coach/member/${member.id}`} label={memberName(member, lang)} />
        <span className="tnum text-muted text-sm" dir="ltr">
          {idx + 1} / {exercises.length}
        </span>
      </div>

      {rest > 0 ? (
        <button
          type="button"
          onClick={() => setRest(0)}
          className="bg-ink flex min-h-tap w-full items-center justify-between rounded-xl px-4 text-white"
        >
          <span className="text-sm font-semibold">{t('coach.session.rest')}</span>
          <span className="tnum text-2xl font-extrabold" dir="ltr">{mmss(rest)}</span>
        </button>
      ) : null}

      <Card className="p-4">
        <h1 className="text-xl font-extrabold">{current.name[lang]}</h1>
        <p className="text-muted text-sm">
          <bdi className="tnum">
            {current.sets} × {text(current.reps, lang)}
          </bdi>
          {current.lastWeightKg ? (
            <>
              {' · '}
              {t('coach.session.lastTime')}{' '}
              <bdi className="tnum">
                {current.lastWeightKg} {t('common.kg')}
              </bdi>
            </>
          ) : null}
        </p>

        <div className="mt-5 max-w-md space-y-4">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-bold">{t('coach.session.weight')}</span>
            <Stepper value={weight} step={2.5} suffix={t('common.kg')} onChange={setWeight} size="lg" />
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-bold">{t('coach.session.reps')}</span>
            <Stepper value={reps} step={1} min={1} onChange={setReps} size="lg" />
          </div>
        </div>

        <Button
          full
          size="lg"
          className="mt-5"
          onClick={() => {
            setLogged((prev) => [
              ...prev,
              { exerciseId: current.id, set: doneForCurrent.length + 1, reps, weightKg: weight },
            ])
            setRest(REST_SECONDS)
          }}
        >
          <Icon name="check" />
          {t('coach.session.set')} {doneForCurrent.length + 1}
        </Button>

        <div className="mt-4 flex flex-wrap gap-2">
          {doneForCurrent.map((s) => (
            <span
              key={s.set}
              className="bg-paid-bg text-paid tnum rounded-full px-3 py-1.5 text-sm font-bold"
              dir="ltr"
            >
              {s.reps} × {s.weightKg}
            </span>
          ))}
          {Array.from({ length: Math.max(0, current.sets - doneForCurrent.length) }).map((_, i) => (
            <span key={i} className="border-line text-muted rounded-full border px-3 py-1.5 text-sm">
              —
            </span>
          ))}
        </div>
      </Card>

      <div className="flex gap-2">
        <Button
          variant="secondary"
          size="lg"
          disabled={idx === 0}
          onClick={() => goTo(idx - 1)}
          className={cn(idx === 0 && 'opacity-40')}
        >
          {t('common.back')}
        </Button>
        {idx < exercises.length - 1 ? (
          <Button full size="lg" variant="secondary" onClick={() => goTo(idx + 1)}>
            {t('common.next')}
          </Button>
        ) : (
          <Button full size="lg" onClick={() => setFinished(true)}>
            {t('coach.session.finish')}
          </Button>
        )}
      </div>
    </Page>
  )
}
