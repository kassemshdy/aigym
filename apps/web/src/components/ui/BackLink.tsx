import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from './Icon'
import { cn } from '@/lib/cn'

/**
 * Back navigation, in one place.
 *
 * The arrow mirrors with the page: "back" points left in English and right in Arabic.
 * A literal "←" character does not mirror, so it pointed forward in Arabic — which is
 * why this is a component and not a string.
 *
 * It is also a real 48px tap target. The old version was bare text about 20px tall,
 * under the minimum in AGENTS.md.
 */
export function BackLink({
  to,
  label,
  className,
}: {
  to: string
  /** Defaults to "Back"; pass a name when returning somewhere specific. */
  label?: string
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <Link
      to={to}
      className={cn(
        'text-muted -ms-2 inline-flex min-h-tap items-center gap-1.5 pe-3 ps-2',
        'text-sm font-semibold',
        className,
      )}
    >
      {/* chevron points end-ward; rotate it to point back, then let RTL flip it again */}
      <span className="rotate-180 rtl:rotate-0">
        <Icon name="chevron" size={18} />
      </span>
      <span className="truncate">{label ?? t('common.back')}</span>
    </Link>
  )
}
