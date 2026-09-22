import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import {
  createPlan,
  deletePlan,
  getStaffRole,
  listMembers,
  listPlans,
  updatePlan,
} from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { ApiError } from '@/data/client'
import { usd } from '@/lib/format'
import type { ApiPlan } from '@/data/types'
import type { Lang } from '@/i18n'

interface Draft {
  ar: string
  en: string
  price: string
  days: string
}

const EMPTY: Draft = { ar: '', en: '', price: '', days: '30' }

function draftOf(plan: ApiPlan): Draft {
  return {
    ar: String(plan.name.ar ?? ''),
    en: String(plan.name.en ?? ''),
    price: String(plan.price_usd),
    days: String(plan.days),
  }
}

/** Both fields are required — a plan saved with one language renders blank
 * on the other side of the app. `days` is pre-filled and price is the only
 * number a gym owner has to think about. */
function isComplete(d: Draft): boolean {
  return (
    d.ar.trim().length > 0 &&
    d.en.trim().length > 0 &&
    Number(d.price) > 0 &&
    Number.isFinite(Number(d.price)) &&
    Number(d.days) >= 1
  )
}

export function ManagerPlans() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const plans = useAsync(listPlans, [])
  const members = useAsync(listMembers, [])

  // Mock mode has no login and so no role; the prototype shows the owner's
  // view, same as the staff screen.
  const viewer = getStaffRole() ?? 'super_admin'
  const canEdit = viewer === 'super_admin' || viewer === 'manager'

  const [editingId, setEditingId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function close() {
    setEditingId(null)
    setAdding(false)
    setConfirmingId(null)
    setDraft(EMPTY)
    setError(null)
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      plans.reload()
      members.reload()
    } catch (err) {
      // A 409 means membership periods reference this plan. Saying so is
      // the difference between an owner understanding the rule and
      // assuming the app is broken.
      setError(
        err instanceof ApiError && err.status === 409
          ? t('manager.plans.inUse')
          : t('common.error'),
      )
    } finally {
      setBusy(false)
    }
  }

  if (plans.loading || members.loading) {
    return <Page title={t('manager.plans.title')}><Empty>{t('common.loading')}</Empty></Page>
  }
  if (plans.error || members.error || !plans.data || !members.data) {
    return <Page title={t('manager.plans.title')}><Empty>{t('common.error')}</Empty></Page>
  }
  const memberList = members.data

  const form = (
    <Card className="space-y-4 p-4">
      <Field label={t('manager.plans.nameEn')}>
        <Input
          value={draft.en}
          onChange={(e) =>
            setDraft((d) => ({
              ...d,
              en: e.target.value,
              // Mirrored while the Arabic field still matches, so a gym
              // that calls the plan the same thing in both languages types
              // it once. Editing the Arabic field stops the mirroring.
              ar: d.ar === d.en ? e.target.value : d.ar,
            }))
          }
          dir="ltr"
          placeholder="Monthly"
          autoFocus
        />
      </Field>
      <Field label={t('manager.plans.nameAr')}>
        <Input
          value={draft.ar}
          onChange={(e) => setDraft((d) => ({ ...d, ar: e.target.value }))}
          dir="rtl"
          placeholder="شهري"
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('manager.plans.price')}>
          <Input
            value={draft.price}
            onChange={(e) => setDraft((d) => ({ ...d, price: e.target.value }))}
            inputMode="decimal"
            dir="ltr"
            className="tnum"
            placeholder="45"
          />
        </Field>
        <Field label={t('manager.plans.duration')}>
          <Input
            value={draft.days}
            onChange={(e) => setDraft((d) => ({ ...d, days: e.target.value }))}
            inputMode="numeric"
            dir="ltr"
            className="tnum"
          />
        </Field>
      </div>
      {editingId ? (
        // Not a footnote: nothing records what a membership period cost
        // when it was sold, so the owner dashboard's collected figure moves
        // with this number. See app/api/plans.py.
        <p className="text-muted text-xs">{t('manager.plans.priceIsRetroactive')}</p>
      ) : null}
      {error ? (
        <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">{error}</p>
      ) : null}
      <div className="flex gap-2">
        <Button variant="secondary" size="lg" onClick={close}>
          {t('common.cancel')}
        </Button>
        <Button
          full
          size="lg"
          disabled={busy || !isComplete(draft)}
          onClick={() =>
            void run(async () => {
              const body = {
                name: { ar: draft.ar.trim(), en: draft.en.trim() },
                price_usd: Number(draft.price),
                days: Number(draft.days),
              }
              if (editingId) await updatePlan(editingId, body)
              else await createPlan(body)
              close()
            })
          }
        >
          {t('common.save')}
        </Button>
      </div>
    </Card>
  )

  return (
    <Page title={t('manager.plans.title')} sub={t('manager.plans.sub')}>
      <div className="grid gap-3 sm:grid-cols-2">
        {plans.data.map((p) => {
          const count = memberList.filter((m) => m.plan_id === p.id).length
          if (editingId === p.id) return <div key={p.id}>{form}</div>
          return (
            <Card key={p.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="font-bold">{p.name[lang]}</h2>
                  <p className="text-muted text-sm">{t('manager.plans.days', { count: p.days })}</p>
                </div>
                <p className="tnum text-2xl font-extrabold">
                  <bdi>{usd(p.price_usd)}</bdi>
                </p>
              </div>
              <p className="text-muted mt-3 text-xs font-semibold">
                {t('manager.members.count', { count })}
              </p>

              {canEdit ? (
                confirmingId === p.id ? (
                  <div className="mt-3 space-y-2">
                    <p className="text-sm font-semibold">
                      {t('manager.plans.confirmDelete', { name: p.name[lang] })}
                    </p>
                    {error ? (
                      <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
                        {error}
                      </p>
                    ) : null}
                    <div className="flex gap-2">
                      <Button variant="secondary" onClick={close}>
                        {t('common.cancel')}
                      </Button>
                      {/* Black, not the `danger` red: red is payment state
                          in this product and nothing else. */}
                      <Button
                        full
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            await deletePlan(p.id)
                            close()
                          })
                        }
                      >
                        {t('common.remove')}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => {
                        close()
                        setDraft(draftOf(p))
                        setEditingId(p.id)
                      }}
                    >
                      {t('manager.plans.edit')}
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        close()
                        setConfirmingId(p.id)
                      }}
                    >
                      {t('common.remove')}
                    </Button>
                  </div>
                )
              ) : null}
            </Card>
          )
        })}
      </div>

      {canEdit ? (
        adding ? (
          form
        ) : (
          <Button
            variant="brand"
            full
            size="lg"
            onClick={() => {
              close()
              setDraft(EMPTY)
              setAdding(true)
            }}
          >
            <Icon name="add" size={18} />
            {t('manager.plans.add')}
          </Button>
        )
      ) : null}
    </Page>
  )
}
