import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { Button, buttonClass } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Field, Input, Row, Segmented } from '@/components/ui/Field'
import { Sparkline } from '@/components/ui/Sparkline'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import {
  getMember,
  listPayments,
  recordPayment,
  setMemberStatus,
  updateMember,
  whatsappReminderLink,
} from '@/data/queries'
import { normalizePhone } from '@/lib/phone'
import { useAsync } from '@/data/useAsync'
import { listSep, shortDate, usd } from '@/lib/format'
import type { Lang } from '@/i18n'
import { SharedPhotos } from '@/features/photos/SharedPhotos'

export function ManagerMemberDetail() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang

  const member = useAsync(() => getMember(id), [id])
  const payments = useAsync(listPayments, [id])

  const [recording, setRecording] = useState(false)
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState<'cash' | 'transfer'>('cash')
  const [saving, setSaving] = useState(false)
  const [confirmingLeave, setConfirmingLeave] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draftName, setDraftName] = useState('')
  const [draftNameEn, setDraftNameEn] = useState('')
  const [draftPhone, setDraftPhone] = useState('')
  const leaveCard = useRef<HTMLDivElement>(null)
  // The confirm grows downward off the bottom of a long page, so the
  // buttons it asks about would otherwise open where nobody can see
  // them. Hooks run before the early returns below on purpose.
  useEffect(() => {
    if (confirmingLeave) leaveCard.current?.scrollIntoView({ block: 'end' })
  }, [confirmingLeave])

  if (member.loading) return <Page><Empty>{t('common.loading')}</Empty></Page>
  if (member.error || !member.data) return <Page><Empty>{t('common.none')}</Empty></Page>

  const m = member.data
  const name = lang === 'ar' ? m.name : m.name_en

  async function openWhatsapp() {
    const { wa_link } = await whatsappReminderLink(id, lang)
    window.open(wa_link, '_blank', 'noreferrer')
  }

  async function submitPayment() {
    const amountUsd = Number(amount)
    if (!amountUsd || amountUsd <= 0) return
    setSaving(true)
    try {
      await recordPayment(id, { amount_usd: amountUsd, method })
      setRecording(false)
      setAmount('')
      member.reload()
      payments.reload()
    } finally {
      setSaving(false)
    }
  }

  const memberPayments = (payments.data ?? []).filter((p) => p.member_id === id)
  const hasLeft = m.status === 'left'

  // A member added in the app has one name, stored twice (AddMember sends
  // it as both). One imported from a notebook can have distinct Arabic and
  // English names. Editing one field for the first kind keeps them equal;
  // the second kind gets both fields, so neither overwrites the other.
  const splitName = m.name !== m.name_en
  const draftPhoneNormalized = normalizePhone(draftPhone)
  const nameChanged = draftName.trim() !== m.name
  const nameEnChanged = splitName && draftNameEn.trim() !== m.name_en
  const phoneChanged = draftPhoneNormalized !== null && draftPhoneNormalized !== m.phone
  const editValid =
    draftName.trim() !== '' &&
    (!splitName || draftNameEn.trim() !== '') &&
    draftPhoneNormalized !== null

  function startEditing() {
    setRecording(false)
    setDraftName(m.name)
    setDraftNameEn(m.name_en)
    setDraftPhone(m.phone)
    setEditing(true)
  }

  async function saveDetails() {
    setSaving(true)
    try {
      await updateMember(id, {
        ...(nameChanged
          ? splitName
            ? { name: draftName.trim() }
            : { name: draftName.trim(), name_en: draftName.trim() }
          : {}),
        ...(nameEnChanged ? { name_en: draftNameEn.trim() } : {}),
        ...(phoneChanged ? { phone: draftPhone } : {}),
      })
      setEditing(false)
      member.reload()
    } finally {
      setSaving(false)
    }
  }

  async function changeStatus(next: 'active' | 'left') {
    setSaving(true)
    try {
      await setMemberStatus(id, next)
      setConfirmingLeave(false)
      member.reload()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Page>
      <BackLink to="/manager/members" />

      <Card className="p-4">
        <div className="flex items-center gap-3">
          <Avatar name={name} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-extrabold">{name}</h1>
            <p className="text-muted tnum text-sm" dir="ltr">{m.phone}</p>
            {hasLeft && m.left_at ? (
              // Not a StatusBadge: green/amber/red are payment state and
              // nothing else, and this is not about money. Decision 43.
              <p className="mt-0.5 text-sm font-bold">
                {t('manager.member.leftOn', { date: shortDate(m.left_at, lang) })}
              </p>
            ) : null}
          </div>
          {m.dues ? <StatusBadge status={m.dues.status} big /> : null}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => void openWhatsapp()}
            className={buttonClass('secondary', 'lg')}
          >
            <Icon name="whatsapp" />
            {t('manager.member.whatsapp')}
          </button>
          <button
            type="button"
            onClick={() => {
              setEditing(false)
              setRecording((v) => !v)
            }}
            className={buttonClass('primary', 'lg')}
          >
            <Icon name="money" />
            {t('manager.member.recordPayment')}
          </button>
          <button
            type="button"
            onClick={() => (editing ? setEditing(false) : startEditing())}
            className={buttonClass('secondary', 'lg')}
          >
            <Icon name="user" />
            {t('manager.member.edit')}
          </button>
          <Link to={`/manager/programs/${id}`} className={buttonClass('secondary', 'lg', true)}>
            <Icon name="dumbbell" />
            {t('manager.member.editPlan')}
          </Link>
        </div>

        {recording ? (
          <div className="border-line mt-4 space-y-3 border-t pt-4">
            <Field label={t('manager.member.amount')}>
              <Input
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                inputMode="decimal"
                dir="ltr"
                placeholder="35"
                autoFocus
              />
            </Field>
            <Field label={t('manager.payments.method')}>
              <Segmented
                value={method}
                onChange={setMethod}
                columns={2}
                options={[
                  { value: 'cash', label: t('manager.payments.cash') },
                  { value: 'transfer', label: t('manager.payments.transfer') },
                ]}
              />
            </Field>
            <Button
              full
              size="lg"
              disabled={saving || !Number(amount)}
              onClick={() => void submitPayment()}
            >
              {t('common.save')}
            </Button>
          </div>
        ) : null}

        {editing ? (
          <div className="border-line mt-4 space-y-3 border-t pt-4">
            <Field label={t('manager.add.name')}>
              <Input value={draftName} onChange={(e) => setDraftName(e.target.value)} autoFocus />
            </Field>
            {splitName ? (
              <Field label={t('manager.member.nameEn')}>
                <Input value={draftNameEn} onChange={(e) => setDraftNameEn(e.target.value)} />
              </Field>
            ) : null}
            <Field label={t('manager.add.phone')}>
              <Input
                value={draftPhone}
                onChange={(e) => setDraftPhone(e.target.value)}
                inputMode="tel"
                dir="ltr"
                placeholder="+961 70 000 000"
              />
            </Field>
            {draftPhone.trim() && draftPhoneNormalized === null ? (
              <p className="text-muted text-sm font-semibold">{t('common.phoneInvalid')}</p>
            ) : null}
            <div className="flex gap-2">
              <Button variant="secondary" size="lg" onClick={() => setEditing(false)}>
                {t('common.cancel')}
              </Button>
              <Button
                full
                size="lg"
                disabled={saving || !editValid || !(nameChanged || nameEnChanged || phoneChanged)}
                onClick={() => void saveDetails()}
              >
                {t('common.save')}
              </Button>
            </div>
          </div>
        ) : null}
      </Card>

      <Card>
        <Row label={t('manager.member.plan')} value={m.plan_name?.[lang]} />
        <Row label={t('manager.member.ends')} value={m.ends_at ? shortDate(m.ends_at, lang) : '—'} />
        <Row
          label={t('manager.member.owed')}
          value={
            <span className={m.dues && m.dues.owed_usd > 0 ? 'text-due tnum' : 'tnum'}>
              {usd(m.dues?.owed_usd ?? 0)}
            </span>
          }
        />
        <Row
          label={t('manager.member.lastVisit')}
          value={m.last_visit ? shortDate(m.last_visit, lang) : t('manager.member.never')}
        />
      </Card>

      {m.profile ? (
        <>
          <Card>
            <CardTitle>{t('manager.member.body')}</CardTitle>
            <Row label={t('manager.member.height')} value={`${m.profile.height_cm} cm`} />
            <Row label={t('manager.member.weight')} value={`${m.profile.weight_kg} ${t('common.kg')}`} />
            <Row label={t('manager.member.bodyFat')} value={m.profile.body_fat ? `${m.profile.body_fat}%` : '—'} />
            <Row
              label={t('manager.member.injuries')}
              value={
                m.profile.injuries.length
                  ? m.profile.injuries.map((i) => i.note[lang]).join(listSep(lang))
                  : t('manager.member.noInjuries')
              }
            />
            <div className="flex items-center justify-between gap-3 px-4 py-3">
              <span className="text-muted text-sm">{t('manager.member.weightHistory')}</span>
              <span className="text-ink"><Sparkline values={m.profile.weight_trend} /></span>
            </div>
          </Card>

          <Card>
            <CardTitle>{t('manager.member.lifestyle')}</CardTitle>
            <Row label={t('manager.add.goal')} value={t(`goal.${m.profile.goal}`)} />
            <Row label={t('manager.add.level')} value={t(`level.${m.profile.level}`)} />
            <Row label={t('manager.member.daysPerWeek')} value={m.profile.days_per_week} />
            <Row label={t('job.desk').split(' ')[0]} value={t(`job.${m.profile.job}`)} />
            <Row label={t('manager.member.sleep')} value={m.profile.sleep_hours} />
          </Card>
        </>
      ) : null}

      <Card>
        <CardTitle>{t('manager.payments.title')}</CardTitle>
        {memberPayments.length === 0 ? (
          <p className="text-muted p-4 text-sm">{t('common.none')}</p>
        ) : (
          memberPayments.map((p) => (
            <Row
              key={p.id}
              label={shortDate(p.at, lang)}
              value={`${usd(p.amount_usd)} · ${t(`manager.payments.${p.method}`)}`}
            />
          ))
        )}
      </Card>

      <SharedPhotos memberId={id} />

      {/* Last on the page on purpose: a manager scrolls past everything they
          normally came for before they can reach it. Decision 43. */}
      <div ref={leaveCard}>
        <Card className="p-4">
          {hasLeft ? (
            <Button full size="lg" disabled={saving} onClick={() => void changeStatus('active')}>
              {t('manager.member.bringBack')}
            </Button>
          ) : confirmingLeave ? (
            <div className="space-y-2">
              <p className="text-sm font-semibold">{t('manager.member.confirmLeft', { name })}</p>
              <p className="text-muted text-xs">{t('manager.member.leftNote')}</p>
              <div className="flex gap-2">
                <Button variant="secondary" size="lg" onClick={() => setConfirmingLeave(false)}>
                  {t('common.cancel')}
                </Button>
                {/* Black, not red: red means payment state in this product
                    and nothing else. The sentence above carries the weight. */}
                <Button full size="lg" disabled={saving} onClick={() => void changeStatus('left')}>
                  {t('manager.member.markLeft')}
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="secondary" full size="lg" onClick={() => setConfirmingLeave(true)}>
              {t('manager.member.markLeft')}
            </Button>
          )}
        </Card>
      </div>
    </Page>
  )
}
