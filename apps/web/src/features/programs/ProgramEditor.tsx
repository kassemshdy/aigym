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
  updateExercise,
  updateProgram,
} from '@/data/queries'
import type { ApiExercise, ApiProgram, ProgramDay } from '@/data/types'
import { PROGRAM_TEMPLATES, type ProgramTemplate } from './templates'
import { cn } from '@/lib/cn'
import type { Lang } from '@/i18n'
import { text } from '@/lib/format'
import { HelpTip } from '@/help/HelpTip'

const MUSCLE_GROUPS = ['chest', 'back', 'legs', 'shoulders', 'arms', 'core'] as const

interface EditableRow {
  key: string
  /** Which of the plan's days this row is on. Decision 53. */
  dayIndex: number
  exerciseId: string
  exerciseName: { ar: string; en: string }
  sets: number
  reps: string
  targetWeightKg: number | null
}

const newKey = () => Math.random().toString(36).slice(2, 10)

const AR_LETTERS = ['أ', 'ب', 'ج', 'د', 'هـ', 'و', 'ز']
const EN_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
/** Matches MAX_DAYS in app/api/programs.py. */
const MAX_DAYS = 7
const defaultDay = (i: number): ProgramDay => ({ ar: `اليوم ${AR_LETTERS[i]}`, en: `Day ${EN_LETTERS[i]}` })

