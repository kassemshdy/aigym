import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Avatar } from '@/components/ui/Avatar'
import { StatusBadge } from '@/components/ui/Badge'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { checkIns, findMember, memberName, planForMember } from '@/mocks/data'
import type { CheckIn } from '@/mocks/types'
import type { Lang } from '@/i18n'

const GROUPS: CheckIn['status'][] = ['waiting', 'training', 'done']

export function CoachQueue() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  return (
    <Page title={t('coach.queue.title')} sub={t('coach.queue.tap')}>
      {GROUPS.map((group) => {
        const rows = checkIns.filter((c) => c.status === group)
        return (
          <Card key={group}>
            <CardTitle>
              {t(`coach.queue.${group}`)}
              <span className="text-muted tnum ms-2 text-sm">{rows.length}</span>
            </CardTitle>
            {rows.length === 0 ? (
              <p className="text-muted p-4 text-sm">{t('common.none')}</p>
            ) : (
              <ul>
                {rows.map((c) => {
                  const m = findMember(c.memberId)
                  if (!m) return null
                  const plan = planForMember(m.id)
                  return (
                    <li key={c.id}>
                      <Link
                        to={`/coach/member/${m.id}`}
                        className="border-line flex min-h-tap-lg items-center gap-4 border-b px-4 py-3 last:border-0"
                      >
                        <Avatar name={memberName(m, lang)} size="lg" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-lg font-bold">
                            {memberName(m, lang)}
                          </span>
                          <span className="text-muted block truncate text-sm">
                            {plan ? plan.title[lang] : t('coach.card.noPlan')}
                          </span>
                        </span>
                        <span className="tnum text-muted text-sm" dir="ltr">{c.at}</span>
                        {m.status === 'due' ? <StatusBadge status="due" /> : null}
                        <span className="text-muted rtl:rotate-180">
                          <Icon name="chevron" />
                        </span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>
        )
      })}
      {checkIns.length === 0 ? <Empty>{t('common.none')}</Empty> : null}
    </Page>
  )
}
