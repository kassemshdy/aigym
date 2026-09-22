import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button, buttonClass } from '@/components/ui/Button'
import { Field, Input, Segmented } from '@/components/ui/Field'
import { Avatar } from '@/components/ui/Avatar'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import {
  createStaff,
  getStaffRole,
  listStaff,
  resetStaffPassword,
  revokeStaffAccess,
  updateStaffRole,
} from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { ApiError } from '@/data/client'
import { gym } from '@/mocks/data'
import { waLink } from '@/lib/whatsapp'
import type { ApiStaff, StaffRole } from '@/data/types'
import type { Lang } from '@/i18n'
import { HelpTip } from '@/help/HelpTip'

interface Credentials {
  name: string
  phone: string
  username: string
  password: string
}

/** Ordered most access first, which is also how the Segmented control
 * reads. Flat, not a hierarchy (app/deps.py's require_role). */
const ROLES: StaffRole[] = ['super_admin', 'manager', 'coach']

/** What the viewer is allowed to do, mirroring app/api/staff.py so the
 * screen never offers an action the server will refuse:
 *
 * - Only a super_admin changes roles. A manager promoting a coach would be
 *   handing out access they were never given authority to hand out, and
 *   demoting a peer is worse — so PATCH /staff/{id} is closed to them and
 *   the control is simply absent rather than disabled-with-an-error.
 * - A manager may remove or reset the password of a coach, nobody else.
 */
function canActOn(viewer: StaffRole, target: ApiStaff): boolean {
  return viewer === 'super_admin' || target.role === 'coach'
}

