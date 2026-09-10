import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { useStore } from '@/state/store'
import { shortDate } from '@/lib/format'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'

/**
 * Progress photos are the most sensitive data in the product. Three rules hold everywhere:
 * private by default, sharing is per-photo and explicit, and delete really deletes.
 * Nothing here is opt-out.
 */
export function MemberPhotos() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const { state, actions } = useStore()
  const fileRef = useRef<HTMLInputElement>(null)
  const [confirming, setConfirming] = useState<string | null>(null)

  return (
    <Page title={t('photos.title')}>
      <p className="bg-canvas text-muted flex items-start gap-2 rounded-xl px-4 py-3 text-sm font-semibold">
        <span className="mt-0.5 shrink-0">
          <Icon name="lock" size={18} />
        </span>
        {t('photos.private')}
      </p>

      <Button full size="lg" onClick={() => fileRef.current?.click()}>
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
          if (file) {
            const reader = new FileReader()
            reader.onload = () => actions.addPhoto(String(reader.result))
            reader.readAsDataURL(file)
          }
          e.target.value = ''
        }}
      />

      {state.photos.length === 0 ? <Empty>{t('photos.empty')}</Empty> : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {state.photos.map((p) => (
          <Card key={p.id} className="overflow-hidden">
            <img src={p.url} alt="" className="max-h-72 w-full object-cover" />
            <div className="space-y-3 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted text-sm">{shortDate(p.at, lang)}</span>
                <span
                  className={cn(
                    'rounded-full px-2.5 py-1 text-xs font-bold',
                    p.sharedWithCoach ? 'bg-soon-bg text-soon' : 'bg-canvas text-muted',
                  )}
                >
                  {p.sharedWithCoach ? t('photos.shared') : t('photos.private').split('—')[0].trim()}
                </span>
              </div>

              {confirming === p.id ? (
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => setConfirming(null)}>
                    {t('common.cancel')}
                  </Button>
                  <Button
                    onClick={() => {
                      actions.setPhotoShared(p.id, true)
                      setConfirming(null)
                    }}
                  >
                    {t('photos.shareWithCoach')}
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => actions.removePhoto(p.id)}>
                    {t('photos.delete')}
                  </Button>
                  {p.sharedWithCoach ? (
                    <Button variant="secondary" onClick={() => actions.setPhotoShared(p.id, false)}>
                      {t('photos.unshare')}
                    </Button>
                  ) : (
                    <Button variant="secondary" onClick={() => setConfirming(p.id)}>
                      {t('photos.shareWithCoach')}
                    </Button>
                  )}
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </Page>
  )
}
