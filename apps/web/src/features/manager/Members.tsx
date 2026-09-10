import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Chip, StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Input } from '@/components/ui/Field'
import { Empty, Page } from '@/components/ui/Page'
import { findPlan, members } from '@/mocks/data'
import type { DuesStatus } from '@/mocks/types'
import { usd } from '@/lib/format'
import type { Lang } from '@/i18n'

type Filter = 'all' | DuesStatus

export function ManagerMembers() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<Filter>('all')

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return members.filter((m) => {
      if (filter !== 'all' && m.status !== filter) return false
      if (!needle) return true
      return (
        m.name.includes(needle) ||
        m.nameEn.toLowerCase().includes(needle) ||
        m.phone.includes(needle)
      )
    })
  }, [q, filter])

  return (
    <Page title={t('manager.members.title')} sub={t('manager.members.count', { count: list.length })}>
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('common.search')} inputMode="search" />

      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {(['all', 'due', 'soon', 'paid'] as Filter[]).map((f) => (
          <Chip key={f} active={filter === f} onClick={() => setFilter(f)}>
            {f === 'all' ? t('common.all') : t(`status.${f}`)}
          </Chip>
        ))}
      </div>

      {list.length === 0 ? (
        <Empty>{t('manager.members.empty')}</Empty>
      ) : (
        <Card>
          <ul>
            {list.map((m) => (
              <li key={m.id}>
                <Link
                  to={`/manager/members/${m.id}`}
                  className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
                >
                  <Avatar name={m.name} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{lang === 'ar' ? m.name : m.nameEn}</span>
                    <span className="text-muted block text-xs">
                      {findPlan(m.planId)?.name[lang]}
                      {m.owedUsd > 0 ? <span className="text-due tnum font-bold"> · {usd(m.owedUsd)}</span> : null}
                    </span>
                  </span>
                  <StatusBadge status={m.status} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </Page>
  )
}
