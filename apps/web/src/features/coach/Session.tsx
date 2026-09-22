import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { Button, buttonClass } from '@/components/ui/Button'
import { Stepper } from '@/components/ui/Stepper'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { GenerateAiButton } from '@/features/coach/GenerateAiButton'
import { useAsync } from '@/data/useAsync'
import {
  createWorkoutSession,
  finishWorkoutSession,
  getMember,
  getTodayWorkout,
  getWorkoutSession,
  listMachines,
  listTodaysCheckIns,
  logSet,
  updateCheckInStatus,
} from '@/data/queries'
import type {
  ApiCheckIn,
  ApiMachine,
  ApiMemberDetail,
  ApiTodayExercise,
  ApiWorkoutSession,
} from '@/data/types'
import type { EffortBand } from '@/mocks/types'
import { mmss, text } from '@/lib/format'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'

const REST_SECONDS = 90

export function CoachSession() {
  const { id = '' } = useParams()
  const { t } = useTranslation()

  const { data: member, reload: reloadMember } = useAsync(() => getMember(id), [id])
  const {
    data: today,
    loading: todayLoading,
    reload: reloadToday,
  } = useAsync(() => getTodayWorkout(id), [id])
  const { data: machines } = useAsync(listMachines, [])
  const { data: checkIns } = useAsync(listTodaysCheckIns, [])
  const checkIn = checkIns?.find((c) => c.member_id === id) ?? null

  const [session, setSession] = useState<ApiWorkoutSession | null>(null)

  // A read (unlike a write) never queues — reconnecting is the only thing
  // that can resolve it, so ask again rather than leaving the coach stuck
  // on the loading screen after the network drops mid-load.
  useEffect(() => {
    function handleOnline() {
      reloadMember()
      reloadToday()
    }
    window.addEventListener('online', handleOnline)
    return () => window.removeEventListener('online', handleOnline)
  }, [reloadMember, reloadToday])

  useEffect(() => {
    if (todayLoading || !today) return
    const openSessionId = today.open_session_id
    let cancelled = false
    async function resolve() {
      const resolved = openSessionId
        ? await getWorkoutSession(openSessionId)
        : await createWorkoutSession({ member_id: id, started_at: new Date().toISOString() })
      if (!cancelled) setSession(resolved)
    }
    void resolve()
    return () => {
      cancelled = true
    }
  }, [id, today, todayLoading])

  // The Queue's waiting -> training move: fires once the coach actually
  // opens the session, not earlier — tapping into the member card alone
  // doesn't commit to starting a session.
  useEffect(() => {
    if (checkIn && checkIn.status === 'waiting') {
      void updateCheckInStatus(checkIn, 'training')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkIn?.id])

  if (!member || todayLoading || !today || !session) {
    return (
      <Page>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }
  if (today.exercises.length === 0) {
    return (
      <Page>
        <Empty>{t('coach.card.noPlan')}</Empty>
      </Page>
    )
  }

  return (
    <SessionBody
      key={session.id}
      member={member}
      exercises={today.exercises}
      initialSession={session}
      machines={machines ?? []}
      checkIn={checkIn}
    />
  )
}

function SessionBody({
  member,
  exercises,
  initialSession,
  machines,
  checkIn,
}: {
  member: ApiMemberDetail
  exercises: ApiTodayExercise[]
  initialSession: ApiWorkoutSession
  machines: ApiMachine[]
  checkIn: ApiCheckIn | null
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const [session, setSession] = useState(initialSession)
  const [idx, setIdx] = useState(0)
  const [rest, setRest] = useState(0)
  const [finished, setFinished] = useState(false)
  /** The coach can pick the station the member is actually using — there is
   * no default per exercise server-side, only what's picked this session. */
  const [machineFor, setMachineFor] = useState<Record<string, string>>({})
  const [pickingMachine, setPickingMachine] = useState(false)
  const [effort, setEffort] = useState<EffortBand | null>(null)

  const current = exercises[idx]
  const [weight, setWeight] = useState(current.last_weight_kg ?? current.target_weight_kg ?? 20)
  const [reps, setReps] = useState(10)

  /** Moving between exercises resets the weight to what this member lifted last time. */
  const goTo = (next: number) => {
    setIdx(next)
    setWeight(exercises[next].last_weight_kg ?? exercises[next].target_weight_kg ?? 20)
  }

  useEffect(() => {
    if (rest <= 0) return
    const timer = setInterval(() => setRest((r) => Math.max(0, r - 1)), 1000)
    return () => clearInterval(timer)
  }, [rest])

  const memberName = lang === 'ar' ? member.name : member.name_en
  const machine = machines.find((m) => m.id === machineFor[current.exercise_id])
  const doneForCurrent = session.sets.filter((s) => s.exercise_id === current.exercise_id)
  const totalVolume = session.sets.reduce((sum, s) => sum + s.reps * s.weight_kg, 0)

  async function logCurrentSet() {
    const newSet = await logSet(session.id, {
      exercise_id: current.exercise_id,
      set_number: doneForCurrent.length + 1,
      reps,
      weight_kg: weight,
      machine_id: machineFor[current.exercise_id] ?? null,
      at: new Date().toISOString(),
    })
    setSession((prev) => ({ ...prev, sets: [...prev.sets, newSet] }))
    setRest(REST_SECONDS)
  }

  async function chooseEffort(band: EffortBand) {
    setEffort(band)
    const updated = await finishWorkoutSession(session, {
      finished_at: session.finished_at ?? new Date().toISOString(),
      effort_band: band,
    })
    setSession(updated)
  }

  async function finish() {
    const updated = await finishWorkoutSession(session, { finished_at: new Date().toISOString() })
    setSession(updated)
    setFinished(true)
    if (checkIn) void updateCheckInStatus(checkIn, 'done')
  }

  if (finished) {
    return (
      <Page title={t('coach.session.summary')} sub={memberName}>
        <div className="grid grid-cols-2 gap-3">
          <Card className="p-4">
            <p className="tnum text-3xl font-extrabold">{session.sets.length}</p>
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
            const sets = session.sets.filter((s) => s.exercise_id === e.exercise_id)
            if (!sets.length) return null
            return (
              <div
                key={e.program_exercise_id}
                className="border-line border-b px-4 py-3 last:border-0"
              >
                <p className="font-semibold">{text(e.exercise_name, lang)}</p>
                <p className="tnum text-muted text-sm" dir="ltr">
                  {sets.map((s) => `${s.reps}×${s.weight_kg}kg`).join('  ·  ')}
                </p>
              </div>
            )
          })}
        </Card>

        <Card>
          <CardTitle>{t('coach.session.howWas')}</CardTitle>
          <div className="grid grid-cols-2 gap-2 p-4">
            {(['easy', 'good', 'hard', 'struggled'] as EffortBand[]).map((band) => (
              <button
                key={band}
                type="button"
                onClick={() => void chooseEffort(band)}
                className={cn(
                  'min-h-tap-lg rounded-xl px-3 text-base font-bold',
                  effort === band ? 'bg-ink text-white' : 'border border-line bg-surface',
                )}
              >
                {t(`coach.session.${band}`)}
              </button>
            ))}
          </div>
          {effort ? (
            <p className="text-paid flex items-center gap-2 px-4 pb-4 text-sm font-bold">
              <Icon name="check" size={18} />
              {t('coach.session.feedbackSaved')}
            </p>
          ) : null}
        </Card>

        {/* Deliberately a button the coach taps, not an automatic call on
            every finished session — that volume is a real recurring cost
            nothing in the roadmap asks for. */}
        <GenerateAiButton
          memberId={member.id}
          kind="tip"
          label={t('coach.session.getAiSuggestion')}
        />

        <Link to="/coach" className={buttonClass('brand', 'lg', true)}>
          {t('common.done')}
        </Link>
      </Page>
    )
  }

  return (
    <Page>
      <div className="flex items-center justify-between gap-3">
        <BackLink to={`/coach/member/${member.id}`} label={memberName} />
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
          <span className="tnum text-2xl font-extrabold" dir="ltr">
            {mmss(rest)}
          </span>
        </button>
      ) : null}

      <Card className="p-4">
        <h1 className="text-xl font-extrabold">{text(current.exercise_name, lang)}</h1>
        <button
          type="button"
          onClick={() => setPickingMachine(true)}
          className="border-line text-muted mt-1 inline-flex min-h-9 items-center gap-1.5 rounded-lg border px-3 text-xs font-semibold"
        >
          {t('coach.session.machine')}
          {machine ? `: ${text(machine.name, lang)}` : ''}
        </button>
        <p className="text-muted text-sm">
          <bdi className="tnum">
            {current.sets} × {text(current.reps, lang)}
          </bdi>
          {current.last_weight_kg ? (
            <>
              {' · '}
              {t('coach.session.lastTime')}{' '}
              <bdi className="tnum">
                {current.last_weight_kg} {t('common.kg')}
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

        <Button full size="lg" className="mt-5" onClick={() => void logCurrentSet()}>
          <Icon name="check" />
          {t('coach.session.set')} {doneForCurrent.length + 1}
        </Button>

        <div className="mt-4 flex flex-wrap gap-2">
          {doneForCurrent.map((s) => (
            <span
              key={s.id}
              className="bg-paid-bg text-paid tnum rounded-full px-3 py-1.5 text-sm font-bold"
              dir="ltr"
            >
              {s.reps} × {s.weight_kg}
            </span>
          ))}
          {Array.from({ length: Math.max(0, current.sets - doneForCurrent.length) }).map((_, i) => (
            <span key={i} className="border-line text-muted rounded-full border px-3 py-1.5 text-sm">
              —
            </span>
          ))}
        </div>
      </Card>

      {pickingMachine ? (
        <Card>
          <CardTitle>{t('coach.session.changeMachine')}</CardTitle>
          <div className="grid grid-cols-2 gap-2 p-4">
            {machines.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => {
                  setMachineFor((prev) => ({ ...prev, [current.exercise_id]: m.id }))
                  setPickingMachine(false)
                }}
                className={cn(
                  'min-h-tap rounded-xl px-3 text-sm font-semibold',
                  m.id === machine?.id ? 'bg-ink text-white' : 'border border-line bg-surface',
                )}
              >
                {text(m.name, lang)}
              </button>
            ))}
          </div>
        </Card>
      ) : null}

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
          <Button full size="lg" onClick={() => void finish()}>
            {t('coach.session.finish')}
          </Button>
        )}
      </div>
    </Page>
  )
}
