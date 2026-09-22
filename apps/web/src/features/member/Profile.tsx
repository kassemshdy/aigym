import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Row } from '@/components/ui/Field'
import { Empty, Page } from '@/components/ui/Page'
import { currentMemberId as mockCurrentMemberId } from '@/mocks/data'
import { getCurrentMemberId, getMember, memberSignOut } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { listSep, shortDate, usd } from '@/lib/format'
import type { Lang } from '@/i18n'
import { useGymName } from '@/gym/GymProvider'

export function MemberProfile() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const gymName = useGymName(lang)
  const navigate = useNavigate()
  const memberId = getCurrentMemberId() ?? mockCurrentMemberId
  const member = useAsync(() => getMember(memberId), [memberId])

  if (member.loading) {
    return (
      <Page>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }
  if (member.error || !member.data) return <Page><Empty>{t('common.none')}</Empty></Page>

  const m = member.data
  const name = lang === 'ar' ? m.name : m.name_en
  const profile = m.profile

  return (
    <Page title={t('member.profile.title')}>
      <Card className="p-4">
        <div className="flex items-center gap-4">
          <Avatar name={name} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-extrabold">{name}</h1>
            <p className="text-muted text-sm">{gymName}</p>
          </div>
          {m.dues ? <StatusBadge status={m.dues.status} big /> : null}
        </div>
      </Card>

      <Card>
        <CardTitle>{t('member.profile.membership')}</CardTitle>
        <Row label={t('manager.member.plan')} value={m.plan_name?.[lang]} />
        <Row label={t('member.profile.endsOn')} value={m.ends_at ? shortDate(m.ends_at, lang) : '—'} />
        {m.dues && m.dues.owed_usd > 0 ? (
          <Row label={t('manager.member.owed')} value={<span className="text-due tnum">{usd(m.dues.owed_usd)}</span>} />
        ) : null}
      </Card>

      {profile ? (
        <>
          <Card>
            <CardTitle>{t('manager.member.body')}</CardTitle>
            <Row label={t('manager.member.height')} value={`${profile.height_cm} cm`} />
            <Row label={t('manager.member.weight')} value={`${profile.weight_kg} ${t('common.kg')}`} />
            <Row label={t('manager.member.bodyFat')} value={profile.body_fat ? `${profile.body_fat}%` : '—'} />
            <Row
              label={t('manager.member.injuries')}
              value={
                profile.injuries.length
                  ? profile.injuries.map((i) => i.note[lang]).join(listSep(lang))
                  : t('manager.member.noInjuries')
              }
            />
          </Card>

          <Card>
            <CardTitle>{t('manager.member.lifestyle')}</CardTitle>
            <Row label={t('manager.add.goal')} value={t(`goal.${profile.goal}`)} />
            <Row label={t('manager.add.level')} value={t(`level.${profile.level}`)} />
            <Row label={t('manager.member.daysPerWeek')} value={profile.days_per_week} />
            <Row label={t('manager.member.sleep')} value={profile.sleep_hours} />
          </Card>

          <Button
            variant="secondary"
            size="lg"
            full
            onClick={() => navigate('/member/profile/edit')}
          >
            {t('member.profile.edit')}
          </Button>
        </>
      ) : null}

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
