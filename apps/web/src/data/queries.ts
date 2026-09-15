/**
 * The only functions manager feature components call for data — never
 * `fetch` directly (client.ts is the one place that lives), and never
 * `@/mocks/data` directly. Each function checks API_URL once and either
 * calls the live API or the mock adapter; the shape returned is identical
 * either way (src/data/types.ts).
 */
import { API_URL, apiFetch, newIdempotencyKey, setTokens } from './client'
import {
  mockCreateMember,
  mockGetMember,
  mockLapsedMembers,
  mockListMembers,
  mockListPayments,
  mockListPlans,
  mockListTodaysCheckIns,
  mockRecordPayment,
  mockWhatsappReminder,
} from './mockAdapter'
import type {
  ApiCheckIn,
  ApiLapsedMember,
  ApiMember,
  ApiMemberDetail,
  ApiPayment,
  ApiPlan,
  CreateMemberInput,
  RecordPaymentInput,
  StaffPinResetResult,
  TokenPair,
} from './types'

export async function listMembers(): Promise<ApiMember[]> {
  if (!API_URL) return mockListMembers()
  return apiFetch('/members')
}

export async function getMember(memberId: string): Promise<ApiMemberDetail> {
  if (!API_URL) return mockGetMember(memberId)
  return apiFetch(`/members/${memberId}`)
}

export async function listPlans(): Promise<ApiPlan[]> {
  if (!API_URL) return mockListPlans()
  return apiFetch('/plans')
}

export async function listTodaysCheckIns(): Promise<ApiCheckIn[]> {
  if (!API_URL) return mockListTodaysCheckIns()
  return apiFetch('/check-ins/today')
}

export async function listLapsedMembers(minDays = 14): Promise<ApiLapsedMember[]> {
  if (!API_URL) return mockLapsedMembers(minDays)
  return apiFetch(`/members/lapsed?min_days=${minDays}`)
}

export async function createMember(input: CreateMemberInput): Promise<ApiMemberDetail> {
  if (!API_URL) return mockCreateMember(input)
  return apiFetch('/members', {
    method: 'POST',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function recordPayment(
  memberId: string,
  input: RecordPaymentInput,
): Promise<ApiMemberDetail> {
  if (!API_URL) return mockRecordPayment(memberId, input)
  return apiFetch(`/members/${memberId}/payments`, {
    method: 'POST',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function whatsappReminderLink(
  memberId: string,
  lang: 'ar' | 'en',
): Promise<{ wa_link: string }> {
  if (!API_URL) return mockWhatsappReminder(memberId, lang)
  return apiFetch(`/members/${memberId}/whatsapp-reminder?lang=${lang}`)
}

export async function listPayments(): Promise<ApiPayment[]> {
  if (!API_URL) return mockListPayments()
  return apiFetch('/payments')
}

export async function staffLogin(phone: string, pin: string): Promise<void> {
  if (!API_URL) return
  const tokens = await apiFetch<TokenPair>('/auth/staff/login', {
    method: 'POST',
    body: { phone, pin },
  })
  setTokens(tokens)
}

/** Sends a fresh PIN to `phone` over WhatsApp (decision 20's narrow
 * exception to the wa.me-link pattern) and resets it on the account
 * immediately, whether or not delivery succeeds. No mock equivalent —
 * the manager login screen this powers only renders when API_URL is set. */
export async function requestStaffPinReset(phone: string): Promise<StaffPinResetResult> {
  if (!API_URL) return { sent: false }
  return apiFetch('/auth/staff/pin/reset', { method: 'POST', body: { phone } })
}

export { clearTokens as managerSignOut, isManagerSignedIn } from './client'
