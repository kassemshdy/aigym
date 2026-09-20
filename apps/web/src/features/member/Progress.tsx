import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Sparkline } from '@/components/ui/Sparkline'
import { Empty, Page } from '@/components/ui/Page'
import { currentMemberId as mockCurrentMemberId } from '@/mocks/data'
import {
  getCurrentMemberId,
  getMember,
  getTodayWorkout,
  listMyAttendance,
  listWorkoutSessions,
} from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { text } from '@/lib/format'
import type { Lang } from '@/i18n'

/** Current consecutive-day streak, counting back from today. A day not
 * yet visited doesn't break yesterday's streak — the day only "counts
 * against" it once it's over. */
function computeStreak(days: string[]): number {
  const dates = new Set(days)
  const iso = (d: Date) => d.toISOString().slice(0, 10)
  const cursor = new Date()
  if (!dates.has(iso(cursor))) cursor.setDate(cursor.getDate() - 1)
  let streak = 0
  while (dates.has(iso(cursor))) {
    streak++
    cursor.setDate(cursor.getDate() - 1)
  }
  return streak
}

const thisMonthPrefix = () => new Date().toISOString().slice(0, 7)

export function MemberProgress() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const memberId = getCurrentMemberId() ?? mockCurrentMemberId
  const member = useAsync(() => getMember(memberId), [memberId])
  const today = useAsync(() => getTodayWorkout(memberId), [memberId])
  const sessions = useAsync(() => listWorkoutSessions(memberId, 100, 'member'), [memberId])
  const attendance = useAsync(listMyAttendance, [])

  if (member.loading || today.loading) {
    return (
      <Page>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }
  if (member.error || !member.data || today.error || !today.data) {
    return <Page><Empty>{t('common.none')}</Empty></Page>
  }

  const weightTrend = member.data.profile?.weight_trend ?? []
  const first = weightTrend[0]
  const last = weightTrend[weightTrend.length - 1]
  const delta = first !== undefined && last !== undefined ? +(last - first).toFixed(1) : 0
  const workout = today.data

  const sessionsThisMonth = (sessions.data ?? []).filter((s) =>
    s.started_at.startsWith(thisMonthPrefix()),
  ).length
  const streak = computeStreak((attendance.data ?? []).map((a) => a.date))

  return (
    <Page title={t('member.progress.title')}>
      <div className="grid grid-cols-2 gap-3">
        <Card className="p-4">
          <p className="tnum text-3xl font-extrabold">{sessions.loading ? '—' : sessionsThisMonth}</p>
          <p className="text-muted mt-1 text-xs font-semibold">{t('member.progress.sessions')}</p>
        </Card>
        <Card className="p-4">
          <p className="tnum text-3xl font-extrabold">{attendance.loading ? '—' : streak}</p>
          <p className="text-muted mt-1 text-xs font-semibold">{t('member.progress.streak')}</p>
        </Card>
      </div>

      {weightTrend.length > 0 && last !== undefined ? (
        <Card className="p-4">
          <CardTitle>{t('member.progress.weight')}</CardTitle>
          <div className="flex items-end justify-between gap-4 pt-4">
            <div>
              <p className="tnum text-4xl font-extrabold">
                {last}
                <span className="text-muted text-base"> {t('common.kg')}</span>
              </p>
              <p className={`tnum text-sm font-bold ${delta <= 0 ? 'text-paid' : 'text-soon'}`} dir="ltr">
                {delta > 0 ? '+' : ''}
                {delta} {t('common.kg')}
              </p>
            </div>
            <span className="text-ink">
              <Sparkline values={weightTrend} width={200} height={64} />
            </span>
          </div>
        </Card>
      ) : null}

      <Link to="/member/photos" className={buttonClass('secondary', 'lg', true)}>
        <Icon name="camera" />
        {t('photos.title')}
      </Link>

      {workout.exercises.length > 0 ? (
        <Card>
          <CardTitle>{t('coach.card.todayWorkout')}</CardTitle>
          {workout.exercises.map((e) => (
            <div
              key={e.program_exercise_id}
              className="border-line flex items-center justify-between gap-3 border-b px-4 py-3 last:border-0"
            >
              <span className="font-semibold">{text(e.exercise_name, lang)}</span>
              <span className="tnum text-muted text-sm" dir="ltr">
                {e.last_weight_kg ? `${e.last_weight_kg} kg` : '—'}
              </span>
            </div>
          ))}
        </Card>
      ) : null}
    </Page>
  )
}
