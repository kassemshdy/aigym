import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { gym } from '@/mocks/data'
import { requestStaffPasswordReset, staffLogin } from '@/data/queries'
import { ApiError } from '@/data/client'
import type { Lang } from '@/i18n'

type ResetState = 'idle' | 'sending' | 'sent' | 'notSent' | 'notFound' | 'rateLimited'

/** Only reachable when VITE_API_URL is set — with no API, /manager needs no
 * login at all (see RequireManager in App.tsx), exactly like Phase 1.
 * Username + password (decision 21) — not phone + PIN. */
export function ManagerLogin() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [resetState, setResetState] = useState<ResetState>('idle')

  async function submit() {
    setBusy(true)
    setError(false)
    try {
      await staffLogin(username, password)
      navigate('/manager')
    } catch (err) {
      setError(err instanceof ApiError ? err.status === 401 : true)
    } finally {
      setBusy(false)
    }
  }

  async function forgotPassword() {
    setResetState('sending')
    try {
      const result = await requestStaffPasswordReset(username)
      setResetState(result.sent ? 'sent' : 'notSent')
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setResetState('notFound')
      else if (err instanceof ApiError && err.status === 429) setResetState('rateLimited')
      else setResetState('notSent')
    }
  }

  const resetMessageKey: Partial<Record<ResetState, string>> = {
    sent: 'manager.login.resetSent',
    notSent: 'manager.login.resetNotSent',
    notFound: 'manager.login.resetNotFound',
    rateLimited: 'manager.login.resetRateLimited',
  }

  return (
    <div className="bg-chrome relative min-h-full overflow-hidden">
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
          <h1 className="mt-4 text-2xl font-extrabold text-white">{gym.name[lang]}</h1>
          <p className="mt-1 text-sm text-white/60">{t('manager.login.sub')}</p>
        </div>

        <Card className="space-y-4 p-4">
          <Field label={t('manager.login.username')}>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              dir="ltr"
              placeholder="kassem"
              autoFocus
            />
          </Field>
          <Field label={t('manager.login.password')}>
            <Input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              dir="ltr"
              placeholder="••••••••"
              type="password"
            />
          </Field>

          {error ? (
            // Not a payment state, so not due/soon/paid — those colors are
            // reserved. A neutral high-contrast banner instead.
            <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
              {t('manager.login.error')}
            </p>
          ) : null}

          <Button
            variant="brand"
            full
            size="lg"
            disabled={busy || username.trim().length < 2 || password.trim().length < 4}
            onClick={submit}
          >
            {t('manager.login.enter')}
          </Button>

          <Button
            variant="ghost"
            full
            disabled={resetState === 'sending' || username.trim().length < 2}
            onClick={forgotPassword}
          >
            {t('manager.login.forgotPassword')}
          </Button>

          {resetState !== 'idle' && resetState !== 'sending' ? (
            // Same neutral treatment as the sign-in error above — this is
            // account-recovery status, not a payment state.
            <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">
              {t(resetMessageKey[resetState] ?? 'manager.login.resetNotSent')}
            </p>
          ) : null}
        </Card>
      </div>
    </div>
  )
}
