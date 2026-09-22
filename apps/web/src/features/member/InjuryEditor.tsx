import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/Button'
import { Field, Input, Segmented } from '@/components/ui/Field'
import { Icon } from '@/components/ui/Icon'
import type { ApiMemberInjury, InjuryBodyPart } from '@/data/types'

const BODY_PARTS: InjuryBodyPart[] = [
  'lower_back', 'knee_left', 'knee_right', 'shoulder_left', 'shoulder_right',
  'hip', 'neck', 'wrist', 'ankle', 'other',
]

const SEVERITIES = ['none', 'mild', 'moderate', 'severe'] as const

/** Shared between AddMember.tsx (a member's first snapshot) and
 * EditProfile.tsx (a member editing their own). body_part is a canonical
 * key (Segmented, not typed) so the guardrail logic (app/domain/
 * guardrails.py) can reason about it deterministically — see decision 30. */
export function InjuryEditor({
  injuries,
  onChange,
}: {
  injuries: ApiMemberInjury[]
  onChange: (injuries: ApiMemberInjury[]) => void
}) {
  const { t } = useTranslation()

  function add() {
    onChange([...injuries, { body_part: 'other', note: { ar: '', en: '' }, severity: null }])
  }

  function update(index: number, patch: Partial<ApiMemberInjury>) {
    onChange(injuries.map((injury, i) => (i === index ? { ...injury, ...patch } : injury)))
  }

  function remove(index: number) {
    onChange(injuries.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      {injuries.map((injury, i) => (
        <div key={i} className="border-line space-y-3 rounded-xl border p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">
              {t('member.profile.injuryEditor.item', { n: i + 1 })}
            </span>
            <button
              type="button"
              onClick={() => remove(i)}
              aria-label={t('common.remove')}
              className="text-muted flex size-11 items-center justify-center"
            >
              <Icon name="close" size={18} />
            </button>
          </div>
          <Field label={t('member.profile.injuryEditor.bodyPart')}>
            <Segmented
              value={injury.body_part}
              onChange={(v) => update(i, { body_part: v })}
              columns={2}
              options={BODY_PARTS.map((bp) => ({ value: bp, label: t(`injuryBodyPart.${bp}`) }))}
            />
          </Field>
          <Field label={t('member.profile.injuryEditor.note')}>
            <Input
              value={injury.note.en || injury.note.ar}
              onChange={(e) => update(i, { note: { ar: e.target.value, en: e.target.value } })}
              placeholder={t('member.profile.injuryEditor.notePlaceholder')}
            />
          </Field>
          <Field label={t('member.profile.injuryEditor.severityLabel')}>
            <Segmented
              value={injury.severity ?? 'none'}
              onChange={(v) => update(i, { severity: v === 'none' ? null : v })}
              columns={4}
              options={SEVERITIES.map((s) => ({
                value: s,
                label: t(`member.profile.injuryEditor.severity.${s}`),
              }))}
            />
          </Field>
        </div>
      ))}
      <Button variant="secondary" size="lg" full onClick={add}>
        <Icon name="add" />
        {t('member.profile.injuryEditor.add')}
      </Button>
    </div>
  )
}
