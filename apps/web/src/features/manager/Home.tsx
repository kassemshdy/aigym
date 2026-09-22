import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import {
  getAnalyticsSummary,
  listLapsedMembers,
  listMembers,
  listTodaysCheckIns,
} from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { usd } from '@/lib/format'
import { waLink } from '@/lib/whatsapp'
import type { Lang } from '@/i18n'
import { useGymName } from '@/gym/GymProvider'
import { useTourAutostart } from '@/help/TourProvider'
import { INSIGHTS_WEEKS } from './Insights'
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
  const gymName = useGymName(lang)
  useTourAutostart('manager')

  const members = useAsync(listMembers, [])
  const checkIns = useAsync(listTodaysCheckIns, [])
  const lapsed = useAsync(() => listLapsedMembers(LAPSED_AFTER_DAYS), [])
  // Manager/super_admin only on the server, so a coach who taps through to
  // /manager gets a 403 from this one read. Deliberately optional rather
  // than part of the error gate below: the rest of this screen worked for
  // them before the tile existed and still should.
  const insights = useAsync(() => getAnalyticsSummary(INSIGHTS_WEEKS, LAPSED_AFTER_DAYS), [])

  if (members.loading || checkIns.loading || lapsed.loading || insights.loading) {
    return <Page title={t('manager.home.title')} sub={gymName}><Empty>{t('common.loading')}</Empty></Page>
  }
  if (!members.data || !checkIns.data || !lapsed.data) {
    return <Page title={t('manager.home.title')} sub={gymName}><Empty>{t('common.error')}</Empty></Page>
  }

  const owing = members.data.filter((m) => m.dues?.status === 'due')
  const ending = members.data.filter((m) => m.dues?.status === 'soon')

  return (
    <Page title={t('manager.home.title')} sub={gymName}>
      <div data-tour="manager-stats" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile n={String(checkIns.data.length)} label={t('manager.home.cameToday')} />
        <Tile n={String(owing.length)} label={t('manager.home.owes')} tone="due" />
        <Tile n={String(ending.length)} label={t('manager.home.endingSoon')} tone="soon" />
        {/* Was every payment ever recorded, summed, under a label that said
            "this month". Now the real windowed aggregate the dashboard is
            built on, so the two screens cannot disagree. */}
        {insights.data ? (
          <Tile
            n={usd(insights.data.collection.collected_usd)}
            label={t('manager.home.collected', { weeks: INSIGHTS_WEEKS })}
          />
        ) : null}
      </div>

      {/* Neither screen is in the tab bar — five tabs is already the most
          a 390px phone holds — and /manager/plans had no link into it at
          all before this, which made the price list unreachable in the app
          rather than merely hard to find. */}
      <div className="grid gap-3 sm:grid-cols-2">
        {insights.data ? (
          <Link to="/manager/insights">
            <Card className="flex min-h-tap items-center gap-3 p-4">
              <Icon name="chart" />
              <span className="flex-1 font-semibold">{t('insights.title')}</span>
            </Card>
          </Link>
        ) : null}
        <Link to="/manager/plans">
          <Card className="flex min-h-tap items-center gap-3 p-4">
            <Icon name="money" />
            <span className="flex-1 font-semibold">{t('manager.home.plans')}</span>
          </Card>
        </Link>
        <Link to="/manager/settings">
          <Card className="flex min-h-tap items-center gap-3 p-4">
            <Icon name="user" />
            <span className="flex-1 font-semibold">{t('manager.settings.title')}</span>
          </Card>
        </Link>
      </div>

      <Link
        to="/manager/members/new"
        data-tour="manager-add"
        className={buttonClass('brand', 'lg', true)}
      >
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
                    t('whatsapp.dues', { name, gym: gymName, amount: m.dues?.owed_usd ?? 0 }),
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
