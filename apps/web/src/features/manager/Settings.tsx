import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { updateGym, uploadGymLogo } from '@/data/queries'
import { useMediaUrl } from '@/data/useMediaUrl'
import { useGym } from '@/gym/GymProvider'

/**
 * The gym's name and logo — the only two things Phase 6 made configurable.
 *
 * **The chrome is not configurable and should not become so.** Yellow on
 * black is the product's contrast guarantee (#f9e54c clears AA on black,
 * not on white), and green/amber/red are reserved for payment state. A
 * per-gym palette would break both, so branding here stops at name and
 * logo. See docs/DECISIONS.md.
 */
export function ManagerSettings() {
  const { t } = useTranslation()
  const { gym, reload } = useGym()
  const fileRef = useRef<HTMLInputElement>(null)

  const [en, setEn] = useState<string | null>(null)
  const [ar, setAr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const [saved, setSaved] = useState(false)

  const logoUrl = useMediaUrl(gym?.logo_key ?? null, 'staff')

  if (!gym) {
    return <Page title={t('manager.settings.title')}><Empty>{t('common.loading')}</Empty></Page>
  }

  // null means "not edited yet", so the fields follow the server until the
  // owner actually types something.
  const nameEn = en ?? gym.name.en
  const nameAr = ar ?? gym.name.ar
  const dirty = nameEn !== gym.name.en || nameAr !== gym.name.ar
  const complete = nameEn.trim().length > 0 && nameAr.trim().length > 0

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(false)
    setSaved(false)
    try {
      await action()
      reload()
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  function onLogo(file: File) {
    const reader = new FileReader()
    reader.onload = () => {
      void run(async () => {
        const key = await uploadGymLogo(file, String(reader.result))
        await updateGym({ logo_key: key })
      })
    }
    reader.readAsDataURL(file)
  }

  return (
    <Page title={t('manager.settings.title')} sub={t('manager.settings.sub')}>
      <Card>
        <CardTitle>{t('manager.settings.logo')}</CardTitle>
        <div className="flex items-center gap-4 p-4">
          <img
            src={logoUrl ?? '/logo.png'}
            alt=""
            width={64}
            height={64}
            className="bg-chrome size-16 shrink-0 rounded-2xl object-cover"
          />
          <div className="grid flex-1 gap-2">
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              <Icon name="camera" size={16} />
              {t('manager.settings.chooseLogo')}
            </Button>
            {gym.logo_key ? (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => void run(async () => { await updateGym({ logo_key: null }) })}
              >
                {t('manager.settings.removeLogo')}
              </Button>
            ) : null}
          </div>
        </div>
        <p className="text-muted px-4 pb-4 text-xs">{t('manager.settings.logoNote')}</p>
      </Card>

      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onLogo(file)
          e.target.value = ''
        }}
      />

      <Card className="space-y-4 p-4">
        <p className="text-muted text-sm font-semibold">{t('manager.settings.name')}</p>
        <Field label={t('manager.plans.nameEn')}>
          <Input
            value={nameEn}
            onChange={(e) => {
              // Mirrored into Arabic while the two still match, so a gym
              // that uses one name everywhere types it once. Editing the
              // Arabic field directly stops the mirroring.
              const mirror = nameAr === nameEn
              setEn(e.target.value)
              if (mirror) setAr(e.target.value)
            }}
            dir="ltr"
          />
        </Field>
        <Field label={t('manager.plans.nameAr')}>
          <Input value={nameAr} onChange={(e) => setAr(e.target.value)} dir="rtl" />
        </Field>
        {error ? (
          <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
            {t('common.error')}
          </p>
        ) : null}
        {saved ? <p className="text-muted text-sm">{t('manager.settings.saved')}</p> : null}
        <Button
          full
          size="lg"
          disabled={busy || !dirty || !complete}
          onClick={() =>
            void run(async () => {
              await updateGym({ name: { ar: nameAr.trim(), en: nameEn.trim() } })
              setEn(null)
              setAr(null)
              setSaved(true)
            })
          }
        >
          {t('common.save')}
        </Button>
      </Card>
    </Page>
  )
}
