import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { gym } from '@/mocks/data'
import { listLapsedMembers, listMembers, listPayments, listTodaysCheckIns } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { usd } from '@/lib/format'
import { waLink } from '@/lib/whatsapp'
import type { Lang } from '@/i18n'
import { LAPSED_AFTER_DAYS } from './Lapsed'

function Tile({ n, label, tone }: { n: string; label: string; tone?: 'due' | 'soon' }) {
  return (
    <Card className="p-4">
      <p
        className={`tnum text-3xl font-extrabold ${
          tone === 'due' ? 'text-due' : tone === 'soon' ? 'text-soon' : ''
        }`}
      >
        {n}
      </p>
      <p className="text-muted mt-1 text-xs font-semibold">{label}</p>
    </Card>
  )
}

export function ManagerHome() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const members = useAsync(listMembers, [])
  const checkIns = useAsync(listTodaysCheckIns, [])
  const payments = useAsync(listPayments, [])
  const lapsed = useAsync(() => listLapsedMembers(LAPSED_AFTER_DAYS), [])

  if (members.loading || checkIns.loading || payments.loading || lapsed.loading) {
    return <Page title={t('manager.home.title')} sub={gym.name[lang]}><Empty>{t('common.loading')}</Empty></Page>
  }
  if (!members.data || !checkIns.data || !payments.data || !lapsed.data) {
    return <Page title={t('manager.home.title')} sub={gym.name[lang]}><Empty>{t('common.error')}</Empty></Page>
  }

  const owing = members.data.filter((m) => m.dues?.status === 'due')
  const ending = members.data.filter((m) => m.dues?.status === 'soon')
  const collected = payments.data.reduce((sum, p) => sum + p.amount_usd, 0)

  return (
    <Page title={t('manager.home.title')} sub={gym.name[lang]}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile n={String(checkIns.data.length)} label={t('manager.home.cameToday')} />
        <Tile n={String(owing.length)} label={t('manager.home.owes')} tone="due" />
        <Tile n={String(ending.length)} label={t('manager.home.endingSoon')} tone="soon" />
        <Tile n={usd(collected)} label={t('manager.home.collected')} />
      </div>

      <Link to="/manager/members/new" className={buttonClass('brand', 'lg', true)}>
        <Icon name="users" />
        {t('manager.home.addMember')}
      </Link>

      <Card>
        <CardTitle
          action={
            <Link to="/manager/members" className="text-muted text-sm font-semibold">
              {t('manager.home.seeAll')}
            </Link>
          }
        >
          {t('manager.home.whoOwes')}
        </CardTitle>
        <ul>
          {owing.map((m) => {
            const name = lang === 'ar' ? m.name : m.name_en
            return (
              <li key={m.id} className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0">
                <Avatar name={name} />
                <Link to={`/manager/members/${m.id}`} className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{name}</p>
                  <p className="text-due tnum text-sm font-bold">{usd(m.dues?.owed_usd ?? 0)}</p>
                </Link>
                <a
                  href={waLink(
                    m.phone,
                    t('whatsapp.dues', { name, gym: gym.name[lang], amount: m.dues?.owed_usd ?? 0 }),
                  )}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={t('manager.member.whatsapp')}
                  className="border-line text-paid flex size-12 items-center justify-center rounded-xl border"
                >
                  <Icon name="whatsapp" />
                </a>
              </li>
            )
          })}
        </ul>
      </Card>

      <Card>
        <CardTitle
          action={
            <Link to="/manager/lapsed" className="text-muted text-sm font-semibold">
              {t('manager.home.seeAll')}
            </Link>
          }
        >
          {t('lapsed.title')}
        </CardTitle>
        <ul>
          {lapsed.data.slice(0, 3).map((m) => {
            const name = lang === 'ar' ? m.name : m.name_en
            return (
              <li key={m.id}>
                <Link
                  to="/manager/lapsed"
                  className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
                >
                  <Avatar name={name} />
                  <span className="min-w-0 flex-1 truncate font-semibold">{name}</span>
                  <span className="text-soon tnum text-sm font-bold">
                    {t('lapsed.days', { count: m.days_since_visit ?? 0 })}
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
      </Card>

      <Card>
        <CardTitle>{t('manager.home.endingSoon')}</CardTitle>
        <ul>
          {ending.map((m) => {
            const name = lang === 'ar' ? m.name : m.name_en
            return (
              <li key={m.id}>
                <Link
                  to={`/manager/members/${m.id}`}
                  className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
                >
                  <Avatar name={name} />
                  <span className="min-w-0 flex-1 truncate font-semibold">{name}</span>
                  {m.dues ? <StatusBadge status={m.dues.status} /> : null}
                </Link>
              </li>
            )
          })}
        </ul>
      </Card>
    </Page>
  )
}
