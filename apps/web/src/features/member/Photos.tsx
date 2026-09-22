import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import {
  createProgressPhoto,
  deleteProgressPhoto,
  listProgressPhotos,
  setProgressPhotoShared,
  uploadProgressPhoto,
} from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { useMediaUrl } from '@/data/useMediaUrl'
import type { ApiProgressPhoto } from '@/data/types'
import { shortDate } from '@/lib/format'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'

/**
 * Progress photos are the most sensitive data in the product. Three rules hold everywhere:
 * private by default, sharing is per-photo and explicit, and delete really deletes.
 * Nothing here is opt-out.
 */
export function MemberPhotos() {
  const { t } = useTranslation()
  const fileRef = useRef<HTMLInputElement>(null)
  const photos = useAsync(listProgressPhotos, [])
  const [uploading, setUploading] = useState(false)

  async function onPhoto(file: File) {
    setUploading(true)
    try {
      const dataUrl = await new Promise<string>((resolve) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.readAsDataURL(file)
      })
      const key = await uploadProgressPhoto(file, dataUrl)
      await createProgressPhoto(key)
      photos.reload()
    } finally {
      setUploading(false)
    }
  }

  return (
    <Page title={t('photos.title')}>
      <p className="bg-canvas text-muted flex items-start gap-2 rounded-xl px-4 py-3 text-sm font-semibold">
        <span className="mt-0.5 shrink-0">
          <Icon name="lock" size={18} />
        </span>
        {t('photos.private')}
      </p>

      <Button full size="lg" disabled={uploading} onClick={() => fileRef.current?.click()}>
        <Icon name="camera" />
        {t('photos.add')}
      </Button>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="user"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void onPhoto(file)
          e.target.value = ''
        }}
      />

      {photos.loading ? (
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      ) : photos.error || !photos.data ? (
        <Empty>{t('common.error')}</Empty>
      ) : photos.data.length === 0 ? (
        <Empty>{t('photos.empty')}</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {photos.data.map((p) => (
            <PhotoCard key={p.id} photo={p} onChanged={() => photos.reload()} />
          ))}
        </div>
      )}
    </Page>
  )
}

function PhotoCard({
  photo,
  onChanged,
}: {
  photo: ApiProgressPhoto
  onChanged: () => void
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const [confirming, setConfirming] = useState(false)
  const url = useMediaUrl(photo.photo_key, 'member')

  return (
    <Card className="overflow-hidden">
      {url ? (
        <img src={url} alt="" className="max-h-72 w-full object-cover" />
      ) : (
        <div className="bg-canvas text-muted flex aspect-square items-center justify-center">
          <Icon name="camera" size={32} />
        </div>
      )}
      <div className="space-y-3 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted text-sm">{shortDate(photo.at, lang)}</span>
          <span
            className={cn(
              'rounded-full px-2.5 py-1 text-xs font-bold',
              photo.shared_with_coach ? 'bg-soon-bg text-soon' : 'bg-canvas text-muted',
            )}
          >
            {photo.shared_with_coach ? t('photos.shared') : t('photos.private').split('—')[0].trim()}
          </span>
        </div>

        {confirming ? (
          <div className="grid grid-cols-2 gap-2">
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => {
                setConfirming(false)
                void setProgressPhotoShared(photo.id, true).then(onChanged)
              }}
            >
              {t('photos.shareWithCoach')}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="secondary"
              onClick={() => void deleteProgressPhoto(photo.id).then(onChanged)}
            >
              {t('photos.delete')}
            </Button>
            {photo.shared_with_coach ? (
              <Button
                variant="secondary"
                onClick={() => void setProgressPhotoShared(photo.id, false).then(onChanged)}
              >
                {t('photos.unshare')}
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => setConfirming(true)}>
                {t('photos.shareWithCoach')}
              </Button>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
