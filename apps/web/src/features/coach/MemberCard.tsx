import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { buttonClass } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Sparkline } from '@/components/ui/Sparkline'
import { Empty, Page } from '@/components/ui/Page'
import { useAsync } from '@/data/useAsync'
import {
  createNutritionLog,
  getMember,
  getTodayWorkout,
  listNutritionLogs,
  listWorkoutSessions,
} from '@/data/queries'
import type {
  ApiMemberDetail,
  ApiNutritionLog,
  ApiTodayWorkout,
  ApiWorkoutSession,
} from '@/data/types'
import type { Lang } from '@/i18n'
import { listSep, shortDate, text } from '@/lib/format'
import { cn } from '@/lib/cn'

const BANDS = ['low', 'ok', 'high', 'unknown'] as const

/** Tapped, not typed. Exact calories are optional and almost never entered on the floor. */
const QUICK_MEALS = [
  { ar: 'بيض', en: 'Eggs' },
  { ar: 'خبز', en: 'Bread' },
  { ar: 'دجاج', en: 'Chicken' },
  { ar: 'رز', en: 'Rice' },
  { ar: 'لبنة', en: 'Labneh' },
  { ar: 'سلطة', en: 'Salad' },
  { ar: 'قهوة', en: 'Coffee' },
  { ar: 'موز', en: 'Banana' },
]

function isToday(iso: string) {
  return iso.slice(0, 10) === new Date().toISOString().slice(0, 10)
}

