import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { currentMemberId as mockCurrentMemberId, gym } from '@/mocks/data'
import { getCurrentMemberId, getMember, getTodayWorkout } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { shortDate, text } from '@/lib/format'
import type { Lang } from '@/i18n'

export function MemberToday() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const memberId = getCurrentMemberId() ?? mockCurrentMemberId
  const member = useAsync(() => getMember(memberId), [memberId])
  const today = useAsync(() => getTodayWorkout(memberId), [memberId])

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

  const m = member.data
  const workout = today.data
  const programTitle = workout.program_title ? text(workout.program_title, lang) : null

  return (
    <Page title={t('member.today.title')} sub={programTitle ?? t('member.today.rest')}>
      {m.dues?.status === 'due' ? (
        <p className="bg-due-bg text-due rounded-xl px-4 py-3 text-sm font-bold">
          {t('status.due')} {m.ends_at ? `· ${t('manager.member.ends')} ${shortDate(m.ends_at, lang)}` : null}
        </p>
      ) : null}

      {workout.exercises.length === 0 ? (
        <Empty>{t('member.today.rest')}</Empty>
      ) : (
        <Card>
          <CardTitle>{programTitle}</CardTitle>
          <ul>
            {workout.exercises.map((e) => (
              <li
                key={e.program_exercise_id}
                className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{text(e.exercise_name, lang)}</span>
                  <span className="text-muted block text-sm">
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
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Link to="/member/videos" className={buttonClass('secondary', 'lg', true)}>
        <Icon name="play" />
        {t('member.videos.by', { coach: gym.coach[lang] })}
      </Link>
    </Page>
  )
}
