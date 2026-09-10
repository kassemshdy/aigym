import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Page } from '@/components/ui/Page'
import { checkIns, gym, memberName, members, payments } from '@/mocks/data'
import { usd } from '@/lib/format'
import { waLink } from '@/lib/whatsapp'
import type { Lang } from '@/i18n'

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

  const owing = members.filter((m) => m.status === 'due')
  const ending = members.filter((m) => m.status === 'soon')
  const collected = payments.reduce((sum, p) => sum + p.amountUsd, 0)

  return (
    <Page title={t('manager.home.title')} sub={gym.name[lang]}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile n={String(checkIns.length)} label={t('manager.home.cameToday')} />
        <Tile n={String(owing.length)} label={t('manager.home.owes')} tone="due" />
        <Tile n={String(ending.length)} label={t('manager.home.endingSoon')} tone="soon" />
        <Tile n={usd(collected)} label={t('manager.home.collected')} />
      </div>

      <Link to="/manager/members/new" className={buttonClass('primary', 'lg', true)}>
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
          {owing.map((m) => (
            <li key={m.id} className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0">
              <Avatar name={memberName(m, lang)} />
              <Link to={`/manager/members/${m.id}`} className="min-w-0 flex-1">
                <p className="truncate font-semibold">{memberName(m, lang)}</p>
                <p className="text-due tnum text-sm font-bold">{usd(m.owedUsd)}</p>
              </Link>
              <a
                href={waLink(
                  m.phone,
                  t('whatsapp.dues', {
                    name: memberName(m, lang),
                    gym: gym.name[lang],
                    amount: m.owedUsd,
                  }),
                )}
                target="_blank"
                rel="noreferrer"
                aria-label={t('manager.member.whatsapp')}
                className="border-line text-paid flex size-12 items-center justify-center rounded-xl border"
              >
                <Icon name="whatsapp" />
              </a>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardTitle>{t('manager.home.endingSoon')}</CardTitle>
        <ul>
          {ending.map((m) => (
            <li key={m.id}>
              <Link
                to={`/manager/members/${m.id}`}
                className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
              >
                <Avatar name={memberName(m, lang)} />
                <span className="min-w-0 flex-1 truncate font-semibold">
                  {memberName(m, lang)}
                </span>
                <StatusBadge status={m.status} />
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </Page>
  )
}
