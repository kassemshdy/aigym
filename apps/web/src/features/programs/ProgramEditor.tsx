import { useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { Button } from '@/components/ui/Button'
import { Field, Input, Segmented } from '@/components/ui/Field'
import { Stepper } from '@/components/ui/Stepper'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { useAsync } from '@/data/useAsync'
import {
  createExercise,
  createProgram,
  getActiveProgram,
  getMember,
  listExercises,
  replaceProgramExercises,
  updateProgram,
} from '@/data/queries'
import type { ApiExercise, ApiProgram } from '@/data/types'
import type { Lang } from '@/i18n'
import { text } from '@/lib/format'

const MUSCLE_GROUPS = ['chest', 'back', 'legs', 'shoulders', 'arms', 'core'] as const

interface EditableRow {
  key: string
  exerciseId: string
  exerciseName: { ar: string; en: string }
  sets: number
  reps: string
  targetWeightKg: number | null
}

const newKey = () => Math.random().toString(36).slice(2, 10)

/** Create/edit a member's one active workout plan. Reached from both the
 * manager member-detail screen and the coach member card — one editor, no
 * duplication, behind the shared RequireStaff guard (App.tsx). */
export function ProgramEditor() {
  const { memberId = '' } = useParams()
  const { pathname } = useLocation()
  const backTo = pathname.startsWith('/manager')
    ? `/manager/members/${memberId}`
    : `/coach/member/${memberId}`
  const { t } = useTranslation()

  const { data: member } = useAsync(() => getMember(memberId), [memberId])
  const { data: program, loading: programLoading } = useAsync(
    () => getActiveProgram(memberId),
    [memberId],
  )
  const { data: exercises, reload: reloadExercises } = useAsync(listExercises, [])

  if (programLoading || !member) {
    return (
      <Page>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }

  return (
    <ProgramEditorForm
      key={memberId}
      memberId={memberId}
      backTo={backTo}
      program={program}
      exercises={exercises ?? []}
      reloadExercises={reloadExercises}
    />
  )
}

function ProgramEditorForm({
  memberId,
  backTo,
  program,
  exercises,
  reloadExercises,
}: {
  memberId: string
  backTo: string
  program: ApiProgram | null
  exercises: ApiExercise[]
  reloadExercises: () => void
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const [title, setTitle] = useState(() => (program ? text(program.title, lang) : ''))
  const [rows, setRows] = useState<EditableRow[]>(() =>
    program
      ? program.exercises.map((pe) => ({
          key: newKey(),
          exerciseId: pe.exercise_id,
          exerciseName: pe.exercise_name,
          sets: pe.sets,
          reps: text(pe.reps, lang),
          targetWeightKg: pe.target_weight_kg,
        }))
      : [],
  )

  const [query, setQuery] = useState('')
  const [addingNew, setAddingNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [newMuscle, setNewMuscle] = useState<(typeof MUSCLE_GROUPS)[number]>('legs')

  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(false)

  function addRow(exercise: ApiExercise) {
    setRows((prev) => [
      ...prev,
      {
        key: newKey(),
        exerciseId: exercise.id,
        exerciseName: exercise.name,
        sets: 3,
        reps: '10',
        targetWeightKg: null,
      },
    ])
    setQuery('')
  }

  function removeRow(key: string) {
    setRows((prev) => prev.filter((r) => r.key !== key))
  }

  function moveRow(index: number, delta: number) {
    setRows((prev) => {
      const next = [...prev]
      const target = index + delta
      if (target < 0 || target >= next.length) return prev
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  async function createNewExercise() {
    if (!newName.trim()) return
    const exercise = await createExercise({
      name: { ar: newName.trim(), en: newName.trim() },
      muscle_group: newMuscle,
    })
    addRow(exercise)
    setNewName('')
    setAddingNew(false)
    reloadExercises()
  }

  async function save() {
    setSaving(true)
    setSaved(false)
    setError(false)
    try {
      const exercisesInput = rows.map((r) => ({
        exercise_id: r.exerciseId,
        sets: r.sets,
        reps: { ar: r.reps, en: r.reps },
        target_weight_kg: r.targetWeightKg,
      }))
      if (program) {
        await replaceProgramExercises(program.id, { exercises: exercisesInput })
        await updateProgram(program.id, { title: { ar: title, en: title } })
      } else {
        await createProgram(memberId, { title: { ar: title, en: title }, exercises: exercisesInput })
      }
      setSaved(true)
    } catch {
      setError(true)
    } finally {
      setSaving(false)
    }
  }

  const filteredCatalog = exercises.filter((e) => {
    const q = query.trim().toLowerCase()
    if (!q) return false
    return text(e.name, lang).toLowerCase().includes(q)
  })

  return (
    <Page>
      <BackLink to={backTo} />

      <Card className="p-4">
        <Field label={t('program.title')}>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t('program.titlePlaceholder')}
          />
        </Field>
      </Card>

      <Card>
        <CardTitle>{t('program.exercises')}</CardTitle>
        {rows.length === 0 ? (
          <div className="p-4">
            <Empty>{t('program.none')}</Empty>
          </div>
        ) : (
          <ul>
            {rows.map((row, i) => (
              <li key={row.key} className="border-line border-b px-4 py-3 last:border-0">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold">{text(row.exerciseName, lang)}</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      aria-label={t('program.moveUp')}
                      disabled={i === 0}
                      onClick={() => moveRow(i, -1)}
                      className="text-muted flex size-9 items-center justify-center disabled:opacity-30"
                    >
                      <Icon name="chevron" size={16} />
                    </button>
                    <button
                      type="button"
                      aria-label={t('program.moveDown')}
                      disabled={i === rows.length - 1}
                      onClick={() => moveRow(i, 1)}
                      className="text-muted flex size-9 rotate-180 items-center justify-center disabled:opacity-30"
                    >
                      <Icon name="chevron" size={16} />
                    </button>
                    <button
                      type="button"
                      aria-label={t('program.remove')}
                      onClick={() => removeRow(row.key)}
                      className="text-due flex size-9 items-center justify-center"
                    >
                      <Icon name="close" size={16} />
                    </button>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-muted text-xs font-semibold">{t('program.sets')}</span>
                    <Stepper
                      value={row.sets}
                      step={1}
                      min={1}
                      onChange={(v) =>
                        setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, sets: v } : r)))
                      }
                    />
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-muted text-xs font-semibold">{t('program.targetWeight')}</span>
                    <Stepper
                      value={row.targetWeightKg ?? 0}
                      step={2.5}
                      suffix={t('common.kg')}
                      onChange={(v) =>
                        setRows((prev) =>
                          prev.map((r) => (r.key === row.key ? { ...r, targetWeightKg: v } : r)),
                        )
                      }
                    />
                  </div>
                </div>
                <div className="mt-2">
                  <Field label={t('program.reps')}>
                    <Input
                      value={row.reps}
                      onChange={(e) =>
                        setRows((prev) =>
                          prev.map((r) => (r.key === row.key ? { ...r, reps: e.target.value } : r)),
                        )
                      }
                      placeholder="8-10"
                    />
                  </Field>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <CardTitle>{t('program.addExercise')}</CardTitle>
        <div className="space-y-3 p-4">
          <Field label={t('common.search')}>
            <Input value={query} onChange={(e) => setQuery(e.target.value)} />
          </Field>
          {filteredCatalog.length > 0 ? (
            <ul className="border-line divide-line divide-y rounded-xl border">
              {filteredCatalog.map((e) => (
                <li key={e.id}>
                  <button
                    type="button"
                    onClick={() => addRow(e)}
                    className="flex min-h-tap w-full items-center justify-between px-4 text-start font-semibold"
                  >
                    {text(e.name, lang)}
                    <Icon name="add" size={18} />
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          {addingNew ? (
            <div className="border-line space-y-3 rounded-xl border p-3">
              <Field label={t('program.newExerciseName')}>
                <Input value={newName} onChange={(e) => setNewName(e.target.value)} autoFocus />
              </Field>
              <Field label={t('program.muscleGroup')}>
                <Segmented
                  value={newMuscle}
                  columns={3}
                  onChange={setNewMuscle}
                  options={MUSCLE_GROUPS.map((g) => ({ value: g, label: t(`muscle.${g}`) }))}
                />
              </Field>
              <Button full disabled={!newName.trim()} onClick={() => void createNewExercise()}>
                {t('common.add')}
              </Button>
            </div>
          ) : (
            <Button variant="secondary" full onClick={() => setAddingNew(true)}>
              <Icon name="add" size={18} />
              {t('program.newExercise')}
            </Button>
          )}
        </div>
      </Card>

      {error ? (
        <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
          {t('common.error')}
        </p>
      ) : null}

      <Button
        variant="brand"
        full
        size="lg"
        disabled={saving || rows.length === 0 || !title.trim()}
        onClick={() => void save()}
      >
        {saved ? t('program.saved') : t('common.save')}
      </Button>
    </Page>
  )
}
