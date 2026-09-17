import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { Field, Input } from '@/components/ui/Field'
import { Avatar } from '@/components/ui/Avatar'
import { Empty, Page } from '@/components/ui/Page'
import { useAsync } from '@/data/useAsync'
import { createCheckIn, listMembers } from '@/data/queries'
import type { Lang } from '@/i18n'

/** Manual check-in by name search. A QR-code path was tried and dropped —
 * the only decoder small enough for the iPad's browser (no native
 * BarcodeDetector on Safari) still cost ~51 KB gzipped, more than the
 * 200 KB budget could absorb alongside the rest of Phase 3 (offline
 * outbox, service worker). Revisit once a lighter decoder exists or a
 * member-facing QR display (Phase 4) makes the trade-off worth relitigating. */
export function CoachCheckIn() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const navigate = useNavigate()

  const { data: members } = useAsync(listMembers, [])
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState(false)

  async function checkIn(memberId: string) {
    setBusy(memberId)
    setError(false)
    try {
      await createCheckIn(memberId)
      navigate(`/coach/member/${memberId}`)
    } catch {
      setError(true)
      setBusy(null)
    }
  }

  const filtered =
    members?.filter((m) => {
      const q = query.trim()
      if (!q) return false
      return m.name.includes(q) || m.name_en.toLowerCase().includes(q.toLowerCase())
    }) ?? []

  return (
    <Page title={t('coach.checkIn.title')}>
      <BackLink to="/coach" />

      <Card>
        <CardTitle>{t('coach.checkIn.searchInstead')}</CardTitle>
        <div className="space-y-3 p-4">
          <Field label={t('common.search')}>
            <Input value={query} onChange={(e) => setQuery(e.target.value)} autoFocus />
          </Field>
          {query.trim() && filtered.length === 0 ? <Empty>{t('common.none')}</Empty> : null}
          {filtered.length > 0 ? (
            <ul className="border-line divide-line divide-y rounded-xl border">
              {filtered.map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    disabled={busy === m.id}
                    onClick={() => void checkIn(m.id)}
                    className="flex min-h-tap-lg w-full items-center gap-3 px-4 py-3 text-start"
                  >
                    <Avatar name={lang === 'ar' ? m.name : m.name_en} />
                    <span className="flex-1 truncate font-semibold">
                      {lang === 'ar' ? m.name : m.name_en}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {error ? (
            <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
              {t('common.error')}
            </p>
          ) : null}
        </div>
      </Card>
    </Page>
  )
}
