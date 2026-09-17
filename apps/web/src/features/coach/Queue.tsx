import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Avatar } from '@/components/ui/Avatar'
import { StatusBadge } from '@/components/ui/Badge'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { useAsync } from '@/data/useAsync'
import { getActiveProgram, listMembers, listTodaysCheckIns } from '@/data/queries'
import type { ApiCheckIn, ApiMember } from '@/data/types'
import type { Lang } from '@/i18n'
import { hhmm, text } from '@/lib/format'
import { useTourAutostart } from '@/help/TourProvider'

const GROUPS: ApiCheckIn['status'][] = ['waiting', 'training', 'done']

function memberName(m: ApiMember, lang: Lang) {
  return lang === 'ar' ? m.name : m.name_en
}

function QueueRow({ checkIn, member, lang }: { checkIn: ApiCheckIn; member: ApiMember; lang: Lang }) {
  const { t } = useTranslation()
  const { data: program } = useAsync(() => getActiveProgram(member.id), [member.id])

  return (
    <Link
      to={`/coach/member/${member.id}`}
      className="border-line flex min-h-tap-lg items-center gap-4 border-b px-4 py-3 last:border-0"
    >
      <Avatar name={memberName(member, lang)} size="lg" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-lg font-bold">{memberName(member, lang)}</span>
        <span className="text-muted block truncate text-sm">
          {program ? text(program.title, lang) : t('coach.card.noPlan')}
        </span>
      </span>
      <span className="tnum text-muted text-sm" dir="ltr">
        {hhmm(checkIn.at)}
      </span>
      {member.dues?.status === 'due' ? <StatusBadge status="due" /> : null}
      <span className="text-muted rtl:rotate-180">
        <Icon name="chevron" />
      </span>
    </Link>
  )
}

export function CoachQueue() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  useTourAutostart('coach')

  const { data: checkIns, loading: checkInsLoading } = useAsync(listTodaysCheckIns, [])
  const { data: members, loading: membersLoading } = useAsync(listMembers, [])

  if (checkInsLoading || membersLoading || !checkIns || !members) {
    return (
      <Page title={t('coach.queue.title')} sub={t('coach.queue.tap')}>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }

  const memberById = new Map(members.map((m) => [m.id, m]))

  return (
    <Page title={t('coach.queue.title')} sub={t('coach.queue.tap')}>
      <Link
        to="/coach/check-in"
        data-tour="coach-checkin"
        className="border-line text-brand flex min-h-tap items-center justify-center gap-2 rounded-xl border px-4 text-sm font-bold"
      >
        <Icon name="check" />
        {t('coach.queue.checkIn')}
      </Link>

      <div data-tour="coach-groups" className="space-y-4">
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
                    const member = memberById.get(c.member_id)
                    if (!member) return null
                    return (
                      <li key={c.id}>
                        <QueueRow checkIn={c} member={member} lang={lang} />
                      </li>
                    )
                  })}
                </ul>
              )}
            </Card>
          )
        })}
      </div>
      {checkIns.length === 0 ? <Empty>{t('common.none')}</Empty> : null}
    </Page>
  )
}
