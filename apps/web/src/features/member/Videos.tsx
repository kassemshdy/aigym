import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { Chip } from '@/components/ui/Badge'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { getVideo, listVideos } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import type { ApiVideo } from '@/data/types'
import type { Lang } from '@/i18n'
import { useGymName } from '@/gym/GymProvider'
import { isShort, youtubeThumb } from '@/lib/youtube'

const MUSCLES = ['chest', 'back', 'legs', 'shoulders', 'core'] as const

const thumb = youtubeThumb

/** A Short as YouTube shows it: a vertical tile, title over the picture. */
function ShortTile({ v, lang }: { v: ApiVideo; lang: Lang }) {
  return (
    <Link
      to={`/member/videos/${v.id}`}
      className="bg-ink relative block aspect-[9/16] overflow-hidden rounded-2xl"
    >
      <img
        src={thumb(v)}
        alt=""
        loading="lazy"
        onError={(e) => {
          e.currentTarget.hidden = true
        }}
        className="size-full object-cover"
      />
      <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent p-3 pt-10">
        <span className="line-clamp-2 text-sm font-bold text-white">{v.title[lang]}</span>
      </span>
    </Link>
  )
}

export function MemberVideos() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const gymName = useGymName(lang)
  const [muscle, setMuscle] = useState<'all' | (typeof MUSCLES)[number]>('all')
  const videos = useAsync(() => listVideos('member'), [])

  if (videos.loading) {
    return (
      <Page title={t('member.videos.title')} sub={t('member.videos.by', { gym: gymName })}>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }
  if (videos.error || !videos.data) {
    return (
      <Page title={t('member.videos.title')} sub={t('member.videos.by', { gym: gymName })}>
        <Empty>{t('common.error')}</Empty>
      </Page>
    )
  }

  const list = videos.data.filter((v) => muscle === 'all' || v.muscle_group === muscle)
  const shorts = list.filter(isShort)
  const long = list.filter((v) => !isShort(v))

  return (
    <Page title={t('member.videos.title')} sub={t('member.videos.by', { gym: gymName })}>
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        <Chip active={muscle === 'all'} onClick={() => setMuscle('all')}>
          {t('common.all')}
        </Chip>
        {MUSCLES.map((m) => (
          <Chip key={m} active={muscle === m} onClick={() => setMuscle(m)}>
            {t(`muscle.${m}`)}
          </Chip>
        ))}
      </div>

      {list.length === 0 ? <Empty>{t('common.none')}</Empty> : null}

      {shorts.length > 0 ? (
        <section className="space-y-2">
          <h2 className="font-extrabold">{t('member.videos.shorts')}</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {shorts.map((v) => (
              <ShortTile key={v.id} v={v} lang={lang} />
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {long.map((v) => (
          <Link key={v.id} to={`/member/videos/${v.id}`}>
            <Card className="overflow-hidden">
              <div className="bg-ink relative aspect-video">
                <img
                  src={thumb(v)}
                  alt=""
                  loading="lazy"
                  onError={(e) => {
                    e.currentTarget.hidden = true
                  }}
                  className="size-full object-cover opacity-90"
                />
                <span className="absolute inset-0 flex items-center justify-center text-white">
                  <Icon name="play" size={40} />
                </span>
                <span className="tnum absolute bottom-2 end-2 rounded bg-black/70 px-1.5 py-0.5 text-xs font-bold text-white" dir="ltr">
                  {Math.floor(v.seconds / 60)}:{String(v.seconds % 60).padStart(2, '0')}
                </span>
              </div>
              <div className="p-3">
                <p className="font-semibold">{v.title[lang]}</p>
                <p className="text-muted mt-0.5 text-xs">
                  {t(`muscle.${v.muscle_group}`, v.muscle_group)} ·{' '}
                  {t(`equipment.${v.equipment}`, v.equipment)} ·{' '}
                  {t('member.videos.views', { count: v.view_count })}
                </p>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </Page>
  )
}

export function MemberVideoDetail() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const video = useAsync(() => getVideo(id, 'member'), [id])

  if (video.loading) {
    return (
      <Page>
        <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
      </Page>
    )
  }
  if (video.error || !video.data) {
    return (
      <Page>
        <Empty>{t('common.none')}</Empty>
      </Page>
    )
  }

  const v = video.data

  return (
    <Page>
      <BackLink to="/member/videos" />
      <Card className="overflow-hidden">
        {/* Unlisted embed: zero hosting cost, and the link is the only access control.
            A Short is filmed vertically, so it gets a 9:16 frame sized by the
            screen's height — in 16:9 it played as a strip between black bars. */}
        <div className={isShort(v) ? 'bg-ink flex justify-center' : 'bg-ink aspect-video'}>
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${v.external_id}`}
            title={v.title[lang]}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className={
              isShort(v)
                ? 'aspect-[9/16] h-[58dvh] max-w-full border-0'
                : 'size-full border-0'
            }
          />
        </div>
        <div className="p-4">
          <h1 className="text-lg font-extrabold">{v.title[lang]}</h1>
          <p className="text-muted mt-1 text-sm">
            {t(`muscle.${v.muscle_group}`, v.muscle_group)} ·{' '}
            {t(`equipment.${v.equipment}`, v.equipment)} ·{' '}
            {t('member.videos.views', { count: v.view_count })}
          </p>
        </div>
      </Card>
    </Page>
  )
}
