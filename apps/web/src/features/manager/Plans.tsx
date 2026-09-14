import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Empty, Page } from '@/components/ui/Page'
import { listMembers, listPlans } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { usd } from '@/lib/format'
import type { Lang } from '@/i18n'

export function ManagerPlans() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const plans = useAsync(listPlans, [])
  const members = useAsync(listMembers, [])

  if (plans.loading || members.loading) return <Page title={t('manager.plans.title')}><Empty>{t('common.loading')}</Empty></Page>
  if (plans.error || members.error || !plans.data || !members.data) {
    return <Page title={t('manager.plans.title')}><Empty>{t('common.error')}</Empty></Page>
  }
  const memberList = members.data

  return (
    <Page title={t('manager.plans.title')}>
      <div className="grid gap-3 sm:grid-cols-2">
        {plans.data.map((p) => {
          const count = memberList.filter((m) => m.plan_id === p.id).length
          return (
            <Card key={p.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-bold">{p.name[lang]}</h2>
                  <p className="text-muted text-sm">{t('manager.plans.days', { count: p.days })}</p>
                </div>
                <p className="tnum text-2xl font-extrabold">{usd(p.price_usd)}</p>
              </div>
              <p className="text-muted mt-3 text-xs font-semibold">
                {t('manager.members.count', { count })}
              </p>
            </Card>
          )
        })}
      </div>
    </Page>
  )
}
