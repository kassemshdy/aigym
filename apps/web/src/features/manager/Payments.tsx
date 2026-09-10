import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/Card'
import { Avatar } from '@/components/ui/Avatar'
import { Page } from '@/components/ui/Page'
import { findMember, payments } from '@/mocks/data'
import { shortDate, usd } from '@/lib/format'
import type { Lang } from '@/i18n'

export function ManagerPayments() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const total = payments.reduce((s, p) => s + p.amountUsd, 0)

  return (
    <Page title={t('manager.payments.title')} sub={`${t('manager.home.collected')} · ${usd(total)}`}>
      <Card>
        <ul>
          {payments.map((p) => {
            const m = findMember(p.memberId)
            if (!m) return null
            return (
              <li key={p.id}>
                <Link
                  to={`/manager/members/${m.id}`}
                  className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
                >
                  <Avatar name={m.name} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{lang === 'ar' ? m.name : m.nameEn}</span>
                    <span className="text-muted block text-xs">
                      {shortDate(p.at, lang)} · {t(`manager.payments.${p.method}`)}
                    </span>
                  </span>
                  <span className="tnum text-paid font-bold">{usd(p.amountUsd)}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      </Card>
    </Page>
  )
}
