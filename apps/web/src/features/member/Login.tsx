import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { useStore } from '@/state/store'
import { gym } from '@/mocks/data'
import type { Lang } from '@/i18n'

/**
 * Phone + code, no email: most gym members here do not use email, and a password is one
 * more thing to forget at the door. Phase 4 wires this to a real OTP over WhatsApp.
 */
export function MemberLogin() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const navigate = useNavigate()
  const { actions } = useStore()

  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(false)

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
          <h1 className="mt-4 text-2xl font-extrabold text-white">{gym.name[lang]}</h1>
          <p className="mt-1 text-sm text-white/60">{t('login.sub')}</p>
        </div>

        <Card className="space-y-4 p-4">
        <Field label={t('login.phone')}>
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            inputMode="tel"
            dir="ltr"
            placeholder="+961 70 000 000"
            autoFocus
          />
        </Field>

        {!sent ? (
          <Button
            variant="brand"
            full
            size="lg"
            disabled={phone.trim().length < 6}
            onClick={() => setSent(true)}
          >
            {t('login.sendCode')}
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
                placeholder="1234"
                autoFocus
              />
            </Field>
            <Button
              variant="brand"
              full
              size="lg"
              disabled={code.trim().length < 4}
              onClick={() => {
                actions.signIn()
                navigate('/member')
              }}
            >
              {t('login.enter')}
            </Button>
            <p className="text-muted text-center text-xs">{t('login.demo')}</p>
          </>
        )}
        </Card>
      </div>
    </div>
  )
}
