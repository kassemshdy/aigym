import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button, buttonClass } from '@/components/ui/Button'
import { Field, Input, Segmented } from '@/components/ui/Field'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { createMember, listPlans } from '@/data/queries'
import { normalizePhone } from '@/lib/phone'
import { useAsync } from '@/data/useAsync'
import { usd } from '@/lib/format'
import { waLink } from '@/lib/whatsapp'
import type { Lang } from '@/i18n'
import { useGymName } from '@/gym/GymProvider'
import type { ApiMemberInjury, JoinPaymentMethod } from '@/data/types'
import { cn } from '@/lib/cn'
import { InjuryEditor } from '@/features/member/InjuryEditor'

const STEPS = ['step1', 'step2', 'step3', 'step4', 'step5'] as const

export function ManagerAddMember() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const gymName = useGymName(lang)
  const navigate = useNavigate()
  const plans = useAsync(listPlans, [])

  const [step, setStep] = useState(0)
  const [done, setDone] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)
  const [form, setForm] = useState({
    name: '',
    phone: '',
    planId: '',
    heightCm: '',
    weightKg: '',
    goal: 'health' as 'lose' | 'gain' | 'strength' | 'health',
    level: 'new' as 'new' | 'mid' | 'strong',
    daysPerWeek: '3' as '2' | '3' | '4' | '5',
    job: 'desk' as 'desk' | 'active' | 'shift',
    bodyFat: '',
    sleepHours: '7',
    injuries: [] as ApiMemberInjury[],
    payment: 'cash' as JoinPaymentMethod,
  })
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const selectedPlanId = form.planId || plans.data?.[0]?.id || ''
  const selectedPlan = plans.data?.find((p) => p.id === selectedPlanId)
  // The server stores every number as +961… and 422s one it cannot
  // (decision 44). Checked here too so a typo is caught on the step
  // that holds the field, rather than four steps later as a generic
  // failure with nothing pointing at the phone.
  const phoneOk = normalizePhone(form.phone) !== null

  async function finish() {
    setSaving(true)
    setError(false)
    try {
      await createMember({
        name: form.name,
        name_en: form.name,
        phone: form.phone,
        plan_id: selectedPlanId,
        goal: form.goal,
        level: form.level,
        height_cm: Number(form.heightCm) || 0,
        weight_kg: Number(form.weightKg) || 0,
        body_fat: form.bodyFat ? Number(form.bodyFat) : null,
        injuries: form.injuries,
        days_per_week: Number(form.daysPerWeek),
        job: form.job,
        sleep_hours: Number(form.sleepHours) || 7,
        payment_method: form.payment,
      })
      setDone(true)
    } catch {
      setError(true)
    } finally {
      setSaving(false)
    }
  }

  if (done) {
    return (
      <Page>
        <Card className="space-y-4 p-6 text-center">
          <span className="bg-paid-bg text-paid mx-auto flex size-16 items-center justify-center rounded-full">
            <Icon name="check" size={32} />
          </span>
          <h1 className="text-lg font-extrabold">{t('manager.add.created')}</h1>
          <p className="font-semibold">{form.name}</p>
          <a
            href={waLink(
              form.phone,
              t('whatsapp.welcome', {
                name: form.name,
                gym: gymName,
                // Straight to their own login, phone already filled in.
                link: `${window.location.origin}/login?phone=${encodeURIComponent(
                  normalizePhone(form.phone) ?? form.phone,
                )}`,
              }),
            )}
            target="_blank"
            rel="noreferrer"
            className={buttonClass('secondary', 'lg', true)}
          >
            <Icon name="whatsapp" />
            {t('manager.member.whatsapp')}
          </a>
          <Button full size="lg" onClick={() => navigate('/manager/members')}>
            {t('common.done')}
          </Button>
        </Card>
      </Page>
    )
  }

  return (
    <Page title={t('manager.add.title')} sub={t(`manager.add.${STEPS[step]}`)}>
      <div className="flex gap-1.5">
        {STEPS.map((s, i) => (
          <span
            key={s}
            className={cn('h-1.5 flex-1 rounded-full', i <= step ? 'bg-ink' : 'bg-line')}
          />
        ))}
      </div>

      <Card className="space-y-4 p-4">
        {step === 0 && (
          <>
            <Field label={t('manager.add.name')}>
              <Input value={form.name} onChange={(e) => set('name', e.target.value)} autoFocus />
            </Field>
            <Field label={t('manager.add.phone')}>
              <Input
                value={form.phone}
                onChange={(e) => set('phone', e.target.value)}
                inputMode="tel"
                dir="ltr"
                placeholder="+961 70 000 000"
              />
            </Field>
            {form.phone.trim() && !phoneOk ? (
              <p className="text-muted text-sm font-semibold">{t('common.phoneInvalid')}</p>
            ) : null}
          </>
        )}

        {step === 1 && (
          <Field label={t('manager.plans.title')}>
            {plans.loading ? (
              <Empty>{t('common.loading')}</Empty>
            ) : plans.error || !plans.data ? (
              <Empty>{t('common.error')}</Empty>
            ) : (
              <div className="space-y-2">
                {plans.data.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => set('planId', p.id)}
                    className={cn(
                      'min-h-tap-lg flex w-full items-center justify-between rounded-xl px-4 text-start',
                      selectedPlanId === p.id ? 'bg-ink text-white' : 'border border-line bg-surface',
                    )}
                  >
                    <span className="font-semibold">{p.name[lang]}</span>
                    <span className="tnum font-bold">{usd(p.price_usd)}</span>
                  </button>
                ))}
              </div>
            )}
          </Field>
        )}

        {/* Asked on the plan step, beside the price it is about. Cash is
            preselected because joining and paying happen in the same
            minute at a Lebanese desk; without this the member showed
            "Paid" with no payment behind it. Decision 48. */}
        {step === 1 && selectedPlan ? (
          <div>
            <Field label={t('manager.add.paidToday')}>
              <Segmented
                value={form.payment}
                onChange={(v) => set('payment', v)}
                columns={3}
                options={[
                  { value: 'cash', label: t('manager.payments.cash') },
                  { value: 'transfer', label: t('manager.payments.transfer') },
                  { value: 'unpaid', label: t('manager.add.notYet') },
                ]}
              />
            </Field>
            {/* Outside the Field: its <label> forwards a tap anywhere inside
                it to the first button, so a note in there selects Cash. */}
            <p className="text-muted mt-2 text-sm font-semibold">
              {t(form.payment === 'unpaid' ? 'manager.add.owesNote' : 'manager.add.paidNote', {
                amount: usd(selectedPlan.price_usd),
              })}
            </p>
          </div>
        ) : null}

        {step === 2 && (
          <>
            <Field label={t('manager.member.height')}>
              <Input value={form.heightCm} onChange={(e) => set('heightCm', e.target.value)} inputMode="numeric" placeholder="175" />
            </Field>
            <Field label={t('manager.member.weight')}>
              <Input value={form.weightKg} onChange={(e) => set('weightKg', e.target.value)} inputMode="numeric" placeholder="78" />
            </Field>
            <Field label={t('manager.add.goal')}>
              <Segmented
                value={form.goal}
                onChange={(v) => set('goal', v)}
                options={(['lose', 'gain', 'strength', 'health'] as const).map((v) => ({
                  value: v,
                  label: t(`goal.${v}`),
                }))}
              />
            </Field>
          </>
        )}

        {step === 3 && (
          <>
            <Field label={t('manager.add.level')}>
              <Segmented
                value={form.level}
                onChange={(v) => set('level', v)}
                columns={3}
                options={(['new', 'mid', 'strong'] as const).map((v) => ({ value: v, label: t(`level.${v}`) }))}
              />
            </Field>
            <Field label={t('manager.member.daysPerWeek')}>
              <Segmented
                value={form.daysPerWeek}
                onChange={(v) => set('daysPerWeek', v)}
                columns={4}
                options={(['2', '3', '4', '5'] as const).map((v) => ({ value: v, label: v }))}
              />
            </Field>
            <Field label={t('manager.member.lifestyle')}>
              <Segmented
                value={form.job}
                onChange={(v) => set('job', v)}
                columns={3}
                options={(['desk', 'active', 'shift'] as const).map((v) => ({ value: v, label: t(`job.${v}`) }))}
              />
            </Field>
          </>
        )}

        {step === 4 && (
          <>
            <Field label={t('manager.member.bodyFat')}>
              <Input
                value={form.bodyFat}
                onChange={(e) => set('bodyFat', e.target.value)}
                inputMode="numeric"
                placeholder="18"
              />
            </Field>
            <Field label={t('manager.member.sleep')}>
              <Input
                value={form.sleepHours}
                onChange={(e) => set('sleepHours', e.target.value)}
                inputMode="numeric"
                placeholder="7"
              />
            </Field>
            <div>
              <span className="text-muted mb-1.5 block text-sm font-semibold">
                {t('manager.member.injuries')}
              </span>
              <InjuryEditor
                injuries={form.injuries}
                onChange={(injuries) => set('injuries', injuries)}
              />
            </div>
            {error ? (
              <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
                {t('common.error')}
              </p>
            ) : null}
          </>
        )}
      </Card>

      <div className="flex gap-2">
        {step > 0 ? (
          <Button variant="secondary" size="lg" onClick={() => setStep((s) => s - 1)}>
            {t('common.back')}
          </Button>
        ) : (
          <Link to="/manager" className={buttonClass('secondary', 'lg')}>
            {t('common.cancel')}
          </Link>
        )}
        <Button
          size="lg"
          full
          disabled={saving || (step === 0 && (!form.name.trim() || !phoneOk))}
          onClick={() => (step === STEPS.length - 1 ? void finish() : setStep((s) => s + 1))}
        >
          {step === STEPS.length - 1 ? t('manager.add.finish') : t('common.next')}
        </Button>
      </div>
    </Page>
  )
}
