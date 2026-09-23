import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { API_URL, isMemberSignedIn, isStaffSignedIn } from '@/data/client'
import { getGym } from '@/data/queries'
import type { ApiGym } from '@/data/types'

interface GymState {
  gym: ApiGym | null
  reload: () => void
}

const GymContext = createContext<GymState>({ gym: null, reload: () => {} })

/**
 * The gym's own name and logo, fetched once and shared by every screen —
 * mirrors OfflineProvider's shape. Before this, `gym` was a const in
 * `src/mocks/data` read directly by nine files, which meant a
 * multi-tenant product hard-coded to one tenant's name.
 *
 * **Nothing here is fetched while signed out, because it cannot be.**
 * GET /gyms/me answers for the gym in the caller's token, and on a login
 * screen there is no token — the app genuinely does not know which gym it
 * is talking to yet. That is why the login screens show the product's
 * identity rather than a gym's (see Login.tsx).
 *
 * Refetch is driven by route changes rather than by Login calling in:
 * signing in navigates, and the first navigation after that is when a
 * token exists. Cheap, because it stops as soon as there is a gym.
 */
export function GymProvider({ children }: { children: React.ReactNode }) {
  const [gym, setGym] = useState<ApiGym | null>(null)
  const { pathname } = useLocation()

  const load = useCallback(() => {
    // Mock mode has no login at all, so the seed is always available.
    const signedInAs = isMemberSignedIn() ? 'member' : isStaffSignedIn() ? 'staff' : null
    if (API_URL && signedInAs === null) return
    void getGym(signedInAs ?? 'staff')
      .then(setGym)
      .catch(() => {
        /* Signed out, or the gym is unreachable. Every consumer falls back
           to the bundled logo and an empty name rather than blocking a
           screen on branding. */
      })
  }, [])

  useEffect(() => {
    if (gym) return
    load()
  }, [gym, load, pathname])

  // The static <title> in index.html is the product name, since a tenant's
  // name cannot be known before the app boots. This replaces it once it is.
  useEffect(() => {
    if (!gym) return
    const name = gym.name.en || gym.name.ar
    if (name) document.title = name
  }, [gym])

  return (
    <GymContext.Provider value={{ gym, reload: load }}>
      {children}
    </GymContext.Provider>
  )
}

export function useGym(): GymState {
  return useContext(GymContext)
}

/**
 * The gym's name in the current language, or `''` while it is still
 * loading or the caller is signed out. Empty rather than a placeholder
 * name on purpose: a WhatsApp message that says "your subscription at
 * Loading… has ended" is worse than one that just omits it.
 */
export function useGymName(lang: 'ar' | 'en'): string {
  const { gym } = useGym()
  if (!gym) return ''
  return gym.name[lang] || gym.name.en || gym.name.ar || ''
}
