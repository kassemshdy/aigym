import { useTranslation } from 'react-i18next'

/** Marks a member on this coach's own list (decision 52). Black, not a
 * status colour: green/amber/red mean payment, and yellow is identity. */
export function YoursTag() {
  const { t } = useTranslation()
  return (
    <span className="bg-ink shrink-0 rounded-full px-2.5 py-1 text-xs font-bold text-white">
      {t('coach.queue.yours')}
    </span>
  )
}