export function ManagerStaff() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const staff = useAsync(listStaff, [])

  // Mock mode has no login, so no token and no role. The prototype shows
  // the owner's view — it is the one that exercises every control, and a
  // demo that hid them would be showing a screen nobody ever sees.
  const viewer = (getStaffRole() ?? 'super_admin') as StaffRole

  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [newRole, setNewRole] = useState<StaffRole>('coach')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<'taken' | 'other' | null>(null)
  const [credentials, setCredentials] = useState<Credentials | null>(null)

  const [openId, setOpenId] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rowError, setRowError] = useState<string | null>(null)

  function resetForm() {
    setName('')
    setPhone('')
    setUsername('')
    setPassword('')
    setNewRole('coach')
  }

  function closeRow() {
    setOpenId(null)
    setConfirmingId(null)
    setRowError(null)
  }

  /** The three guards app/api/staff.py enforces, each with its own answer.
   * A generic "something went wrong" on the last-owner rule would leave a
   * gym owner tapping the same control forever. */
  function explain(err: unknown): string {
    if (err instanceof ApiError && err.status === 409) return t('manager.staff.lastOwner')
    if (err instanceof ApiError && err.status === 403) return t('manager.staff.notAllowed')
    return t('common.error')
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setRowError(null)
    try {
      await action()
      staff.reload()
    } catch (err) {
      setRowError(explain(err))
    } finally {
      setBusy(false)
    }
  }

  async function submit() {
    setSaving(true)
    setError(null)
    try {
      await createStaff({
        username,
        password,
        name,
        phone,
        // A manager may only ever create a coach; the picker above is only
        // rendered for a super_admin, and the server checks it again.
        role: viewer === 'super_admin' ? newRole : 'coach',
      })
      setCredentials({ name, phone, username, password })
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
            {staff.data.map((s) => {
              const open = openId === s.id
              const actionable = canActOn(viewer, s)
              return (
                <li key={s.id} className="border-line border-b last:border-0">
                  <button
                    type="button"
                    disabled={!actionable}
                    onClick={() => (open ? closeRow() : (closeRow(), setOpenId(s.id)))}
                    aria-expanded={open}
                    className="min-h-tap flex w-full items-center gap-3 px-4 py-3 text-start disabled:opacity-100"
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
                    {actionable ? (
                      <span className={open ? 'rotate-90' : 'rtl:rotate-180'}>
                        <Icon name="chevron" size={18} />
                      </span>
                    ) : null}
                  </button>

                  {open ? (
                    <div className="bg-canvas space-y-4 px-4 py-4">
                      {viewer === 'super_admin' ? (
                        <div>
                          <p className="text-muted mb-1.5 text-sm font-semibold">
                            {t('manager.staff.role')}
                          </p>
                          <Segmented
                            value={s.role as StaffRole}
                            columns={3}
                            options={ROLES.map((r) => ({ value: r, label: t(`role.${r}`) }))}
                            onChange={(role) => {
                              if (role === s.role) return
                              void run(async () => {
                                await updateStaffRole(s.id, role)
                              })
                            }}
                          />
                          {/* Not a detail to hide: the server revokes their
                              refresh tokens on a role change, so whoever is
                              holding that phone gets signed out. */}
                          <p className="text-muted mt-1.5 text-xs">
                            {t('manager.staff.roleSignsOut')}
                          </p>
                        </div>
                      ) : null}

                      {confirmingId === s.id ? (
                        <div className="space-y-2">
                          <p className="text-sm font-semibold">
                            {t('manager.staff.confirmRemove', { name: s.name })}
                          </p>
                          <p className="text-muted text-xs">{t('manager.staff.removeNote')}</p>
                          <div className="flex gap-2">
                            <Button variant="secondary" onClick={() => setConfirmingId(null)}>
                              {t('common.cancel')}
                            </Button>
                            {/* Black, not the `danger` red: red means payment
                                state in this product and nothing else. The
                                sentence above carries the weight instead. */}
                            <Button
                              full
                              disabled={busy}
                              onClick={() =>
                                void run(async () => {
                                  await revokeStaffAccess(s.id)
                                  closeRow()
                                })
                              }
                            >
                              {t('manager.staff.remove')}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 gap-2">
                          <Button
                            variant="secondary"
                            disabled={busy}
                            onClick={() =>
                              void run(async () => {
                                const fresh = await resetStaffPassword(s.id)
                                setCredentials({
                                  name: s.name,
                                  phone: fresh.phone,
                                  username: fresh.username,
                                  password: fresh.password,
                                })
                                closeRow()
                              })
                            }
                          >
                            <Icon name="lock" size={16} />
                            {t('manager.staff.resetPassword')}
                          </Button>
                          <Button
                            variant="secondary"
                            disabled={busy}
                            onClick={() => setConfirmingId(s.id)}
                          >
                            {t('manager.staff.remove')}
                          </Button>
                        </div>
                      )}

                      {rowError ? (
                        <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
                          {rowError}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      {credentials ? (
        <Card className="space-y-3 p-6 text-center">
          <span className="bg-paid-bg text-paid mx-auto flex size-12 items-center justify-center rounded-full">
            <Icon name="check" size={24} />
          </span>
          <p className="font-bold">{t('manager.staff.created')}</p>
          <p className="text-muted text-sm">{credentials.name}</p>
          {/* The password is shown here because this is the only time it
              exists in the clear — it is hashed the moment it is stored. */}
          <p className="tnum bg-canvas rounded-xl px-4 py-3 font-bold" dir="ltr">
            {credentials.password}
          </p>
          <a
            href={waLink(
              credentials.phone,
              t('whatsapp.staffCredentials', {
                name: credentials.name,
                gym: gym.name[lang],
                username: credentials.username,
                password: credentials.password,
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
          <Button variant="ghost" full onClick={() => setCredentials(null)}>
            {t('common.done')}
          </Button>
        </Card>
      ) : adding ? (
        <Card className="space-y-4 p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-muted text-sm font-semibold">{t('manager.staff.addSomeone')}</p>
            {viewer === 'super_admin' ? null : <HelpTip text={t('help.staffCoachOnly')} />}
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
          {viewer === 'super_admin' ? (
            <div>
              <p className="text-muted mb-1.5 text-sm font-semibold">
                {t('manager.staff.role')}
              </p>
              <Segmented
                value={newRole}
                columns={3}
                options={ROLES.map((r) => ({ value: r, label: t(`role.${r}`) }))}
                onChange={setNewRole}
              />
            </div>
          ) : null}
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
                saving ||
                !name.trim() ||
                !phone.trim() ||
                !username.trim() ||
                password.trim().length < 4
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
          {viewer === 'super_admin' ? t('manager.staff.addSomeone') : t('manager.staff.addCoach')}
        </Button>
      )}
    </Page>
  )
}
