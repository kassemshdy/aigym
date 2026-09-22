import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { generateAiDraft } from '@/data/queries'
import type { AiDraftKind } from '@/data/types'
import type { Lang } from '@/i18n'

/** A coach action, not a chat message — same ai_plan_drafts mechanism
 * either way (decision 31). Always writes a new pending draft to the
 * inbox and never applies anything itself, so success just routes there
 * for the coach to review. */
export function GenerateAiButton({
  memberId,
  kind,
  label,
  variant = 'secondary',
}: {
  memberId: string
  kind: AiDraftKind
  label: string
  variant?: 'brand' | 'secondary'
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)

  async function generate() {
    setBusy(true)
    setError(false)
    try {
      await generateAiDraft(memberId, kind, lang)
      navigate('/coach/ai')
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <Button variant={variant} size="lg" full disabled={busy} onClick={() => void generate()}>
        <Icon name="spark" />
        {busy ? t('coach.ai.generating') : label}
      </Button>
      {error ? (
        <p className="bg-ink mt-2 rounded-xl px-4 py-3 text-center text-sm font-semibold text-white">
          {t('common.error')}
        </p>
      ) : null}
    </div>
  )
}
