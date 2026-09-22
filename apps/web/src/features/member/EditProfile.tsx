import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button, buttonClass } from '@/components/ui/Button'
import { Field, Input, Segmented } from '@/components/ui/Field'
import { Empty, Page } from '@/components/ui/Page'
import { BackLink } from '@/components/ui/BackLink'
import { currentMemberId as mockCurrentMemberId } from '@/mocks/data'
import { getCurrentMemberId, getMember, updateMyProfile } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { InjuryEditor } from '@/features/member/InjuryEditor'
import type { ApiMemberInjury, ApiMemberProfile } from '@/data/types'

/** A member editing their own body/lifestyle profile (Phase 5 stage 5) —
 * decision 28's /members/me/... pattern. daily_kcal_target is never
 * shown here: it's coach/AI-approval-only. */
export function MemberEditProfile() {
  const { t } = useTranslation()
  const memberId = getCurrentMemberId() ?? mockCurrentMemberId
  const member = useAsync(() => getMember(memberId), [memberId])

  if (member.loading) {
    return (
      <Page>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }
  if (member.error || !member.data?.profile) return <Page><Empty>{t('common.none')}</Empty></Page>

  return <EditProfileForm profile={member.data.profile} />
}

/** Split out so its local state can be initialized directly from the
 * already-loaded profile via useState's initializer — mounted only once
 * the fetch resolves, so there's no effect needed to sync fetched data
 * into local state (react-hooks/set-state-in-effect). */
function EditProfileForm({ profile }: { profile: ApiMemberProfile }) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [heightCm, setHeightCm] = useState(String(profile.height_cm))
  const [weightKg, setWeightKg] = useState(String(profile.weight_kg))
  const [bodyFat, setBodyFat] = useState(profile.body_fat != null ? String(profile.body_fat) : '')
  const [sleepHours, setSleepHours] = useState(String(profile.sleep_hours))
  const [job, setJob] = useState(profile.job as 'desk' | 'active' | 'shift')
  const [injuries, setInjuries] = useState<ApiMemberInjury[]>(profile.injuries)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)

  async function save() {
    setSaving(true)
    setError(false)
    try {
      await updateMyProfile({
        height_cm: Number(heightCm) || undefined,
        weight_kg: Number(weightKg) || undefined,
        body_fat: bodyFat ? Number(bodyFat) : null,
        sleep_hours: Number(sleepHours) || undefined,
        job,
        injuries,
      })
      navigate('/member/profile')
    } catch {
      setError(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Page title={t('member.profile.editTitle')}>
      <BackLink to="/member/profile" />

      <Card className="space-y-4 p-4">
        <Field label={t('manager.member.height')}>
          <Input value={heightCm} onChange={(e) => setHeightCm(e.target.value)} inputMode="numeric" />
        </Field>
        <Field label={t('manager.member.weight')}>
          <Input value={weightKg} onChange={(e) => setWeightKg(e.target.value)} inputMode="numeric" />
        </Field>
        <Field label={t('manager.member.bodyFat')}>
          <Input value={bodyFat} onChange={(e) => setBodyFat(e.target.value)} inputMode="numeric" />
        </Field>
        <Field label={t('manager.member.sleep')}>
          <Input value={sleepHours} onChange={(e) => setSleepHours(e.target.value)} inputMode="numeric" />
        </Field>
        <Field label={t('manager.member.lifestyle')}>
          <Segmented
            value={job}
            onChange={setJob}
            columns={3}
            options={(['desk', 'active', 'shift'] as const).map((v) => ({ value: v, label: t(`job.${v}`) }))}
          />
        </Field>
        <div>
          <span className="text-muted mb-1.5 block text-sm font-semibold">
            {t('manager.member.injuries')}
          </span>
          <InjuryEditor injuries={injuries} onChange={setInjuries} />
        </div>
        {error ? (
          <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
            {t('common.error')}
          </p>
        ) : null}
      </Card>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => navigate('/member/profile')}
          className={buttonClass('secondary', 'lg')}
        >
          {t('common.cancel')}
        </button>
        <Button size="lg" full disabled={saving} onClick={() => void save()}>
          {t('member.profile.save')}
        </Button>
      </div>
    </Page>
  )
}
