import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button, buttonClass } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { createStaff, listStaff } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { ApiError } from '@/data/client'
import { gym } from '@/mocks/data'
import { waLink } from '@/lib/whatsapp'
import type { Lang } from '@/i18n'
import { HelpTip } from '@/help/HelpTip'

interface JustCreated {
  name: string
  phone: string
  username: string
  password: string
}

/** Coaches the manager has added. A manager may only create role "coach"
 * here (the server enforces it — see decision 21's amendment); creating
 * another manager or a super_admin stays a super_admin-only action with
 * no UI yet. After creation, a wa.me link pre-fills the new login for the
 * manager to send by hand — same pattern as the member welcome message
 * (decision 4): no WhatsApp Business API, a human taps send. */
export function ManagerStaff() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const staff = useAsync(listStaff, [])

  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<'taken' | 'other' | null>(null)
  const [justCreated, setJustCreated] = useState<JustCreated | null>(null)

  function resetForm() {
    setName('')
    setPhone('')
    setUsername('')
    setPassword('')
  }

  async function submit() {
    setSaving(true)
    setError(null)
    try {
      await createStaff({ username, password, name, phone, role: 'coach' })
      setJustCreated({ name, phone, username, password })
      setAdding(false)
      resetForm()
      staff.reload()
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? 'taken' : 'other')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Page title={t('manager.staff.title')} sub={t('manager.staff.sub')}>
      <Card>
        <CardTitle>{t('manager.staff.list')}</CardTitle>
        {staff.loading ? (
          <p className="text-muted p-4 text-sm">{t('common.loading')}</p>
        ) : staff.error || !staff.data ? (
          <div className="p-4">
            <Empty>{t('common.error')}</Empty>
          </div>
        ) : staff.data.length === 0 ? (
          <div className="p-4">
            <Empty>{t('common.none')}</Empty>
          </div>
        ) : (
          <ul>
            {staff.data.map((s) => (
              <li
                key={s.id}
                className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
              >
                <Avatar name={s.name} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{s.name}</span>
                  <span className="text-muted tnum block text-xs" dir="ltr">
                    @{s.username}
                  </span>
                </span>
                <span className="bg-canvas text-muted rounded-full px-2.5 py-1 text-xs font-semibold">
                  {t(`role.${s.role}`, s.role)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {justCreated ? (
        <Card className="space-y-3 p-6 text-center">
          <span className="bg-paid-bg text-paid mx-auto flex size-12 items-center justify-center rounded-full">
            <Icon name="check" size={24} />
          </span>
          <p className="font-bold">{t('manager.staff.created')}</p>
          <p className="text-muted text-sm">{justCreated.name}</p>
          <a
            href={waLink(
              justCreated.phone,
              t('whatsapp.staffCredentials', {
                name: justCreated.name,
                gym: gym.name[lang],
                username: justCreated.username,
                password: justCreated.password,
                link: `${window.location.origin}/staff/login`,
              }),
            )}
            target="_blank"
            rel="noreferrer"
            className={buttonClass('secondary', 'lg', true)}
          >
            <Icon name="whatsapp" />
            {t('manager.staff.sendCredentials')}
          </a>
          <Button variant="ghost" full onClick={() => setJustCreated(null)}>
            {t('common.done')}
          </Button>
        </Card>
      ) : adding ? (
        <Card className="space-y-4 p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-muted text-sm font-semibold">{t('manager.staff.addCoach')}</p>
            <HelpTip text={t('help.staffCoachOnly')} />
          </div>
          <Field label={t('manager.staff.name')}>
            <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
          <Field label={t('manager.staff.phone')}>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              inputMode="tel"
              dir="ltr"
              placeholder="+961 70 000 000"
            />
          </Field>
          <Field label={t('manager.login.username')}>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              dir="ltr"
              placeholder="karim"
            />
          </Field>
          <Field label={t('manager.staff.tempPassword')}>
            <Input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              dir="ltr"
              type="password"
            />
          </Field>
          {error ? (
            <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
              {error === 'taken' ? t('manager.staff.usernameTaken') : t('common.error')}
            </p>
          ) : null}
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="lg"
              onClick={() => {
                setAdding(false)
                setError(null)
                resetForm()
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button
              full
              size="lg"
              disabled={
                saving || !name.trim() || !phone.trim() || !username.trim() || password.trim().length < 4
              }
              onClick={() => void submit()}
            >
              {t('common.save')}
            </Button>
          </div>
        </Card>
      ) : (
        <Button variant="brand" full size="lg" onClick={() => setAdding(true)}>
          <Icon name="add" size={18} />
          {t('manager.staff.addCoach')}
        </Button>
      )}
    </Page>
  )
}
