import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { memberLogin, requestMemberCode } from '@/data/queries'
import { API_URL, ApiError } from '@/data/client'
import { normalizePhone } from '@/lib/phone'

/**
 * Phone + code, no email: most gym members here do not use email, and a password is one
 * more thing to forget at the door (decision 13). With no API configured, mock mode keeps
 * the old tap-through demo behavior — RequireMember in App.tsx doesn't gate on API_URL
 * being unset, same as staff.
 */
export function MemberLogin() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  // A link from the front desk carries the member's phone, and — when it
  // came with a code — `step=code`, so they land on the box they need.
  // The phone is theirs already; nothing secret ever goes in the URL.
  const [params] = useSearchParams()
  const [phone, setPhone] = useState(params.get('phone') ?? '')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(params.get('step') === 'code')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)

  async function sendCode() {
    setBusy(true)
    setError(false)
    try {
      await requestMemberCode(phone)
      setSent(true)
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  async function enter() {
    setBusy(true)
    setError(false)
    try {
      await memberLogin(phone, code)
      navigate('/member')
    } catch (err) {
      setError(err instanceof ApiError ? err.status === 401 : true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-chrome relative min-h-full overflow-hidden">
      {/* The angular yellow wedge is lifted straight from the gym's flyers. */}
      <div
        aria-hidden
        className="bg-brand/90 pointer-events-none absolute -top-24 end-[-30%] size-72 rotate-45"
      />
      <div className="relative mx-auto flex min-h-full max-w-md flex-col justify-center gap-4 p-4">
        <div className="text-center">
          <img
            src="/logo.png"
            alt=""
            width={96}
            height={96}
            className="mx-auto size-24 rounded-2xl"
          />
          <h1 className="mt-4 text-2xl font-extrabold text-white">{t('common.appName')}</h1>
          <p className="mt-1 text-sm text-white/60">{t('login.sub')}</p>
        </div>

        <Card className="space-y-4 p-4">
        <Field label={t('login.phone')}>
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            inputMode="tel"
            dir="ltr"
            autoFocus
          />
        </Field>
        {/* Without it a foreign number typed without its country code
            leaves a disabled button and no reason. Decision 49. */}
        {phone.replace(/[^\d]/g, '').length >= 7 && normalizePhone(phone) === null ? (
          <p className="text-muted text-sm font-semibold">{t('common.phoneInvalid')}</p>
        ) : null}

        {error ? (
          <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
            {t(sent ? 'login.errorCode' : 'login.error')}
          </p>
        ) : null}

        {!sent ? (
          <Button
            variant="brand"
            full
            size="lg"
            /* A parseable phone number, not just six characters. The
               endpoint answers `sent: true` whatever it is given so it can't
               be used to test whether a number is a member's (decision 20),
               and that silence meant a typo produced the "check WhatsApp"
               screen and no message. Checking the shape here leaks nothing —
               it says nothing about who is a member. */
            disabled={busy || normalizePhone(phone) === null}
            onClick={() => void sendCode()}
          >
            {t('login.sendCode')}
          </Button>
        ) : null}
        {!sent ? (
          // For a code the front desk already sent: asking for another
          // would only add one to the hourly limit.
          <Button
            variant="ghost"
            full
            disabled={normalizePhone(phone) === null}
            onClick={() => setSent(true)}
          >
            {t('login.haveCode')}
          </Button>
        ) : (
          <>
            <p className="bg-paid-bg text-paid rounded-xl px-4 py-3 text-sm font-semibold">
              {t('login.codeSent')}
            </p>
            <Field label={t('login.code')}>
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                dir="ltr"
                // Six digits. This hint said 1234, and a four-digit code
                // is one that can never exist — it read as "wrong code".
                placeholder="123456"
                autoFocus
              />
            </Field>
            <Button
              variant="brand"
              full
              size="lg"
              disabled={busy || code.trim().length < 4}
              onClick={() => void enter()}
            >
              {t('login.enter')}
            </Button>
            {!API_URL ? (
              <p className="text-muted text-center text-xs">{t('login.demo')}</p>
            ) : null}
          </>
        )}
        </Card>
      </div>
    </div>
  )
}
