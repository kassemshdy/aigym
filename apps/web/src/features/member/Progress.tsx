import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { buttonClass } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Sparkline } from '@/components/ui/Sparkline'
import { Empty, Page } from '@/components/ui/Page'
import { currentMemberId, findMember, planForMember } from '@/mocks/data'
import type { Lang } from '@/i18n'

export function MemberProgress() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const me = findMember(currentMemberId)

  if (!me) return <Page><Empty>{t('common.none')}</Empty></Page>

  const first = me.weightTrend[0]
  const last = me.weightTrend[me.weightTrend.length - 1]
  const delta = +(last - first).toFixed(1)
  const plan = planForMember(me.id)

  return (
    <Page title={t('member.progress.title')}>
      <div className="grid grid-cols-2 gap-3">
        <Card className="p-4">
          <p className="tnum text-3xl font-extrabold">12</p>
          <p className="text-muted mt-1 text-xs font-semibold">{t('member.progress.sessions')}</p>
        </Card>
        <Card className="p-4">
          <p className="tnum text-3xl font-extrabold">4</p>
          <p className="text-muted mt-1 text-xs font-semibold">{t('member.progress.streak')}</p>
        </Card>
      </div>

      <Card className="p-4">
        <CardTitle>{t('member.progress.weight')}</CardTitle>
        <div className="flex items-end justify-between gap-4 pt-4">
          <div>
            <p className="tnum text-4xl font-extrabold">
              {last}
              <span className="text-muted text-base"> {t('common.kg')}</span>
            </p>
            <p className={`tnum text-sm font-bold ${delta <= 0 ? 'text-paid' : 'text-soon'}`} dir="ltr">
              {delta > 0 ? '+' : ''}
              {delta} {t('common.kg')}
            </p>
          </div>
          <span className="text-ink">
            <Sparkline values={me.weightTrend} width={200} height={64} />
          </span>
        </div>
      </Card>

      <Link to="/member/photos" className={buttonClass('secondary', 'lg', true)}>
        <Icon name="camera" />
        {t('photos.title')}
      </Link>

      {plan ? (
        <Card>
          <CardTitle>{t('coach.card.todayWorkout')}</CardTitle>
          {plan.exercises.map((e) => (
            <div
              key={e.id}
              className="border-line flex items-center justify-between gap-3 border-b px-4 py-3 last:border-0"
            >
              <span className="font-semibold">{e.name[lang]}</span>
              <span className="tnum text-muted text-sm" dir="ltr">
                {e.lastWeightKg ? `${e.lastWeightKg} kg` : '—'}
              </span>
            </div>
          ))}
        </Card>
      ) : null}
    </Page>
  )
}
