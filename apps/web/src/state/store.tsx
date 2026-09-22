import { createContext, useContext, useMemo, useReducer, type ReactNode } from 'react'
import { sendChatMessage } from '@/data/queries'
import type { ChatTurnInput } from '@/data/types'
import type { AgentId, ChatMessage, FoodEntry, SupplementId } from '@/mocks/types'
import type { Lang } from '@/i18n'

/**
 * Prototype state. Phase 2 replaces this with the API plus the offline outbox
 * (see .agents/skills/offline-sync); components keep the same shape either way,
 * which is why they read through this hook rather than touching mocks directly.
 */

interface State {
  food: FoodEntry[]
  chats: Record<AgentId, ChatMessage[]>
  /** Suggestions the agents escalated to the coach instead of acting on. */
  draftsSent: number
  /** Glasses of water today — tapped, never typed. */
  water: number
  supplements: SupplementId[]
}

type Action =
  | { type: 'addFood'; entry: FoodEntry }
  | { type: 'removeFood'; id: string }
  | { type: 'chat'; agent: AgentId; messages: ChatMessage[]; draft?: boolean }
  | { type: 'water'; delta: number }
  | { type: 'supplement'; id: SupplementId }

const now = () =>
  new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

const id = () => Math.random().toString(36).slice(2, 10)

const initial: State = {
  food: [
    { id: 'f1', at: '08:20', label: { ar: 'بيض مع خبز', en: 'Eggs with bread' }, kcal: 340, protein: 22, carbs: 34, fat: 12, source: 'manual' },
  ],
  chats: { nutrition: [], training: [] },
  draftsSent: 0,
  water: 3,
  supplements: ['protein'],
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'addFood':
      return { ...state, food: [...state.food, action.entry] }
    case 'removeFood':
      return { ...state, food: state.food.filter((f) => f.id !== action.id) }
    case 'chat':
      return {
        ...state,
        chats: { ...state.chats, [action.agent]: [...state.chats[action.agent], ...action.messages] },
        draftsSent: state.draftsSent + (action.draft ? 1 : 0),
      }
    case 'water':
      return { ...state, water: Math.max(0, state.water + action.delta) }
    case 'supplement':
      return {
        ...state,
        supplements: state.supplements.includes(action.id)
          ? state.supplements.filter((x) => x !== action.id)
          : [...state.supplements, action.id],
      }
  }
}

const Ctx = createContext<{ state: State; actions: ReturnType<typeof makeActions> } | null>(null)

function makeActions(dispatch: (a: Action) => void, chats: Record<AgentId, ChatMessage[]>) {
  return {
    logFood: (entry: Omit<FoodEntry, 'id' | 'at'>) =>
      dispatch({ type: 'addFood', entry: { ...entry, id: id(), at: now() } }),

    removeFood: (foodId: string) => dispatch({ type: 'removeFood', id: foodId }),

    addWater: (delta: number) => dispatch({ type: 'water', delta }),

    toggleSupplement: (supplementId: SupplementId) =>
      dispatch({ type: 'supplement', id: supplementId }),

    /** Sends a message and applies whatever the agent is allowed to do with
     * it. The network call (data/queries.ts's sendChatMessage — the only
     * place `fetch` reaches Claude) is the one async step; the transcript
     * itself stays in this store, same as before Phase 5 stage 7. */
    ask: async (agent: AgentId, text: string, lang: Lang) => {
      const history: ChatTurnInput[] = chats[agent].map((m) => ({
        role: m.role === 'member' ? 'user' : 'assistant',
        text: m.text,
      }))
      const reply = await sendChatMessage(agent, text, history, lang)
      const messages: ChatMessage[] = [
        { id: id(), role: 'member', text, at: now() },
        {
          id: id(),
          role: 'agent',
          text: reply.text,
          at: now(),
          note: reply.referred
            ? 'referred'
            : reply.draft
              ? 'draft_sent'
              : reply.food
                ? 'food_logged'
                : undefined,
        },
      ]
      dispatch({ type: 'chat', agent, messages, draft: reply.draft })
      if (reply.food) {
        dispatch({
          type: 'addFood',
          entry: {
            id: id(), at: now(), source: 'agent',
            label: { ar: reply.food.label, en: reply.food.label },
            kcal: reply.food.kcal, protein: reply.food.protein,
            carbs: reply.food.carbs, fat: reply.food.fat,
          },
        })
      }
    },
  }
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial)
  const value = useMemo(
    () => ({ state, actions: makeActions(dispatch, state.chats) }),
    [state],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStore() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useStore must be used inside StoreProvider')
  return ctx
}