/** A template's exercise in this gym's catalog, by either name. */
function findInCatalog(catalog: ApiExercise[], name: { ar: string; en: string }) {
  const en = name.en.trim().toLowerCase()
  return catalog.find((e) => e.name.en.trim().toLowerCase() === en || e.name.ar === name.ar)
}

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
          dayIndex: pe.day_index,
          exerciseId: pe.exercise_id,
          exerciseName: pe.exercise_name,
          sets: pe.sets,
          reps: text(pe.reps, lang),
          targetWeightKg: pe.target_weight_kg,
        }))
      : [],
  )

  // A one-day plan has no day titles; days appear once a second is added.
  const [days, setDays] = useState<ProgramDay[]>(() => program?.days ?? [])
  const [activeDay, setActiveDay] = useState(0)
  const [pickingTemplate, setPickingTemplate] = useState(() => !program)
  const [confirmTemplate, setConfirmTemplate] = useState<ProgramTemplate | null>(null)
  const [applying, setApplying] = useState(false)

  const [query, setQuery] = useState('')
  const [addingNew, setAddingNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [newMuscle, setNewMuscle] = useState<(typeof MUSCLE_GROUPS)[number]>('legs')
  const [newVideoUrl, setNewVideoUrl] = useState('')

  const [editingVideoFor, setEditingVideoFor] = useState<string | null>(null)
  const [videoUrlDraft, setVideoUrlDraft] = useState('')
  const [savingVideo, setSavingVideo] = useState(false)

  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(false)

  function addRow(exercise: ApiExercise) {
    setRows((prev) => [
      ...prev,
      {
        key: newKey(),
        dayIndex: activeDay,
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

  /** Swap with the neighbour on the same day — rows of other days are
   * interleaved in the array but never visible here. */
  function moveRow(key: string, delta: number) {
    setRows((prev) => {
      const sameDay = prev.map((r, i) => ({ r, i })).filter(({ r }) => r.dayIndex === activeDay)
      const at = sameDay.findIndex(({ r }) => r.key === key)
      const other = sameDay[at + delta]
      if (at === -1 || !other) return prev
      const next = [...prev]
      ;[next[sameDay[at].i], next[other.i]] = [next[other.i], next[sameDay[at].i]]
      return next
    })
  }

  function addDay() {
    if (days.length >= MAX_DAYS) return
    // Going from one day to two names both, so the first keeps its exercises.
    const next = days.length === 0 ? [defaultDay(0), defaultDay(1)] : [...days, defaultDay(days.length)]
    setDays(next)
    setActiveDay(next.length - 1)
  }

  /** Removing a day removes its exercises; later days shift down one. Back
   * to one day, it is a one-day plan again, with no day titles. */
  function removeDay(index: number) {
    setRows((prev) =>
      prev
        .filter((r) => r.dayIndex !== index)
        .map((r) => (r.dayIndex > index ? { ...r, dayIndex: r.dayIndex - 1 } : r)),
    )
    setDays((prev) => {
      const next = prev.filter((_, i) => i !== index)
      return next.length <= 1 ? [] : next
    })
    setActiveDay((d) => Math.max(0, d > index ? d - 1 : d === index ? d - 1 : d))
  }

  function renameDay(index: number, value: string) {
    setDays((prev) => prev.map((d, i) => (i === index ? { ar: value, en: value } : d)))
  }

  /** Fill the editor from a template. Exercises the gym's catalog lacks are
   * added to it first, so a template works at any gym. Nothing is saved
   * until the coach presses Save. */
  async function applyTemplate(template: ProgramTemplate) {
    setApplying(true)
    setError(false)
    try {
      let catalog = exercises
      const next: EditableRow[] = []
      for (const [dayIndex, day] of template.days.entries()) {
        for (const te of day.exercises) {
          let found = findInCatalog(catalog, te.name)
          if (!found) {
            found = await createExercise({ name: te.name, muscle_group: te.muscle, video_url: null })
            catalog = [...catalog, found]
          }
          next.push({
            key: newKey(),
            dayIndex,
            exerciseId: found.id,
            exerciseName: found.name,
            sets: te.sets,
            reps: text(te.reps, lang),
            targetWeightKg: null,
          })
        }
      }
      reloadExercises()
      setRows(next)
      setDays(template.days.length > 1 ? template.days.map((d) => d.title) : [])
      setActiveDay(0)
      if (!title.trim()) setTitle(text(template.title, lang))
      setPickingTemplate(false)
      setConfirmTemplate(null)
    } catch {
      setError(true)
    } finally {
      setApplying(false)
    }
  }

  async function createNewExercise() {
    if (!newName.trim()) return
    const exercise = await createExercise({
      name: { ar: newName.trim(), en: newName.trim() },
      muscle_group: newMuscle,
      video_url: newVideoUrl.trim() || null,
    })
    addRow(exercise)
    setNewName('')
    setNewVideoUrl('')
    setAddingNew(false)
    reloadExercises()
  }

  function startEditingVideo(exercise: ApiExercise) {
    setEditingVideoFor(exercise.id)
    setVideoUrlDraft(exercise.video_url ?? '')
  }

  async function saveVideo(exerciseId: string) {
    setSavingVideo(true)
    try {
      await updateExercise(exerciseId, { video_url: videoUrlDraft.trim() || null })
      reloadExercises()
      setEditingVideoFor(null)
    } finally {
      setSavingVideo(false)
    }
  }

  async function save() {
    setSaving(true)
    setSaved(false)
    setError(false)
    try {
      // Grouped by day, keeping each day's own order.
      const ordered = [...rows].sort((a, b) => a.dayIndex - b.dayIndex)
      const exercisesInput = ordered.map((r) => ({
        exercise_id: r.exerciseId,
        day_index: r.dayIndex,
        sets: r.sets,
        reps: { ar: r.reps, en: r.reps },
        target_weight_kg: r.targetWeightKg,
      }))
      if (program) {
        await replaceProgramExercises(program.id, { exercises: exercisesInput, days })
        await updateProgram(program.id, { title: { ar: title, en: title } })
      } else {
        await createProgram(memberId, {
          title: { ar: title, en: title },
          days,
          exercises: exercisesInput,
        })
      }
      setSaved(true)
    } catch {
      setError(true)
    } finally {
      setSaving(false)
    }
  }

  const dayRows = rows.filter((r) => r.dayIndex === activeDay)

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

      {pickingTemplate ? (
        <Card>
          <CardTitle
            action={
              <button
                type="button"
                onClick={() => {
                  setPickingTemplate(false)
                  setConfirmTemplate(null)
                }}
                aria-label={t('common.cancel')}
                className="text-muted flex size-11 items-center justify-center"
              >
                <Icon name="close" size={18} />
              </button>
            }
          >
            {t('program.templates')}
          </CardTitle>
          <div className="space-y-2 p-4">
            {PROGRAM_TEMPLATES.map((tpl) => (
              <button
                key={tpl.id}
                type="button"
                disabled={applying}
                // Replacing a plan someone has already written asks first.
                onClick={() => (rows.length > 0 ? setConfirmTemplate(tpl) : void applyTemplate(tpl))}
                className={cn(
                  'min-h-tap-lg w-full rounded-xl px-4 py-3 text-start',
                  confirmTemplate?.id === tpl.id ? 'bg-ink text-white' : 'border-line bg-surface border',
                )}
              >
                <span className="block font-bold">{text(tpl.title, lang)}</span>
                <span
                  className={cn(
                    'block text-sm',
                    confirmTemplate?.id === tpl.id ? 'text-white/70' : 'text-muted',
                  )}
                >
                  {text(tpl.note, lang)}
                </span>
              </button>
            ))}
            {confirmTemplate ? (
              <div className="space-y-2 pt-2">
                <p className="text-sm font-semibold">{t('program.templateReplaces')}</p>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => setConfirmTemplate(null)}>
                    {t('common.cancel')}
                  </Button>
                  <Button full disabled={applying} onClick={() => void applyTemplate(confirmTemplate)}>
                    {t('program.useTemplate')}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </Card>
      ) : (
        <Button variant="secondary" full onClick={() => setPickingTemplate(true)}>
          <Icon name="list" size={18} />
          {t('program.templates')}
        </Button>
      )}

      {/* Days, in the order they repeat. A one-day plan shows only the
          button to add a second; titles appear with it. */}
      <Card className="space-y-3 p-4">
        {days.length > 1 ? (
          <>
            <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1" role="tablist">
              {days.map((d, i) => (
                <button
                  key={i}
                  type="button"
                  role="tab"
                  aria-selected={activeDay === i}
                  onClick={() => setActiveDay(i)}
                  className={cn(
                    'min-h-tap shrink-0 rounded-xl px-4 font-bold',
                    activeDay === i ? 'bg-ink text-white' : 'border-line bg-surface border',
                  )}
                >
                  {text(d, lang) || t('program.dayN', { n: i + 1 })}
                  <span className="tnum ms-2 text-xs opacity-70">
                    {rows.filter((r) => r.dayIndex === i).length}
                  </span>
                </button>
              ))}
            </div>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Field label={t('program.dayName')}>
                  <Input
                    value={text(days[activeDay] ?? { ar: '', en: '' }, lang)}
                    onChange={(e) => renameDay(activeDay, e.target.value)}
                  />
                </Field>
              </div>
              <Button variant="secondary" onClick={() => removeDay(activeDay)}>
                {t('program.removeDay')}
              </Button>
            </div>
          </>
        ) : (
          <p className="text-muted text-sm">{t('program.oneDay')}</p>
        )}
        {days.length < MAX_DAYS ? (
          <Button variant="secondary" full onClick={addDay}>
            <Icon name="add" size={18} />
            {t('program.addDay')}
          </Button>
        ) : null}
      </Card>

      <Card>
        <CardTitle>
          {days.length > 1
            ? `${t('program.exercises')} · ${text(days[activeDay], lang) || t('program.dayN', { n: activeDay + 1 })}`
            : t('program.exercises')}
        </CardTitle>
        {dayRows.length === 0 ? (
          <div className="p-4">
            <Empty>{t('program.none')}</Empty>
          </div>
        ) : (
          <ul>
            {dayRows.map((row, i) => (
              <li key={row.key} className="border-line border-b px-4 py-3 last:border-0">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold">{text(row.exerciseName, lang)}</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      aria-label={t('program.moveUp')}
                      disabled={i === 0}
                      onClick={() => moveRow(row.key, -1)}
                      // Up and down, not › and ‹: this reorders the list, and
                      // sideways chevrons read as next/previous.
                      className="text-muted flex size-11 -rotate-90 items-center justify-center disabled:opacity-30"
                    >
                      <Icon name="chevron" size={18} />
                    </button>
                    <button
                      type="button"
                      aria-label={t('program.moveDown')}
                      disabled={i === dayRows.length - 1}
                      onClick={() => moveRow(row.key, 1)}
                      className="text-muted flex size-11 rotate-90 items-center justify-center disabled:opacity-30"
                    >
                      <Icon name="chevron" size={18} />
                    </button>
                    <button
                      type="button"
                      aria-label={t('program.remove')}
                      onClick={() => removeRow(row.key)}
                      className="text-muted flex size-11 items-center justify-center"
                    >
                      <Icon name="close" size={16} />
                    </button>
                  </div>
                </div>
                {/* Stacked on a phone: two steppers side by side need ~430px,
                    and at 390 the second one's + was pushed off the card. */}
                <div className="mt-3 grid gap-2 sm:grid-cols-2 sm:gap-3">
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
        <CardTitle action={<HelpTip text={t('help.videoLink')} />}>{t('program.addExercise')}</CardTitle>
        <div className="space-y-3 p-4">
          <Field label={t('common.search')}>
            <Input value={query} onChange={(e) => setQuery(e.target.value)} />
          </Field>
          {filteredCatalog.length > 0 ? (
            <ul className="border-line divide-line divide-y rounded-xl border">
              {filteredCatalog.map((e) => (
                <li key={e.id}>
                  <div className="flex items-center gap-1 px-2">
                    <button
                      type="button"
                      onClick={() => addRow(e)}
                      className="flex min-h-tap flex-1 items-center justify-between px-2 text-start font-semibold"
                    >
                      {text(e.name, lang)}
                      <Icon name="add" size={18} />
                    </button>
                    <button
                      type="button"
                      aria-label={t('program.videoUrl')}
                      onClick={() => startEditingVideo(e)}
                      className={
                        e.video_url
                          ? 'text-ink flex size-11 shrink-0 items-center justify-center'
                          : 'text-muted/50 flex size-11 shrink-0 items-center justify-center'
                      }
                    >
                      <Icon name="play" size={18} />
                    </button>
                  </div>
                  {editingVideoFor === e.id ? (
                    <div className="border-line space-y-2 border-t p-3">
                      <Field label={t('program.videoUrl')}>
                        <Input
                          value={videoUrlDraft}
                          onChange={(ev) => setVideoUrlDraft(ev.target.value)}
                          placeholder="https://youtube.com/..."
                          autoFocus
                        />
                      </Field>
                      <div className="flex gap-2">
                        <Button
                          full
                          disabled={savingVideo}
                          onClick={() => void saveVideo(e.id)}
                        >
                          {t('common.save')}
                        </Button>
                        <Button
                          variant="secondary"
                          full
                          disabled={savingVideo}
                          onClick={() => setEditingVideoFor(null)}
                        >
                          {t('common.cancel')}
                        </Button>
                      </div>
                    </div>
                  ) : null}
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
              <Field label={t('program.videoUrl')}>
                <Input
                  value={newVideoUrl}
                  onChange={(e) => setNewVideoUrl(e.target.value)}
                  placeholder="https://youtube.com/..."
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
