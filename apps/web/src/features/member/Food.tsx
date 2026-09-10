import { useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { Stepper } from '@/components/ui/Stepper'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { useStore } from '@/state/store'
import type { FoodEntry } from '@/mocks/types'
import { cn } from '@/lib/cn'

const DAILY_KCAL = 2100
const DAILY_PROTEIN = 145

/**
 * Prototype stand-in for the vision call. Phase 5 sends the photo to Claude with the
 * member's usual foods as context and gets the same shape back; the confirm step stays
 * either way, because an estimate the member never checks is a number nobody trusts.
 */
const GUESSES = [
  { label: 'دجاج مشوي مع رز', kcal: 620, protein: 45, carbs: 68, fat: 14 },
  { label: 'لبنة مع خبز وزيتون', kcal: 410, protein: 16, carbs: 44, fat: 19 },
  { label: 'سلطة مع تونة', kcal: 280, protein: 28, carbs: 12, fat: 13 },
  { label: 'منقوشة زعتر', kcal: 350, protein: 8, carbs: 46, fat: 15 },
]

type Draft = (typeof GUESSES)[number] & { photo?: string }

export function MemberFood() {
  const { t } = useTranslation()
  const { state, actions } = useStore()
  const fileRef = useRef<HTMLInputElement>(null)

  const [analyzing, setAnalyzing] = useState(false)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [portion, setPortion] = useState(1)

  const totals = useMemo(
    () =>
      state.food.reduce(
        (acc, f) => ({
          kcal: acc.kcal + f.kcal,
          protein: acc.protein + f.protein,
          carbs: acc.carbs + f.carbs,
          fat: acc.fat + f.fat,
        }),
        { kcal: 0, protein: 0, carbs: 0, fat: 0 },
      ),
    [state.food],
  )

  const onPhoto = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      const photo = String(reader.result)
      setAnalyzing(true)
      // Stands in for the round trip to the vision model.
      setTimeout(() => {
        setDraft({ ...GUESSES[Math.floor(Math.random() * GUESSES.length)], photo })
        setPortion(1)
        setAnalyzing(false)
      }, 1200)
    }
    reader.readAsDataURL(file)
  }

  const scaled = draft && {
    kcal: Math.round(draft.kcal * portion),
    protein: Math.round(draft.protein * portion),
    carbs: Math.round(draft.carbs * portion),
    fat: Math.round(draft.fat * portion),
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
              {t('food.target')} <span className="tnum">{DAILY_KCAL}</span>
            </p>
          </div>
          <p className="tnum text-paid text-lg font-bold">
            {Math.max(0, DAILY_KCAL - totals.kcal)} {t('food.left')}
          </p>
        </div>

        <div className="bg-line mt-3 h-2 overflow-hidden rounded-full">
          <div
            className="bg-ink h-full rounded-full"
            style={{ width: `${Math.min(100, (totals.kcal / DAILY_KCAL) * 100)}%` }}
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

            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" size="lg" onClick={() => setDraft(null)}>
                {t('common.cancel')}
              </Button>
              <Button
                size="lg"
                onClick={() => {
                  actions.logFood({
                    label: draft.label,
                    ...scaled,
                    source: draft.photo ? 'photo' : 'manual',
                    photo: draft.photo,
                  })
                  setDraft(null)
                }}
              >
                <Icon name="check" />
                {t('food.confirm')}
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {!draft && !analyzing ? (
        <div className="grid grid-cols-2 gap-2">
          <Button size="lg" onClick={() => fileRef.current?.click()}>
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
        {state.food.length === 0 ? (
          <p className="text-muted p-4 text-sm">{t('food.empty')}</p>
        ) : (
          <ul>
            {state.food.map((f) => (
              <FoodRow key={f.id} entry={f} onRemove={() => actions.removeFood(f.id)} />
            ))}
          </ul>
        )}
      </Card>

      {state.food.length === 0 && !draft ? <Empty>{t('food.empty')}</Empty> : null}
    </Page>
  )
}

function FoodRow({ entry, onRemove }: { entry: FoodEntry; onRemove: () => void }) {
  const { t } = useTranslation()
  const sourceKey = { photo: 'sourcePhoto', manual: 'sourceManual', agent: 'sourceAgent' } as const

  return (
    <li className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0">
      {entry.photo ? (
        <img src={entry.photo} alt="" className="size-11 shrink-0 rounded-xl object-cover" />
      ) : (
        <span className="bg-canvas text-muted flex size-11 shrink-0 items-center justify-center rounded-xl">
          <Icon name="camera" size={18} />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{entry.label}</span>
        <span className="text-muted block text-xs">
          <bdi className="tnum">{entry.at}</bdi> · {t(`food.${sourceKey[entry.source]}`)}
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
