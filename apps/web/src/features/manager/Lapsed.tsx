import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/Card'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { daysSinceVisit, gym, memberName, members } from '@/mocks/data'
import { waLink } from '@/lib/whatsapp'
import type { Lang } from '@/i18n'

/** A member who has not shown up in two weeks is the one worth a message. */
export const LAPSED_AFTER_DAYS = 14

export function lapsedMembers() {
  return members
    .map((m) => ({ member: m, days: daysSinceVisit(m.id) }))
    .filter((row) => row.days >= LAPSED_AFTER_DAYS)
    .sort((a, b) => b.days - a.days)
}

export function ManagerLapsed() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const rows = lapsedMembers()

  return (
    <Page title={t('lapsed.title')} sub={t('lapsed.sub')}>
      {rows.length === 0 ? <Empty>{t('lapsed.empty')}</Empty> : null}

      <Card>
        <ul>
          {rows.map(({ member, days }) => {
            const name = memberName(member, lang)
            return (
              <li
                key={member.id}
                className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
              >
                <Avatar name={name} />
                <Link to={`/manager/members/${member.id}`} className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{name}</span>
                  <span className="text-soon tnum block text-sm font-bold">
                    {Number.isFinite(days) ? t('lapsed.days', { count: days }) : t('lapsed.never')}
                  </span>
                </Link>
                <a
                  href={waLink(
                    member.phone,
                    t('whatsapp.missYou', { name, gym: gym.name[lang], days }),
                  )}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={t('lapsed.remind')}
                  className="border-line text-paid flex size-12 items-center justify-center rounded-xl border"
                >
                  <Icon name="whatsapp" />
                </a>
              </li>
            )
          })}
        </ul>
      </Card>
    </Page>
  )
}
