import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { buttonClass } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { findMember, memberName, nutrition, planForMember } from '@/mocks/data'
import type { CalorieBand } from '@/mocks/types'
import type { Lang } from '@/i18n'
import { listSep, text } from '@/lib/format'
import { cn } from '@/lib/cn'

const BANDS: CalorieBand[] = ['low', 'ok', 'high', 'unknown']

/** Tapped, not typed. Exact calories are optional and almost never entered on the floor. */
const QUICK_MEALS = [
  { ar: 'بيض', en: 'Eggs' },
  { ar: 'خبز', en: 'Bread' },
  { ar: 'دجاج', en: 'Chicken' },
  { ar: 'رز', en: 'Rice' },
  { ar: 'لبنة', en: 'Labneh' },
  { ar: 'سلطة', en: 'Salad' },
  { ar: 'قهوة', en: 'Coffee' },
  { ar: 'موز', en: 'Banana' },
]

export function CoachMemberCard() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const m = findMember(id)

  const existing = nutrition.find((n) => n.memberId === id)
  const [band, setBand] = useState<CalorieBand | null>(existing?.band ?? null)
  const [meals, setMeals] = useState<string[]>([])

  if (!m) return <Page><Empty>{t('common.none')}</Empty></Page>

  const plan = planForMember(m.id)
  const due = m.status === 'due'

  return (
    <Page>
      <BackLink to="/coach" />

      <Card className="p-4">
        <div className="flex items-center gap-4">
          <Avatar name={memberName(m, lang)} size="lg" />
          <div className="min-w-0">
            <h1 className="truncate text-xl font-extrabold">{memberName(m, lang)}</h1>
            <p className="text-muted text-sm">
              {t(`goal.${m.goal}`)} · {t(`level.${m.level}`)}
            </p>
          </div>
        </div>

        {/* The coach must see payment state before the session, not after. */}
        <p
          className={cn(
            'mt-4 rounded-xl px-4 py-3 text-center text-base font-bold',
            due ? 'bg-due-bg text-due' : 'bg-paid-bg text-paid',
          )}
        >
          {due ? t('coach.card.paidDue', { amount: m.owedUsd }) : t('coach.card.paidOk')}
        </p>

        {m.injuries.length > 0 ? (
          <p className="bg-soon-bg text-soon mt-2 rounded-xl px-4 py-3 text-center text-sm font-bold">
            {t('manager.member.injuries')}: {m.injuries.map((i) => text(i, lang)).join(listSep(lang))}
          </p>
        ) : null}
      </Card>

      <Card>
        <CardTitle>{t('coach.card.askFood')}</CardTitle>
        <div className="space-y-3 p-4">
          <p className="text-lg font-bold">{t('coach.card.foodQuestion')}</p>
          <div className="grid grid-cols-2 gap-2">
            {BANDS.map((b) => (
              <button
                key={b}
                type="button"
                onClick={() => setBand(b)}
                className={cn(
                  'min-h-tap-lg rounded-xl px-3 text-base font-bold',
                  band === b ? 'bg-ink text-white' : 'border border-line bg-surface active:bg-canvas',
                )}
              >
                {t(`coach.food.${b}`)}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            {QUICK_MEALS.map((meal) => (
              <button
                key={meal.en}
                type="button"
                onClick={() =>
                  setMeals((prev) =>
                    prev.includes(meal.en) ? prev.filter((x) => x !== meal.en) : [...prev, meal.en],
                  )
                }
                className={cn(
                  'min-h-11 rounded-full px-4 text-sm font-semibold',
                  meals.includes(meal.en) ? 'bg-ink text-white' : 'border border-line bg-surface',
                )}
              >
                {meal[lang]}
              </button>
            ))}
          </div>

          {band ? (
            <p className="text-paid flex items-center gap-2 text-sm font-bold">
              <Icon name="check" size={18} />
              {t('coach.food.saved')}
            </p>
          ) : null}
        </div>
      </Card>

      <Card>
        <CardTitle>{t('coach.card.todayWorkout')}</CardTitle>
        {!plan ? (
          <p className="text-muted p-4 text-sm">{t('coach.card.noPlan')}</p>
        ) : (
          <>
            <p className="border-line border-b px-4 py-3 font-bold">{plan.title[lang]}</p>
            <ul>
              {plan.exercises.map((e) => (
                <li
                  key={e.id}
                  className="border-line flex items-center justify-between gap-3 border-b px-4 py-3 last:border-0"
                >
                  <span className="font-semibold">{e.name[lang]}</span>
                  <span className="text-muted text-sm">
                    <bdi className="tnum">
                      {e.sets} × {text(e.reps, lang)}
                    </bdi>
                    {e.lastWeightKg ? (
                      <bdi className="tnum">
                        {' · '}
                        {e.lastWeightKg} {t('common.kg')}
                      </bdi>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>

      {plan ? (
        <Link to={`/coach/session/${m.id}`} className={buttonClass('brand', 'lg', true)}>
          <Icon name="dumbbell" />
          {t('coach.card.start')}
        </Link>
      ) : null}

      <Link to={`/coach/programs/${m.id}`} className={buttonClass('secondary', 'lg', true)}>
        <Icon name="list" />
        {t('coach.card.editPlan')}
      </Link>
    </Page>
  )
}
