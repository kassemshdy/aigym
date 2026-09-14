import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/Card'
import { Avatar } from '@/components/ui/Avatar'
import { Empty, Page } from '@/components/ui/Page'
import { listPayments } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { shortDate, usd } from '@/lib/format'
import type { Lang } from '@/i18n'

export function ManagerPayments() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const { data, loading, error } = useAsync(listPayments, [])

  if (loading) return <Page title={t('manager.payments.title')}><Empty>{t('common.loading')}</Empty></Page>
  if (error || !data) return <Page title={t('manager.payments.title')}><Empty>{t('common.error')}</Empty></Page>

  const total = data.reduce((s, p) => s + p.amount_usd, 0)

  return (
    <Page title={t('manager.payments.title')} sub={`${t('manager.home.collected')} · ${usd(total)}`}>
      {data.length === 0 ? (
        <Empty>{t('common.none')}</Empty>
      ) : (
        <Card>
          <ul>
            {data.map((p) => {
              const name = lang === 'ar' ? p.member_name : p.member_name_en
              return (
                <li key={p.id}>
                  <Link
                    to={`/manager/members/${p.member_id}`}
                    className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
                  >
                    <Avatar name={name} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{name}</span>
                      <span className="text-muted block text-xs">
                        {shortDate(p.at, lang)} · {t(`manager.payments.${p.method}`)}
                      </span>
                    </span>
                    <span className="tnum text-paid font-bold">{usd(p.amount_usd)}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </Page>
  )
}
