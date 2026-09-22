import { useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { Stepper } from '@/components/ui/Stepper'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { useStore } from '@/state/store'
import {
  createFoodEntry,
  deleteFoodEntry,
  estimateFoodEntry,
  getCurrentMemberId,
  getMember,
  listFoodEntries,
  uploadFoodPhoto,
} from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { useMediaUrl } from '@/data/useMediaUrl'
import type { ApiFoodEntry } from '@/data/types'
import { hhmm } from '@/lib/format'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'
import { currentMemberId as mockCurrentMemberId } from '@/mocks/data'

const DEFAULT_DAILY_KCAL = 2100
const DAILY_PROTEIN = 145

/** Once the member edits the name it is a plain string in their own words.
 * `photo` is the FileReader data-URL preview, shown in the confirm card.
 * `photoKey` is set once the photo has been uploaded (see onPhoto) — the
 * same key the vision estimate already used, reused as-is by confirm()
 * instead of uploading a second time. */
type Draft = {
  label: string
  kcal: number
  protein: number
  carbs: number
  fat: number
  photo?: string
  photoKey?: string
}

export function MemberFood() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const { state, actions } = useStore()
  const fileRef = useRef<HTMLInputElement>(null)
  const entries = useAsync(listFoodEntries, [])
  const memberId = getCurrentMemberId() ?? mockCurrentMemberId
  const member = useAsync(() => getMember(memberId), [memberId])
  const dailyKcal = member.data?.profile?.daily_kcal_target ?? DEFAULT_DAILY_KCAL

  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState(false)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [portion, setPortion] = useState(1)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)

  const totals = useMemo(
    () =>
      (entries.data ?? []).reduce(
        (acc, f) => ({
          kcal: acc.kcal + f.kcal,
          protein: acc.protein + f.protein,
          carbs: acc.carbs + f.carbs,
          fat: acc.fat + f.fat,
        }),
        { kcal: 0, protein: 0, carbs: 0, fat: 0 },
      ),
    [entries.data],
  )

  const onPhoto = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => void analyze(file, String(reader.result))
    reader.readAsDataURL(file)
  }

  async function analyze(file: File, photo: string) {
    setAnalyzing(true)
    setAnalyzeError(false)
    try {
      const photoKey = await uploadFoodPhoto(file, photo)
      const guess = await estimateFoodEntry(photoKey, lang)
      setDraft({ ...guess, photo, photoKey })
      setPortion(1)
    } catch {
      setAnalyzeError(true)
    } finally {
      setAnalyzing(false)
    }
  }

  const scaled = draft && {
    kcal: Math.round(draft.kcal * portion),
    protein: Math.round(draft.protein * portion),
    carbs: Math.round(draft.carbs * portion),
    fat: Math.round(draft.fat * portion),
  }

  async function confirm() {
    if (!draft || !scaled) return
    setSaving(true)
    setError(false)
    try {
      await createFoodEntry({
        label: draft.label,
        ...scaled,
        source: draft.photoKey ? 'photo' : 'manual',
        photo_key: draft.photoKey ?? null,
        estimate: draft.photoKey
          ? { kcal: draft.kcal, protein: draft.protein, carbs: draft.carbs, fat: draft.fat }
          : null,
      })
      setDraft(null)
      entries.reload()
    } catch {
      setError(true)
    } finally {
      setSaving(false)
    }
  }

  async function remove(entryId: string) {
    await deleteFoodEntry(entryId)
    entries.reload()
  }

  return (
    <Page title={t('food.title')}>
      <Card className="p-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="tnum text-4xl font-extrabold">
              {totals.kcal}
              <span className="text-muted text-base"> {t('food.kcal')}</span>
            </p>
            <p className="text-muted text-sm">
              {t('food.target')} <span className="tnum">{dailyKcal}</span>
            </p>
          </div>
          <p className="tnum text-paid text-lg font-bold">
            {Math.max(0, dailyKcal - totals.kcal)} {t('food.left')}
          </p>
        </div>

        <div className="bg-line mt-3 h-2 overflow-hidden rounded-full">
          <div
            className="bg-ink h-full rounded-full"
            style={{ width: `${Math.min(100, (totals.kcal / dailyKcal) * 100)}%` }}
          />
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          {(
            [
              ['protein', totals.protein, DAILY_PROTEIN],
              ['carbs', totals.carbs, null],
              ['fat', totals.fat, null],
            ] as const
          ).map(([key, value, target]) => (
            <div key={key} className="bg-canvas rounded-xl py-2">
              <p className="tnum font-bold">
                {value}
                {target ? <span className="text-muted font-normal">/{target}</span> : null}
                <span className="text-muted text-xs"> {t('food.g')}</span>
              </p>
              <p className="text-muted text-xs font-semibold">{t(`food.${key}`)}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Water and supplements: tap counters, never a keyboard. */}
      <div className="grid gap-3 sm:grid-cols-2">
        <Card className="p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="tnum text-3xl font-extrabold">{state.water}</p>
              <p className="text-muted mt-1 text-xs font-semibold">{t('food.water')}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="-"
                onClick={() => actions.addWater(-1)}
                className="border-line size-12 rounded-xl border text-xl font-bold"
              >
                −
              </button>
              <button
                type="button"
                aria-label={t('food.addGlass')}
                onClick={() => actions.addWater(1)}
                className="bg-ink size-12 rounded-xl text-xl font-bold text-white"
              >
                +
              </button>
            </div>
          </div>
          <div className="mt-3 flex gap-1">
            {Array.from({ length: 8 }).map((_, i) => (
              <span
                key={i}
                className={cn('h-2 flex-1 rounded-full', i < state.water ? 'bg-ink' : 'bg-line')}
              />
            ))}
          </div>
        </Card>

        <Card className="p-4">
          <p className="text-muted mb-3 text-xs font-semibold">{t('food.supplements')}</p>
          <div className="space-y-2">
            {(['protein', 'creatine', 'vitamins'] as const).map((sup) => {
              const taken = state.supplements.includes(sup)
              return (
                <button
                  key={sup}
                  type="button"
                  onClick={() => actions.toggleSupplement(sup)}
                  className={cn(
                    'min-h-tap flex w-full items-center justify-between rounded-xl px-4 text-sm font-bold',
                    taken ? 'bg-paid-bg text-paid' : 'border border-line bg-surface',
                  )}
                >
                  {t(`food.${sup}`)}
                  {taken ? <Icon name="check" size={18} /> : null}
                </button>
              )
            })}
          </div>
        </Card>
      </div>

      {analyzing ? (
        <Card className="p-6 text-center">
          <p className="font-semibold">{t('food.analyzing')}</p>
          <div className="bg-line mt-3 h-1.5 overflow-hidden rounded-full">
            <div className="bg-ink h-full w-1/3 animate-pulse rounded-full" />
          </div>
        </Card>
      ) : null}

      {draft && scaled ? (
        <Card className="overflow-hidden">
          <CardTitle>{t('food.estimate')}</CardTitle>
          {draft.photo ? (
            <img src={draft.photo} alt="" className="max-h-56 w-full object-cover" />
          ) : null}
          <div className="space-y-4 p-4">
            <Field label={t('food.mealName')}>
              <Input value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} />
            </Field>

            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-bold">{t('food.portion')}</span>
              <Stepper value={portion} step={0.5} min={0.5} onChange={setPortion} />
            </div>

            <div className="grid grid-cols-4 gap-2 text-center">
              {(
                [
                  ['kcal', scaled.kcal],
                  ['protein', scaled.protein],
                  ['carbs', scaled.carbs],
                  ['fat', scaled.fat],
                ] as const
              ).map(([key, value]) => (
                <div key={key} className="bg-canvas rounded-xl py-2">
                  <p className="tnum font-bold">{value}</p>
                  <p className="text-muted text-xs font-semibold">{t(`food.${key}`)}</p>
                </div>
              ))}
            </div>

            <p className="text-muted text-xs">{t('food.notSure')}</p>

            {error ? (
              <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
                {t('common.error')}
              </p>
            ) : null}

            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" size="lg" onClick={() => setDraft(null)} disabled={saving}>
                {t('common.cancel')}
              </Button>
              <Button size="lg" disabled={saving} onClick={() => void confirm()}>
                <Icon name="check" />
                {t('food.confirm')}
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {analyzeError && !draft && !analyzing ? (
        <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
          {t('food.analyzeError')}
        </p>
      ) : null}

      {!draft && !analyzing ? (
        <div className="grid grid-cols-2 gap-2">
          <Button variant="brand" size="lg" onClick={() => fileRef.current?.click()}>
            <Icon name="camera" />
            {t('food.addPhoto')}
          </Button>
          <Button
            variant="secondary"
            size="lg"
            onClick={() => {
              setDraft({ label: '', kcal: 0, protein: 0, carbs: 0, fat: 0 })
              setPortion(1)
            }}
          >
            {t('food.addManual')}
          </Button>
        </div>
      ) : null}

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onPhoto(file)
          e.target.value = ''
        }}
      />

      <Card>
        <CardTitle>{t('food.title')}</CardTitle>
        {entries.loading ? (
          <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
        ) : entries.error || !entries.data ? (
          <div className="p-4">
            <Empty>{t('common.error')}</Empty>
          </div>
        ) : entries.data.length === 0 ? (
          <p className="text-muted p-4 text-sm">{t('food.empty')}</p>
        ) : (
          <ul>
            {entries.data.map((f) => (
              <FoodRow key={f.id} entry={f} onRemove={() => void remove(f.id)} />
            ))}
          </ul>
        )}
      </Card>

      {entries.data?.length === 0 && !draft ? <Empty>{t('food.empty')}</Empty> : null}
    </Page>
  )
}

function FoodRow({ entry, onRemove }: { entry: ApiFoodEntry; onRemove: () => void }) {
  const { t } = useTranslation()
  const sourceKey = { photo: 'sourcePhoto', manual: 'sourceManual', agent: 'sourceAgent' } as const
  const thumb = useMediaUrl(entry.photo_key, 'member')

  return (
    <li className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0">
      {thumb ? (
        <img src={thumb} alt="" className="size-11 shrink-0 rounded-xl object-cover" />
      ) : (
        <span className="bg-canvas text-muted flex size-11 shrink-0 items-center justify-center rounded-xl">
          <Icon name="camera" size={18} />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{entry.label}</span>
        <span className="text-muted block text-xs">
          <bdi className="tnum">{hhmm(entry.at)}</bdi> · {t(`food.${sourceKey[entry.source]}`)}
        </span>
      </span>
      <span className="text-end">
        <span className="tnum block font-bold">{entry.kcal}</span>
        <span className="text-muted tnum block text-xs">
          {entry.protein} {t('food.g')}
        </span>
      </span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={t('food.remove')}
        className={cn('text-muted flex size-11 shrink-0 items-center justify-center rounded-xl')}
      >
        ×
      </button>
    </li>
  )
}
