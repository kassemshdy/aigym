import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { approveAiDraft, listAiDrafts, listMembers, rejectAiDraft } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import type { Lang } from '@/i18n'

/** The coach's AI draft inbox (decision 10) — real data since Phase 5.
 * Nothing an assistant or a coach's "generate" action proposes ever
 * reaches a member's program or calorie target until approved here. */
export function CoachAiDrafts() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const drafts = useAsync(listAiDrafts, [])
  const members = useAsync(listMembers, [])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editedBody, setEditedBody] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const memberById = new Map((members.data ?? []).map((m) => [m.id, m]))

  async function decide(id: string, action: 'approve' | 'reject', edited?: string) {
    setBusyId(id)
    try {
      if (action === 'reject') {
        await rejectAiDraft(id)
      } else if (edited !== undefined) {
        const original = drafts.data?.find((d) => d.id === id)
        const body = original ? { ...original.body, [lang]: edited } : { ar: edited, en: edited }
        await approveAiDraft(id, { body })
      } else {
        await approveAiDraft(id)
      }
      setEditingId(null)
      drafts.reload()
    } finally {
      setBusyId(null)
    }
  }

  const pending = (drafts.data ?? []).filter((d) => d.status === 'pending')

  return (
    <Page title={t('coach.ai.title')} sub={t('coach.ai.pending', { count: pending.length })}>
      <p className="bg-soon-bg text-soon rounded-xl px-4 py-3 text-sm font-semibold">
        {t('coach.ai.notice')}
      </p>

      {drafts.loading ? (
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      ) : drafts.error || !drafts.data ? (
        <Empty>{t('common.error')}</Empty>
      ) : drafts.data.length === 0 ? (
        <Empty>{t('coach.ai.empty')}</Empty>
      ) : (
        drafts.data.map((d) => {
          const m = memberById.get(d.member_id)
          const isEditing = editingId === d.id
          const busy = busyId === d.id
          return (
            <Card key={d.id} className="p-4">
              <div className="flex items-center gap-3">
                {m ? <Avatar name={lang === 'ar' ? m.name : m.name_en} /> : null}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold">{m ? (lang === 'ar' ? m.name : m.name_en) : ''}</p>
                  <p className="text-muted text-xs font-semibold">{t(`aiKind.${d.kind}`)}</p>
                </div>
              </div>

              <h2 className="mt-3 text-base font-extrabold">{d.headline[lang]}</h2>
              {isEditing ? (
                <textarea
                  value={editedBody}
                  onChange={(e) => setEditedBody(e.target.value)}
                  rows={4}
                  placeholder={t('coach.ai.editPlaceholder')}
                  className="border-line mt-1 w-full rounded-xl border p-3 text-sm leading-relaxed"
                />
              ) : (
                <p className="mt-1 text-sm leading-relaxed">{d.body[lang]}</p>
              )}
              {d.original ? (
                <p className="text-muted mt-1 text-xs">{t('coach.ai.editedNotice')}</p>
              ) : null}

              <details className="mt-3">
                <summary className="text-muted min-h-11 cursor-pointer text-sm font-semibold leading-10">
                  {t('coach.ai.why')}
                </summary>
                <p className="bg-canvas text-muted mt-1 rounded-xl p-3 text-sm leading-relaxed">
                  {d.reason[lang]}
                </p>
              </details>

              {d.status === 'pending' ? (
                <>
                  {isEditing ? (
                    <div className="mt-4 grid grid-cols-2 gap-2">
                      <Button
                        variant="secondary"
                        size="lg"
                        onClick={() => setEditingId(null)}
                        disabled={busy}
                      >
                        {t('common.cancel')}
                      </Button>
                      <Button size="lg" onClick={() => void decide(d.id, 'approve', editedBody)} disabled={busy}>
                        {t('coach.ai.approve')}
                      </Button>
                    </div>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingId(d.id)
                          setEditedBody(d.body[lang])
                        }}
                        className="text-muted mt-3 text-sm font-semibold underline"
                        disabled={busy}
                      >
                        {t('coach.ai.edit')}
                      </button>
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        <Button
                          variant="secondary"
                          size="lg"
                          onClick={() => void decide(d.id, 'reject')}
                          disabled={busy}
                        >
                          {t('coach.ai.reject')}
                        </Button>
                        <Button size="lg" onClick={() => void decide(d.id, 'approve')} disabled={busy}>
                          <Icon name="check" />
                          {t('coach.ai.approve')}
                        </Button>
                      </div>
                    </>
                  )}
                </>
              ) : (
                <p
                  className={`mt-4 rounded-xl px-4 py-3 text-center text-sm font-bold ${
                    d.status === 'approved' ? 'bg-paid-bg text-paid' : 'bg-canvas text-muted'
                  }`}
                >
                  {t(`coach.ai.${d.status}`)}
                </p>
              )}
            </Card>
          )
        })
      )}
    </Page>
  )
}
