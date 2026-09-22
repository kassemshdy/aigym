import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/Card'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { listLapsedMembers } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { waLink } from '@/lib/whatsapp'
import type { Lang } from '@/i18n'
import { useGymName } from '@/gym/GymProvider'

/** A member who has not shown up in two weeks is the one worth a message —
 * the GTM number this phase exists to make measurable against a live gym,
 * not mock data. */
export const LAPSED_AFTER_DAYS = 14

export function ManagerLapsed() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const gymName = useGymName(lang)
  const { data, loading, error } = useAsync(() => listLapsedMembers(LAPSED_AFTER_DAYS), [])

  if (loading) return <Page title={t('lapsed.title')} sub={t('lapsed.sub')}><Empty>{t('common.loading')}</Empty></Page>
  if (error || !data) return <Page title={t('lapsed.title')} sub={t('lapsed.sub')}><Empty>{t('common.error')}</Empty></Page>

  return (
    <Page title={t('lapsed.title')} sub={t('lapsed.sub')}>
      {data.length === 0 ? <Empty>{t('lapsed.empty')}</Empty> : null}

      <Card>
        <ul>
          {data.map((m) => {
            const name = lang === 'ar' ? m.name : m.name_en
            const days = m.days_since_visit
            return (
              <li
                key={m.id}
                className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
              >
                <Avatar name={name} />
                <Link to={`/manager/members/${m.id}`} className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{name}</span>
                  <span className="text-soon tnum block text-sm font-bold">
                    {days !== null ? t('lapsed.days', { count: days }) : t('lapsed.never')}
                  </span>
                </Link>
                <a
                  href={waLink(
                    m.phone,
                    t('whatsapp.missYou', { name, gym: gymName, days: days ?? 0 }),
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
