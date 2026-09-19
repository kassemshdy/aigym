import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Icon } from '@/components/ui/Icon'
import { listSharedPhotos } from '@/data/queries'
import { useMediaUrl } from '@/data/useMediaUrl'
import type { ApiProgressPhoto } from '@/data/types'
import { shortDate } from '@/lib/format'
import type { Lang } from '@/i18n'

/**
 * Staff's one read of a member's progress photos (decision 11) — only
 * ever rows the member explicitly shared, enforced server-side by
 * GET /members/{id}/shared-photos, never a client-side filter. Nothing
 * loads until a manager or coach taps to reveal it: browsing a member's
 * body because the screen loaded it by default is exactly the harm
 * decision 11 exists to rule out.
 */
export function SharedPhotos({ memberId }: { memberId: string }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [photos, setPhotos] = useState<ApiProgressPhoto[] | null>(null)

  async function reveal() {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    if (photos !== null) return
    setLoading(true)
    try {
      setPhotos(await listSharedPhotos(memberId))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardTitle
        action={
          <button type="button" onClick={() => void reveal()} className="text-muted text-sm font-semibold">
            {open ? t('sharedPhotos.hide') : t('sharedPhotos.view')}
          </button>
        }
      >
        {t('sharedPhotos.title')}
      </CardTitle>

      {open ? (
        loading ? (
          <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
        ) : !photos || photos.length === 0 ? (
          <p className="text-muted p-4 text-sm">{t('sharedPhotos.empty')}</p>
        ) : (
          <ul>
            {photos.map((p) => (
              <SharedPhotoRow key={p.id} photo={p} lang={lang} />
            ))}
          </ul>
        )
      ) : null}
    </Card>
  )
}

function SharedPhotoRow({ photo, lang }: { photo: ApiProgressPhoto; lang: Lang }) {
  const url = useMediaUrl(photo.photo_key, 'staff')

  return (
    <li className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0">
      {url ? (
        <img src={url} alt="" className="size-14 shrink-0 rounded-xl object-cover" />
      ) : (
        <span className="bg-canvas text-muted flex size-14 shrink-0 items-center justify-center rounded-xl">
          <Icon name="camera" size={18} />
        </span>
      )}
      <span className="text-sm font-semibold">{shortDate(photo.at, lang)}</span>
    </li>
  )
}
