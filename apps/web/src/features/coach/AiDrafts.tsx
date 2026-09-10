import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { aiDrafts, findMember } from '@/mocks/data'
import type { AiDraft } from '@/mocks/types'
import type { Lang } from '@/i18n'

export function CoachAiDrafts() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const [state, setState] = useState<Record<string, AiDraft['status']>>({})

  const decide = (id: string, status: AiDraft['status']) =>
    setState((prev) => ({ ...prev, [id]: status }))

  const pending = aiDrafts.filter((d) => (state[d.id] ?? d.status) === 'pending')

  return (
    <Page
      title={t('coach.ai.title')}
      sub={t('coach.ai.pending', { count: pending.length })}
    >
      <p className="bg-soon-bg text-soon rounded-xl px-4 py-3 text-sm font-semibold">
        {t('coach.ai.notice')}
      </p>

      {aiDrafts.length === 0 ? <Empty>{t('coach.ai.empty')}</Empty> : null}

      {aiDrafts.map((d) => {
        const m = findMember(d.memberId)
        const status = state[d.id] ?? d.status
        return (
          <Card key={d.id} className="p-4">
            <div className="flex items-center gap-3">
              {m ? <Avatar name={m.name} /> : null}
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold">{m ? (lang === 'ar' ? m.name : m.nameEn) : ''}</p>
                <p className="text-muted text-xs font-semibold">{t(`aiKind.${d.kind}`)}</p>
              </div>
            </div>

            <h2 className="mt-3 text-base font-extrabold">{d.headline[lang]}</h2>
            <p className="mt-1 text-sm leading-relaxed">{d.body[lang]}</p>

            <details className="mt-3">
              <summary className="text-muted min-h-11 cursor-pointer text-sm font-semibold leading-10">
                {t('coach.ai.why')}
              </summary>
              <p className="bg-canvas text-muted mt-1 rounded-xl p-3 text-sm leading-relaxed">
                {d.reason[lang]}
              </p>
            </details>

            {status === 'pending' ? (
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Button variant="secondary" size="lg" onClick={() => decide(d.id, 'rejected')}>
                  {t('coach.ai.reject')}
                </Button>
                <Button size="lg" onClick={() => decide(d.id, 'approved')}>
                  <Icon name="check" />
                  {t('coach.ai.approve')}
                </Button>
              </div>
            ) : (
              <p
                className={`mt-4 rounded-xl px-4 py-3 text-center text-sm font-bold ${
                  status === 'approved' ? 'bg-paid-bg text-paid' : 'bg-canvas text-muted'
                }`}
              >
                {t(`coach.ai.${status}`)}
              </p>
            )}
          </Card>
        )
      })}
    </Page>
  )
}
