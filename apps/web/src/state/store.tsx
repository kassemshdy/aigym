import { createContext, useContext, useMemo, useReducer, type ReactNode } from 'react'
import { replyTo } from '@/mocks/agents'
import type { AgentId, ChatMessage, FoodEntry, ProgressPhoto } from '@/mocks/types'
import type { Lang } from '@/i18n'

/**
 * Prototype state. Phase 2 replaces this with the API plus the offline outbox
 * (see .agents/skills/offline-sync); components keep the same shape either way,
 * which is why they read through this hook rather than touching mocks directly.
 */

interface State {
  signedIn: boolean
  food: FoodEntry[]
  photos: ProgressPhoto[]
  chats: Record<AgentId, ChatMessage[]>
  /** Suggestions the agents escalated to the coach instead of acting on. */
  draftsSent: number
}

type Action =
  | { type: 'signIn' }
  | { type: 'signOut' }
  | { type: 'addFood'; entry: FoodEntry }
  | { type: 'removeFood'; id: string }
  | { type: 'addPhoto'; photo: ProgressPhoto }
  | { type: 'setPhotoShared'; id: string; shared: boolean }
  | { type: 'removePhoto'; id: string }
  | { type: 'chat'; agent: AgentId; messages: ChatMessage[]; draft?: boolean }

const now = () =>
  new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

const id = () => Math.random().toString(36).slice(2, 10)

const SIGNED_IN_KEY = 'aigym.signedIn'

const initial: State = {
  signedIn: (() => {
    try {
      return localStorage.getItem(SIGNED_IN_KEY) === '1'
    } catch {
      return false
    }
  })(),
  food: [
    { id: 'f1', at: '08:20', label: 'بيض مع خبز', kcal: 340, protein: 22, carbs: 34, fat: 12, source: 'manual' },
  ],
  photos: [],
  chats: { nutrition: [], training: [] },
  draftsSent: 0,
}

function persistSignedIn(value: boolean) {
  try {
    if (value) localStorage.setItem(SIGNED_IN_KEY, '1')
    else localStorage.removeItem(SIGNED_IN_KEY)
  } catch {
    /* private mode — the session just won't survive a reload */
  }
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'signIn':
      persistSignedIn(true)
      return { ...state, signedIn: true }
    case 'signOut':
      persistSignedIn(false)
      return { ...state, signedIn: false }
    case 'addFood':
      return { ...state, food: [...state.food, action.entry] }
    case 'removeFood':
      return { ...state, food: state.food.filter((f) => f.id !== action.id) }
    case 'addPhoto':
      return { ...state, photos: [action.photo, ...state.photos] }
    case 'setPhotoShared':
      return {
        ...state,
        photos: state.photos.map((p) =>
          p.id === action.id ? { ...p, sharedWithCoach: action.shared } : p,
        ),
      }
    case 'removePhoto':
      return { ...state, photos: state.photos.filter((p) => p.id !== action.id) }
    case 'chat':
      return {
        ...state,
        chats: { ...state.chats, [action.agent]: [...state.chats[action.agent], ...action.messages] },
        draftsSent: state.draftsSent + (action.draft ? 1 : 0),
      }
  }
}

const Ctx = createContext<{ state: State; actions: ReturnType<typeof makeActions> } | null>(null)

function makeActions(dispatch: (a: Action) => void) {
  return {
    signIn: () => dispatch({ type: 'signIn' }),
    signOut: () => dispatch({ type: 'signOut' }),

    logFood: (entry: Omit<FoodEntry, 'id' | 'at'>) =>
      dispatch({ type: 'addFood', entry: { ...entry, id: id(), at: now() } }),

    removeFood: (foodId: string) => dispatch({ type: 'removeFood', id: foodId }),

    addPhoto: (url: string) =>
      dispatch({
        type: 'addPhoto',
        // Private by default. Sharing is always a separate, deliberate act.
        photo: { id: id(), at: new Date().toISOString(), url, sharedWithCoach: false },
      }),

    setPhotoShared: (photoId: string, shared: boolean) =>
      dispatch({ type: 'setPhotoShared', id: photoId, shared }),

    removePhoto: (photoId: string) => dispatch({ type: 'removePhoto', id: photoId }),

    /** Sends a message and applies whatever the agent is allowed to do with it. */
    ask: (agent: AgentId, text: string, lang: Lang) => {
      const reply = replyTo(agent, text, lang)
      const messages: ChatMessage[] = [
        { id: id(), role: 'member', text, at: now() },
        {
          id: id(),
          role: 'agent',
          text: reply.body,
          at: now(),
          note: reply.draft ? 'draft_sent' : reply.food ? 'food_logged' : undefined,
        },
      ]
      dispatch({ type: 'chat', agent, messages, draft: reply.draft })
      if (reply.food) {
        dispatch({
          type: 'addFood',
          entry: { ...reply.food, id: id(), at: now(), source: 'agent' },
        })
      }
    },
  }
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial)
  const value = useMemo(() => ({ state, actions: makeActions(dispatch) }), [state])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStore() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useStore must be used inside StoreProvider')
  return ctx
}
