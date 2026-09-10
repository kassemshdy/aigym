import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { Chip } from '@/components/ui/Badge'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { findVideo, gym, videos } from '@/mocks/data'
import type { Video } from '@/mocks/types'
import type { Lang } from '@/i18n'

const MUSCLES = ['chest', 'back', 'legs', 'shoulders', 'core'] as const

const thumb = (v: Video) =>
  v.provider === 'youtube' ? `https://img.youtube.com/vi/${v.externalId}/mqdefault.jpg` : ''

export function MemberVideos() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const [muscle, setMuscle] = useState<'all' | (typeof MUSCLES)[number]>('all')

  const list = videos.filter((v) => muscle === 'all' || v.muscle === muscle)

  return (
    <Page title={t('member.videos.title')} sub={t('member.videos.by', { coach: gym.coach[lang] })}>
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

      <div className="grid gap-3 sm:grid-cols-2">
        {list.map((v) => (
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
                  {t(`muscle.${v.muscle}`)} · {t(`equipment.${v.equipment}`)} ·{' '}
                  {t('member.videos.views', { count: v.views })}
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
  const v = findVideo(id)

  if (!v) return <Page><Empty>{t('common.none')}</Empty></Page>

  return (
    <Page>
      <BackLink to="/member/videos" />
      <Card className="overflow-hidden">
        {/* Unlisted embed: zero hosting cost, and the link is the only access control. */}
        <div className="bg-ink aspect-video">
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${v.externalId}`}
            title={v.title[lang]}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="size-full border-0"
          />
        </div>
        <div className="p-4">
          <h1 className="text-lg font-extrabold">{v.title[lang]}</h1>
          <p className="text-muted mt-1 text-sm">
            {t(`muscle.${v.muscle}`)} · {t(`equipment.${v.equipment}`)} ·{' '}
            {t('member.videos.views', { count: v.views })}
          </p>
        </div>
      </Card>
    </Page>
  )
}
