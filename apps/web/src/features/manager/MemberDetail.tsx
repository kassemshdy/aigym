import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Row } from '@/components/ui/Field'
import { Sparkline } from '@/components/ui/Sparkline'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { findMember, findPlan, gym, payments } from '@/mocks/data'
import { shortDate, usd } from '@/lib/format'
import { waLink } from '@/lib/whatsapp'
import type { Lang } from '@/i18n'

export function ManagerMemberDetail() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const m = findMember(id)

  if (!m) return <Page><Empty>{t('common.none')}</Empty></Page>

  const name = lang === 'ar' ? m.name : m.nameEn
  const message =
    m.status === 'due'
      ? t('whatsapp.dues', { name, gym: gym.name[lang], amount: m.owedUsd })
      : t('whatsapp.expiring', { name, gym: gym.name[lang], date: shortDate(m.endsAt, lang) })

  return (
    <Page>
      <Link to="/manager/members" className="text-muted text-sm font-semibold">
        ← {t('common.back')}
      </Link>

      <Card className="p-4">
        <div className="flex items-center gap-3">
          <Avatar name={m.name} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-extrabold">{name}</h1>
            <p className="text-muted tnum text-sm" dir="ltr">{m.phone}</p>
          </div>
          <StatusBadge status={m.status} big />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <a href={waLink(m.phone, message)} target="_blank" rel="noreferrer" className={buttonClass('secondary', 'lg')}>
            <Icon name="whatsapp" />
            {t('manager.member.whatsapp')}
          </a>
          <button type="button" className={buttonClass('primary', 'lg')}>
            <Icon name="money" />
            {t('manager.member.recordPayment')}
          </button>
        </div>
      </Card>

      <Card>
        <Row label={t('manager.member.plan')} value={findPlan(m.planId)?.name[lang]} />
        <Row label={t('manager.member.ends')} value={shortDate(m.endsAt, lang)} />
        <Row
          label={t('manager.member.owed')}
          value={<span className={m.owedUsd ? 'text-due tnum' : 'tnum'}>{usd(m.owedUsd)}</span>}
        />
        <Row
          label={t('manager.member.lastVisit')}
          value={m.lastVisit ? shortDate(m.lastVisit, lang) : t('manager.member.never')}
        />
      </Card>

      <Card>
        <CardTitle>{t('manager.member.body')}</CardTitle>
        <Row label={t('manager.member.height')} value={`${m.heightCm} cm`} />
        <Row label={t('manager.member.weight')} value={`${m.weightKg} ${t('common.kg')}`} />
        <Row label={t('manager.member.bodyFat')} value={m.bodyFat ? `${m.bodyFat}%` : '—'} />
        <Row
          label={t('manager.member.injuries')}
          value={m.injuries.length ? m.injuries.join('، ') : t('manager.member.noInjuries')}
        />
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <span className="text-muted text-sm">{t('manager.member.weightHistory')}</span>
          <span className="text-ink"><Sparkline values={m.weightTrend} /></span>
        </div>
      </Card>

      <Card>
        <CardTitle>{t('manager.member.lifestyle')}</CardTitle>
        <Row label={t('manager.add.goal')} value={t(`goal.${m.goal}`)} />
        <Row label={t('manager.add.level')} value={t(`level.${m.level}`)} />
        <Row label={t('manager.member.daysPerWeek')} value={m.daysPerWeek} />
        <Row label={t('job.desk').split(' ')[0]} value={t(`job.${m.job}`)} />
        <Row label={t('manager.member.sleep')} value={m.sleepHours} />
      </Card>

      <Card>
        <CardTitle>{t('manager.payments.title')}</CardTitle>
        {payments.filter((p) => p.memberId === m.id).length === 0 ? (
          <p className="text-muted p-4 text-sm">{t('common.none')}</p>
        ) : (
          payments
            .filter((p) => p.memberId === m.id)
            .map((p) => (
              <Row
                key={p.id}
                label={shortDate(p.at, lang)}
                value={`${usd(p.amountUsd)} · ${t(`manager.payments.${p.method}`)}`}
              />
            ))
        )}
      </Card>
    </Page>
  )
}
