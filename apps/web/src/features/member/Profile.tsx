import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Row } from '@/components/ui/Field'
import { Empty, Page } from '@/components/ui/Page'
import { currentMemberId, findMember, findPlan, gym, memberName } from '@/mocks/data'
import { memberSignOut } from '@/data/queries'
import { listSep, shortDate, text, usd } from '@/lib/format'
import type { Lang } from '@/i18n'

export function MemberProfile() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const me = findMember(currentMemberId)
  const navigate = useNavigate()

  if (!me) return <Page><Empty>{t('common.none')}</Empty></Page>

  const plan = findPlan(me.planId)

  return (
    <Page title={t('member.profile.title')}>
      <Card className="p-4">
        <div className="flex items-center gap-4">
          <Avatar name={memberName(me, lang)} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-extrabold">{memberName(me, lang)}</h1>
            <p className="text-muted text-sm">{gym.name[lang]}</p>
          </div>
          <StatusBadge status={me.status} big />
        </div>
      </Card>

      <Card>
        <CardTitle>{t('member.profile.membership')}</CardTitle>
        <Row label={t('manager.member.plan')} value={plan?.name[lang]} />
        <Row label={t('member.profile.endsOn')} value={shortDate(me.endsAt, lang)} />
        {me.owedUsd > 0 ? (
          <Row label={t('manager.member.owed')} value={<span className="text-due tnum">{usd(me.owedUsd)}</span>} />
        ) : null}
      </Card>

      <Card>
        <CardTitle>{t('manager.member.body')}</CardTitle>
        <Row label={t('manager.member.height')} value={`${me.heightCm} cm`} />
        <Row label={t('manager.member.weight')} value={`${me.weightKg} ${t('common.kg')}`} />
        <Row label={t('manager.member.bodyFat')} value={me.bodyFat ? `${me.bodyFat}%` : '—'} />
        <Row
          label={t('manager.member.injuries')}
          value={me.injuries.length ? me.injuries.map((i) => text(i, lang)).join(listSep(lang)) : t('manager.member.noInjuries')}
        />
      </Card>

      <Card>
        <CardTitle>{t('manager.member.lifestyle')}</CardTitle>
        <Row label={t('manager.add.goal')} value={t(`goal.${me.goal}`)} />
        <Row label={t('manager.add.level')} value={t(`level.${me.level}`)} />
        <Row label={t('manager.member.daysPerWeek')} value={me.daysPerWeek} />
        <Row label={t('manager.member.sleep')} value={me.sleepHours} />
      </Card>

      <Button
        variant="secondary"
        size="lg"
        full
        onClick={() => {
          memberSignOut()
          navigate('/login')
        }}
      >
        {t('member.profile.signOut')}
      </Button>
    </Page>
  )
}
