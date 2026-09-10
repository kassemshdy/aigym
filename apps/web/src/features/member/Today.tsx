import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { currentMemberId, findMember, gym, planForMember } from '@/mocks/data'
import { shortDate } from '@/lib/format'
import type { Lang } from '@/i18n'

export function MemberToday() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const me = findMember(currentMemberId)
  const plan = planForMember(currentMemberId)

  if (!me) return <Page><Empty>{t('common.none')}</Empty></Page>

  return (
    <Page title={t('member.today.title')} sub={plan ? plan.title[lang] : t('member.today.rest')}>
      {me.status === 'due' ? (
        <p className="bg-due-bg text-due rounded-xl px-4 py-3 text-sm font-bold">
          {t('status.due')} · {t('manager.member.ends')} {shortDate(me.endsAt, lang)}
        </p>
      ) : null}

      {!plan ? (
        <Empty>{t('member.today.rest')}</Empty>
      ) : (
        <Card>
          <CardTitle>{plan.title[lang]}</CardTitle>
          <ul>
            {plan.exercises.map((e) => (
              <li
                key={e.id}
                className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{e.name[lang]}</span>
                  <span className="text-muted block text-sm">
                    <bdi className="tnum">
                      {e.sets} × {e.reps}
                    </bdi>
                    {e.lastWeightKg ? (
                      <bdi className="tnum">
                        {' · '}
                        {e.lastWeightKg} {t('common.kg')}
                      </bdi>
                    ) : null}
                  </span>
                </span>
                {e.videoId ? (
                  <Link
                    to={`/member/videos/${e.videoId}`}
                    aria-label={t('member.today.watch')}
                    className="border-line flex size-12 items-center justify-center rounded-xl border"
                  >
                    <Icon name="play" />
                  </Link>
                ) : null}
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
