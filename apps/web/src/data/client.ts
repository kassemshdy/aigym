import type { TokenPair } from './types'

/** Unset ⇒ the whole data layer falls back to mocks (see queries.ts). This
 * is the only place `fetch` appears, per apps/web/AGENTS.md's Phase 2
 * boundary — feature components import from queries.ts, never from here. */
export const API_URL = import.meta.env.VITE_API_URL

const ACCESS_TOKEN_KEY = 'aigym.staff.accessToken'
const REFRESH_TOKEN_KEY = 'aigym.staff.refreshToken'

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* private mode — the session just won't survive a reload */
  }
}

export function getAccessToken() {
  return readStorage(ACCESS_TOKEN_KEY)
}

function getRefreshToken() {
  return readStorage(REFRESH_TOKEN_KEY)
}

export function setTokens(tokens: TokenPair) {
  writeStorage(ACCESS_TOKEN_KEY, tokens.access_token)
  writeStorage(REFRESH_TOKEN_KEY, tokens.refresh_token)
}

export function clearTokens() {
  writeStorage(ACCESS_TOKEN_KEY, null)
  writeStorage(REFRESH_TOKEN_KEY, null)
}

export function isStaffSignedIn() {
  return getAccessToken() !== null
}

/** Decodes the access token's `role` claim client-side, without verifying
 * the signature — used only to pick which surface to land on after login
 * (coach vs. manager/super_admin). The server re-checks the real,
 * signature-verified role on every request via require_role(); this is UX
 * routing, not a security boundary. */
export function getStaffRole(): string | null {
  const token = getAccessToken()
  if (!token) return null
  try {
    const payload = token.split('.')[1]
    const decoded: unknown = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
    return decoded && typeof decoded === 'object' && 'role' in decoded
      ? String((decoded as { role: unknown }).role)
      : null
  } catch {
    return null
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function refreshTokens(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!response.ok) {
    clearTokens()
    return false
  }
  setTokens((await response.json()) as TokenPair)
  return true
}

interface FetchOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Required for POST/PATCH/DELETE — the middleware rejects mutations without one. */
  idempotencyKey?: string
}

/**
 * The one function that calls `fetch`. Attaches the manager's bearer token
 * when present, retries once after a silent refresh on 401, and surfaces
 * failures as ApiError so callers can show a real message instead of a
 * blank screen.
 */
export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  if (!API_URL) {
    throw new Error('apiFetch called without VITE_API_URL set — this should never happen')
  }

  const request = () => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
    if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey
    return fetch(`${API_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })
  }

  let response = await request()
  if (response.status === 401 && getRefreshToken() && (await refreshTokens())) {
    response = await request()
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : response.statusText
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function newIdempotencyKey() {
  return crypto.randomUUID()
}
