import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/Card'
import { BackLink } from '@/components/ui/BackLink'
import { Button } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Page } from '@/components/ui/Page'
import { AGENTS, SUGGESTIONS } from '@/mocks/agents'
import type { AgentId } from '@/mocks/types'
import { useStore } from '@/state/store'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'

const IDS: AgentId[] = ['nutrition', 'training']

export function MemberChatPicker() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const { state } = useStore()

  return (
    <Page title={t('chat.title')} sub={t('chat.pick')}>
      {IDS.map((id) => (
        <Link key={id} to={`/member/chat/${id}`}>
          <Card className="flex items-center gap-4 p-4">
            <span className="bg-ink flex size-12 shrink-0 items-center justify-center rounded-full text-white">
              <Icon name={id === 'nutrition' ? 'spark' : 'dumbbell'} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-bold">{AGENTS[id].name[lang]}</span>
              <span className="text-muted block text-sm">{AGENTS[id].blurb[lang]}</span>
            </span>
            <span className="text-muted tnum text-xs">
              {state.chats[id].length ? state.chats[id].length : ''}
            </span>
          </Card>
        </Link>
      ))}

      <p className="bg-soon-bg text-soon rounded-xl px-4 py-3 text-sm font-semibold">
        {t('chat.disclaimer')}
      </p>
    </Page>
  )
}

export function MemberChat() {
  const { agent } = useParams()
  const id = (IDS.includes(agent as AgentId) ? agent : 'nutrition') as AgentId
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const { state, actions } = useStore()
  const [text, setText] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  const messages = state.chats[id]

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length])

  const send = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return
    actions.ask(id, trimmed, lang)
    setText('')
  }

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex-1 space-y-4 p-4">
        <BackLink to="/member/chat" />

        <div className="flex items-center gap-3">
          <span className="bg-ink flex size-11 shrink-0 items-center justify-center rounded-full text-white">
            <Icon name={id === 'nutrition' ? 'spark' : 'dumbbell'} />
          </span>
          <div>
            <h1 className="font-extrabold">{AGENTS[id].name[lang]}</h1>
            <p className="text-muted text-xs">{AGENTS[id].blurb[lang]}</p>
          </div>
        </div>

        {messages.length === 0 ? (
          <div className="space-y-2">
            <p className="text-muted text-sm font-semibold">{t('chat.suggestions')}</p>
            {SUGGESTIONS[id].map((s) => (
              <button
                key={s.en}
                type="button"
                onClick={() => send(s[lang])}
                className="border-line bg-surface min-h-tap w-full rounded-xl border px-4 text-start text-sm font-semibold"
              >
                {s[lang]}
              </button>
            ))}
          </div>
        ) : null}

        <div className="space-y-3">
          {messages.map((m) => (
            <div
              key={m.id}
              className={cn('flex', m.role === 'member' ? 'justify-end' : 'justify-start')}
            >
              <div
                className={cn(
                  'max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
                  m.role === 'member' ? 'bg-ink text-white' : 'bg-surface border-line border',
                )}
              >
                <p>{m.text}</p>
                {m.note ? (
                  <p
                    className={cn(
                      'mt-2 flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-bold',
                      m.note === 'draft_sent' ? 'bg-soon-bg text-soon' : 'bg-paid-bg text-paid',
                    )}
                  >
                    <Icon name="check" size={14} />
                    {t(m.note === 'draft_sent' ? 'chat.draftSent' : 'chat.foodLogged')}
                  </p>
                ) : null}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </div>

      <div className="bg-surface border-line sticky bottom-[var(--nav-total)] border-t p-3">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            send(text)
          }}
        >
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t('chat.placeholder')}
            className="border-line bg-canvas min-h-tap flex-1 rounded-xl border px-4 text-base outline-none focus:border-ink"
          />
          <Button type="submit" disabled={!text.trim()}>
            {t('chat.send')}
          </Button>
        </form>
      </div>
    </div>
  )
}
