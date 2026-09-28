import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Chip, StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Input } from '@/components/ui/Field'
import { Empty, Page } from '@/components/ui/Page'
import { listMembers } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import type { DuesStatus, MemberStatus } from '@/data/types'
import { usd } from '@/lib/format'
import type { Lang } from '@/i18n'

/** Two axes in one row of chips, because from the desk it is one question:
 * "show me who". `all` and the three dues states are active members;
 * `left` is the only way back to someone marked as having left, since they
 * are off every other list by design (decision 43). */
type Filter = 'all' | DuesStatus | 'left'
const FILTERS: Filter[] = ['all', 'due', 'soon', 'paid', 'left']

export function ManagerMembers() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<Filter>('all')

  const lifecycle: MemberStatus = filter === 'left' ? 'left' : 'active'
  const { data, loading, error } = useAsync(() => listMembers(lifecycle), [lifecycle])

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (data ?? []).filter((m) => {
      // 'left' is answered by the fetch above, not by filtering here.
      if (filter !== 'all' && filter !== 'left' && m.dues?.status !== filter) return false
      if (!needle) return true
      return (
        m.name.includes(needle) ||
        m.name_en.toLowerCase().includes(needle) ||
        m.phone.includes(needle)
      )
    })
  }, [data, q, filter])

  return (
    <Page title={t('manager.members.title')} sub={t('manager.members.count', { count: list.length })}>
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('common.search')} inputMode="search" />

      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {FILTERS.map((f) => (
          <Chip key={f} active={filter === f} onClick={() => setFilter(f)}>
            {f === 'all'
              ? t('common.all')
              : f === 'left'
                ? t('manager.members.left')
                : t(`status.${f}`)}
          </Chip>
        ))}
      </div>

      {loading ? (
        <Empty>{t('common.loading')}</Empty>
      ) : error ? (
        <Empty>{t('common.error')}</Empty>
      ) : list.length === 0 ? (
        <Empty>{t('manager.members.empty')}</Empty>
      ) : (
        <Card>
          <ul>
            {list.map((m) => {
              const name = lang === 'ar' ? m.name : m.name_en
              return (
                <li key={m.id}>
                  <Link
                    to={`/manager/members/${m.id}`}
                    className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
                  >
                    <Avatar name={name} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{name}</span>
                      <span className="text-muted block text-xs">
                        {m.plan_name?.[lang]}
                        {m.dues && m.dues.owed_usd > 0 ? (
                          <span className="text-due tnum font-bold"> · {usd(m.dues.owed_usd)}</span>
                        ) : null}
                      </span>
                    </span>
                    {m.dues ? <StatusBadge status={m.dues.status} /> : null}
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