export function CoachMemberCard() {
  const { id = '' } = useParams()
  const { t } = useTranslation()

  const { data: member, loading: memberLoading } = useAsync(() => getMember(id), [id])
  const { data: today, loading: todayLoading } = useAsync(() => getTodayWorkout(id), [id])
  const { data: logs, loading: logsLoading } = useAsync(() => listNutritionLogs(id), [id])
  const { data: recentSessions, loading: sessionsLoading } = useAsync(
    () => listWorkoutSessions(id, 5),
    [id],
  )

  if (memberLoading || todayLoading || logsLoading || sessionsLoading) {
    return (
      <Page>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }
  if (!member || !today) return <Page><Empty>{t('common.none')}</Empty></Page>

  return (
    <MemberCardBody
      key={id}
      memberId={id}
      member={member}
      today={today}
      logs={logs ?? []}
      recentSessions={recentSessions ?? []}
    />
  )
}

function MemberCardBody({
  memberId,
  member,
  today,
  logs,
  recentSessions,
}: {
  memberId: string
  member: ApiMemberDetail
  today: ApiTodayWorkout
  logs: ApiNutritionLog[]
  recentSessions: ApiWorkoutSession[]
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const todaysLog = logs.find((n) => isToday(n.at))
  const [band, setBand] = useState<(typeof BANDS)[number] | null>(
    (todaysLog?.band as (typeof BANDS)[number] | undefined) ?? null,
  )
  const [meals, setMeals] = useState<string[]>((todaysLog?.meals as string[] | undefined) ?? [])
  const [saved, setSaved] = useState(false)

  const name = lang === 'ar' ? member.name : member.name_en
  const due = member.dues?.status === 'due'
  const injuries = member.profile?.injuries ?? []
  const weightTrend = member.profile?.weight_trend ?? []
  const lastSession = recentSessions[0] ?? null
  const lastSessionVolume = lastSession
    ? lastSession.sets.reduce((sum, s) => sum + s.reps * s.weight_kg, 0)
    : 0

  async function save(nextBand: (typeof BANDS)[number], nextMeals: string[]) {
    setBand(nextBand)
    setSaved(false)
    await createNutritionLog(memberId, {
      at: new Date().toISOString(),
      band: nextBand,
      meals: nextMeals,
      source: 'coach',
    })
    setSaved(true)
  }

  return (
    <Page>
      <BackLink to="/coach" />

      <Card className="p-4">
        <div className="flex items-center gap-4">
          <Avatar name={name} size="lg" />
          <div className="min-w-0">
            <h1 className="truncate text-xl font-extrabold">{name}</h1>
            {member.profile ? (
              <p className="text-muted truncate text-sm">
                {t(`goal.${member.profile.goal}`)} · {t(`level.${member.profile.level}`)}
              </p>
            ) : null}
          </div>
        </div>

        {/* The coach must see payment state before the session, not after. */}
        <p
          className={cn(
            'mt-4 rounded-xl px-4 py-3 text-center text-base font-bold',
            due ? 'bg-due-bg text-due' : 'bg-paid-bg text-paid',
          )}
        >
          {due
            ? t('coach.card.paidDue', { amount: member.dues?.owed_usd ?? 0 })
            : t('coach.card.paidOk')}
        </p>

        {injuries.length > 0 ? (
          <p className="bg-soon-bg text-soon mt-2 rounded-xl px-4 py-3 text-center text-sm font-bold">
            {t('manager.member.injuries')}:{' '}
            {injuries
              .map((i) => text(i as Parameters<typeof text>[0], lang))
              .join(listSep(lang))}
          </p>
        ) : null}
      </Card>

      <Card>
        <CardTitle>{t('coach.card.askFood')}</CardTitle>
        <div className="space-y-3 p-4">
          <p className="text-lg font-bold">{t('coach.card.foodQuestion')}</p>
          <div className="grid grid-cols-2 gap-2">
            {BANDS.map((b) => (
              <button
                key={b}
                type="button"
                onClick={() => void save(b, meals)}
                className={cn(
                  'min-h-tap-lg rounded-xl px-3 text-base font-bold',
                  band === b ? 'bg-ink text-white' : 'border border-line bg-surface active:bg-canvas',
                )}
              >
                {t(`coach.food.${b}`)}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            {QUICK_MEALS.map((meal) => (
              <button
                key={meal.en}
                type="button"
                onClick={() => {
                  const next = meals.includes(meal.en)
                    ? meals.filter((x) => x !== meal.en)
                    : [...meals, meal.en]
                  setMeals(next)
                  if (band) void save(band, next)
                }}
                className={cn(
                  'min-h-11 rounded-full px-4 text-sm font-semibold',
                  meals.includes(meal.en) ? 'bg-ink text-white' : 'border border-line bg-surface',
                )}
              >
                {meal[lang]}
              </button>
            ))}
          </div>

          {saved ? (
            <p className="text-paid flex items-center gap-2 text-sm font-bold">
              <Icon name="check" size={18} />
              {t('coach.food.saved')}
            </p>
          ) : null}
        </div>
      </Card>

      {member.profile ? (
        <Card>
          <CardTitle>{t('coach.card.progress')}</CardTitle>
          <div className="space-y-3 p-4">
            {weightTrend.length >= 2 ? (
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted text-sm">{t('manager.member.weightHistory')}</span>
                <span className="text-ink">
                  <Sparkline values={weightTrend} />
                </span>
              </div>
            ) : null}

            {lastSession ? (
              <div>
                <p className="text-muted text-sm">
                  {t('coach.card.lastWorkout')} ·{' '}
                  <bdi className="tnum">{shortDate(lastSession.started_at, lang)}</bdi>
                </p>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <div className="bg-canvas rounded-xl p-3">
                    <p className="tnum text-2xl font-extrabold">{lastSession.sets.length}</p>
                    <p className="text-muted text-xs font-semibold">
                      {t('coach.session.totalSets')}
                    </p>
                  </div>
                  <div className="bg-canvas rounded-xl p-3">
                    <p className="tnum text-2xl font-extrabold">
                      {lastSessionVolume.toLocaleString('en-US')}
                      <span className="text-muted text-sm"> {t('common.kg')}</span>
                    </p>
                    <p className="text-muted text-xs font-semibold">
                      {t('coach.session.totalVolume')}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-muted text-sm">{t('coach.card.noWorkoutsYet')}</p>
            )}
          </div>
        </Card>
      ) : null}

      <Card>
        <CardTitle>{t('coach.card.todayWorkout')}</CardTitle>
        {today.exercises.length === 0 ? (
          <p className="text-muted p-4 text-sm">{t('coach.card.noPlan')}</p>
        ) : (
          <>
            {today.program_title ? (
              <p className="border-line border-b px-4 py-3 font-bold">
                {text(today.program_title, lang)}
              </p>
            ) : null}
            <ul>
              {today.exercises.map((e) => (
                <li
                  key={e.program_exercise_id}
                  className="border-line flex items-center justify-between gap-3 border-b px-4 py-3 last:border-0"
                >
                  <span className="font-semibold">{text(e.exercise_name, lang)}</span>
                  <span className="text-muted text-sm">
                    <bdi className="tnum">
                      {e.sets} × {text(e.reps, lang)}
                    </bdi>
                    {e.last_weight_kg ? (
                      <bdi className="tnum">
                        {' · '}
                        {e.last_weight_kg} {t('common.kg')}
                      </bdi>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>

      {today.exercises.length > 0 ? (
        <Link to={`/coach/session/${memberId}`} className={buttonClass('brand', 'lg', true)}>
          <Icon name="dumbbell" />
          {t('coach.card.start')}
        </Link>
      ) : null}

      <Link to={`/coach/programs/${memberId}`} className={buttonClass('secondary', 'lg', true)}>
        <Icon name="list" />
        {t('coach.card.editPlan')}
      </Link>
    </Page>
  )
}
