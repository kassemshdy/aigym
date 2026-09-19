import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input, Segmented } from '@/components/ui/Field'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { createVideo, listVideos, updateVideo } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import type { Lang } from '@/i18n'

const MUSCLES = ['chest', 'back', 'legs', 'shoulders', 'arms', 'core'] as const
const EQUIPMENT = ['barbell', 'dumbbell', 'machine', 'bodyweight'] as const

/** Accepts either a bare YouTube video id or a full watch/share/embed URL —
 * one less thing the coach has to get exactly right (decision 28: no live
 * oEmbed fetch, so this is the only parsing help they get). */
function extractYoutubeId(input: string): string {
  const trimmed = input.trim()
  const url = trimmed.match(/(?:v=|youtu\.be\/|embed\/)([\w-]{11})/)
  return url ? url[1] : trimmed
}

/** The video library's staff-side management screen (Phase 4 stage 3) —
 * reachable by any staff role per app/api/videos.py, linked from the
 * coach tab bar since coaches are the ones filming and cataloguing
 * training content. Mirrors ManagerStaff's list + lightweight add form. */
export function CoachVideos() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const videos = useAsync(listVideos, [])

  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  const [muscle, setMuscle] = useState<(typeof MUSCLES)[number]>('chest')
  const [equipment, setEquipment] = useState<(typeof EQUIPMENT)[number]>('barbell')
  const [urlOrId, setUrlOrId] = useState('')
  const [seconds, setSeconds] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)

  function resetForm() {
    setTitle('')
    setMuscle('chest')
    setEquipment('barbell')
    setUrlOrId('')
    setSeconds('')
  }

  async function submit() {
    setSaving(true)
    setError(false)
    try {
      await createVideo({
        title: { ar: title.trim(), en: title.trim() },
        provider: 'youtube',
        external_id: extractYoutubeId(urlOrId),
        muscle_group: muscle,
        equipment,
        seconds: Number(seconds),
      })
      setAdding(false)
      resetForm()
      videos.reload()
    } catch {
      setError(true)
    } finally {
      setSaving(false)
    }
  }

  async function remove(videoId: string) {
    await updateVideo(videoId, { active: false })
    videos.reload()
  }

  return (
    <Page title={t('coach.videos.title')} sub={t('coach.videos.sub')}>
      <Card>
        <CardTitle>{t('coach.videos.list')}</CardTitle>
        {videos.loading ? (
          <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
        ) : videos.error || !videos.data ? (
          <div className="p-4">
            <Empty>{t('common.error')}</Empty>
          </div>
        ) : videos.data.length === 0 ? (
          <div className="p-4">
            <Empty>{t('common.none')}</Empty>
          </div>
        ) : (
          <ul>
            {videos.data.map((v) => (
              <li
                key={v.id}
                className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{v.title[lang]}</span>
                  <span className="text-muted block text-xs">
                    {t(`muscle.${v.muscle_group}`, v.muscle_group)} ·{' '}
                    {t(`equipment.${v.equipment}`, v.equipment)}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => void remove(v.id)}
                  aria-label={t('common.remove')}
                  className="text-muted flex size-11 items-center justify-center"
                >
                  <Icon name="close" size={18} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {adding ? (
        <Card className="space-y-4 p-4">
          <p className="text-muted text-sm font-semibold">{t('coach.videos.add')}</p>
          <Field label={t('coach.videos.videoTitle')}>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
          </Field>
          <Field label={t('coach.videos.link')}>
            <Input
              value={urlOrId}
              onChange={(e) => setUrlOrId(e.target.value)}
              dir="ltr"
              placeholder="https://youtube.com/watch?v=..."
            />
          </Field>
          <Field label={t('coach.videos.duration')}>
            <Input
              value={seconds}
              onChange={(e) => setSeconds(e.target.value)}
              inputMode="numeric"
              dir="ltr"
              placeholder="180"
            />
          </Field>
          <Field label={t('coach.videos.muscleGroup')}>
            <Segmented
              value={muscle}
              onChange={setMuscle}
              columns={3}
              options={MUSCLES.map((m) => ({ value: m, label: t(`muscle.${m}`) }))}
            />
          </Field>
          <Field label={t('coach.videos.equipment')}>
            <Segmented
              value={equipment}
              onChange={setEquipment}
              columns={2}
              options={EQUIPMENT.map((e) => ({ value: e, label: t(`equipment.${e}`) }))}
            />
          </Field>
          {error ? (
            <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
              {t('common.error')}
            </p>
          ) : null}
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="lg"
              onClick={() => {
                setAdding(false)
                setError(false)
                resetForm()
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button
              full
              size="lg"
              disabled={saving || !title.trim() || !urlOrId.trim() || !seconds.trim()}
              onClick={() => void submit()}
            >
              {t('common.save')}
            </Button>
          </div>
        </Card>
      ) : (
        <Button variant="brand" full size="lg" onClick={() => setAdding(true)}>
          <Icon name="add" size={18} />
          {t('coach.videos.add')}
        </Button>
      )}
    </Page>
  )
}
