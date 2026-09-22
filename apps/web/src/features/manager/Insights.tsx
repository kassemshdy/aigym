import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Meter } from '@/components/ui/Meter'
import { Sparkline } from '@/components/ui/Sparkline'
import { Empty, Page } from '@/components/ui/Page'
import { getAnalyticsSummary } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { pct, usd } from '@/lib/format'
import { LAPSED_AFTER_DAYS } from './Lapsed'

/** A quarter — also the window the GTM guarantee is settled over ("the
 * first 90 days"). The endpoint takes `weeks` as a parameter, but this
 * screen deliberately offers no picker: a gym owner comparing two
 * arbitrary windows is a different product from one answering "is this
 * working". */
export const INSIGHTS_WEEKS = 12

/** One figure, its label, and what it was in the window before. The
 * comparison is the point of this screen rather than decoration — a
 * collection rate on its own says nothing about whether anything got
 * better, which is exactly the claim the guarantee makes. */
function Stat({
  value,
  label,
  note,
  tone,
}: {
  value: string
  label: string
  note?: string
  tone?: 'due'
}) {
  return (
    <Card className="p-4">
      <p className={`tnum text-3xl font-extrabold ${tone === 'due' ? 'text-due' : ''}`}>
        <bdi>{value}</bdi>
      </p>
      <p className="mt-1 text-xs font-semibold">{label}</p>
      {note ? <p className="text-muted mt-1 text-xs">{note}</p> : null}
    </Card>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-[15px] font-bold">{children}</h2>
}

export function ManagerInsights() {
  const { t } = useTranslation()
  const { data, loading, error } = useAsync(
    () => getAnalyticsSummary(INSIGHTS_WEEKS, LAPSED_AFTER_DAYS),
    [],
  )

  const title = t('insights.title')
  const sub = t('insights.sub', { weeks: INSIGHTS_WEEKS })

  if (loading) {
    return <Page title={title} sub={sub}><Empty>{t('common.loading')}</Empty></Page>
  }
  if (error || !data) {
    return <Page title={title} sub={sub}><Empty>{t('common.error')}</Empty></Page>
  }

  const now = data.collection
  const before = data.collection_previous

  // "—" rather than "0%" when nothing fell due: a window with no renewals
  // due is not a window where every renewal was missed, and the endpoint
  // is careful to send null instead of zero precisely so this screen can
  // tell them apart (app/domain/analytics.py's on_time_rate).
  const rate = now.on_time_rate === null ? '—' : pct(now.on_time_rate)

  /** The money figures need the same care as the rate: "$0 collected
   * before" is a claim about a period that collected nothing, and a period
   * with nothing due did not. `due_count` is what separates them, since a
   * window with no periods in it sums to zero either way. */
  const comparedTo = (value: string) =>
    before.due_count === 0 ? t('insights.noComparison') : t('insights.previously', { value })

  const rateBefore =
    before.on_time_rate === null
      ? t('insights.noComparison')
      : t('insights.previously', { value: pct(before.on_time_rate) })

  return (
    <Page title={title} sub={sub}>
      <Card>
        <CardTitle>{t('insights.collectionTitle')}</CardTitle>
        <div className="space-y-3 p-4">
          <p className="tnum text-5xl font-extrabold">
            <bdi>{rate}</bdi>
          </p>
          <Meter value={now.on_time_rate} label={t('insights.collectionTitle')} />
          <p className="text-muted text-sm">
            {now.due_count === 0
              ? t('insights.nothingDue')
              : t('insights.collectionNote', {
                  onTime: now.on_time_count,
                  due: now.due_count,
                })}
          </p>
          <p className="text-muted text-xs font-semibold">{rateBefore}</p>
        </div>
      </Card>

      <Card>
        <CardTitle>{t('insights.trendTitle')}</CardTitle>
        <div className="p-4">
          <span className="text-ink">
            <Sparkline
              values={data.series.map((week) => week.collected_usd)}
              width={280}
              height={64}
            />
          </span>
          <p className="text-muted mt-2 text-xs">
            {t('insights.trendNote', { weeks: data.weeks })}
          </p>
        </div>
      </Card>

      <SectionTitle>{t('insights.moneyTitle')}</SectionTitle>
      <div className="grid grid-cols-2 gap-3">
        <Stat
          value={usd(now.collected_usd)}
          label={t('insights.collected')}
          note={comparedTo(usd(before.collected_usd))}
        />
        {/* Red because this is money a member owes the gym — the meaning
            `text-due` already carries everywhere else, not a decorative
            "bad number" colour. */}
        <Stat
          value={usd(now.uncollected_usd)}
          label={t('insights.uncollected')}
          note={comparedTo(usd(before.uncollected_usd))}
          tone="due"
        />
      </div>

      <SectionTitle>{t('insights.membersTitle')}</SectionTitle>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat value={String(data.active_members)} label={t('insights.active')} />
        <Stat
          value={String(data.new_members)}
          label={t('insights.newMembers')}
          note={t('insights.previously', { value: String(data.new_members_previous) })}
        />
        <Stat
          value={String(data.lapsed_now)}
          label={t('insights.missing', { days: LAPSED_AFTER_DAYS })}
          note={t('insights.previously', { value: String(data.lapsed_at_window_start) })}
        />
      </div>

      <Link to="/manager/lapsed" className="text-muted block text-sm font-semibold">
        {t('insights.seeMissing')}
      </Link>
    </Page>
  )
}
