/**
 * The only functions manager feature components call for data — never
 * `fetch` directly (client.ts is the one place that lives), and never
 * `@/mocks/data` directly. Each function checks API_URL once and either
 * calls the live API or the mock adapter; the shape returned is identical
 * either way (src/data/types.ts).
 */
import { API_URL, apiFetch, newIdempotencyKey, setTokens } from './client'
import {
  mockCreateExercise,
  mockCreateMember,
  mockCreateNutritionLog,
  mockCreateProgram,
  mockCreateWorkoutSession,
  mockFinishWorkoutSession,
  mockGetActiveProgram,
  mockGetMember,
  mockGetTodayWorkout,
  mockGetWorkoutSession,
  mockLapsedMembers,
  mockListExercises,
  mockListMachines,
  mockListMembers,
  mockListNutritionLogs,
  mockListPayments,
  mockListPlans,
  mockListTodaysCheckIns,
  mockLogSet,
  mockRecordPayment,
  mockReplaceProgramExercises,
  mockUpdateCheckInStatus,
  mockUpdateProgram,
  mockWhatsappReminder,
} from './mockAdapter'
import type {
  ApiCheckIn,
  ApiExercise,
  ApiLapsedMember,
  ApiMachine,
  ApiMember,
  ApiMemberDetail,
  ApiNutritionLog,
  ApiPayment,
  ApiPlan,
  ApiProgram,
  ApiTodayWorkout,
  ApiWorkoutSession,
  ApiWorkoutSet,
  CreateExerciseInput,
  CreateMemberInput,
  CreateNutritionLogInput,
  CreateProgramInput,
  CreateWorkoutSessionInput,
  FinishWorkoutSessionInput,
  LogSetInput,
  RecordPaymentInput,
  ReplaceProgramExercisesInput,
  StaffPasswordResetResult,
  TokenPair,
  UpdateProgramInput,
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

export async function updateCheckInStatus(checkInId: string, status: string): Promise<ApiCheckIn> {
  if (!API_URL) return mockUpdateCheckInStatus(checkInId, status)
  return apiFetch(`/check-ins/${checkInId}`, {
    method: 'PATCH',
    body: { status },
    idempotencyKey: newIdempotencyKey(),
  })
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

export async function staffLogin(username: string, password: string): Promise<void> {
  if (!API_URL) return
  const tokens = await apiFetch<TokenPair>('/auth/staff/login', {
    method: 'POST',
    body: { username, password },
  })
  setTokens(tokens)
}

/** Sends a fresh password for `username` over WhatsApp (decision 20's
 * narrow exception to the wa.me-link pattern) — delivered to the phone on
 * file — and resets it on the account immediately, whether or not
 * delivery succeeds. No mock equivalent — the manager login screen this
 * powers only renders when API_URL is set. */
export async function requestStaffPasswordReset(
  username: string,
): Promise<StaffPasswordResetResult> {
  if (!API_URL) return { sent: false }
  return apiFetch('/auth/staff/password/reset', { method: 'POST', body: { username } })
}

export { clearTokens as staffSignOut, getStaffRole, isStaffSignedIn } from './client'

// ---------------------------------------------------------------------
// Phase 3 — the floor. Coach and manager share one staff data layer
// (decision 21); nothing here is manager- or coach-only at the query
// layer, callers decide what to render.
// ---------------------------------------------------------------------

export async function listExercises(): Promise<ApiExercise[]> {
  if (!API_URL) return mockListExercises()
  return apiFetch('/exercises')
}

export async function createExercise(input: CreateExerciseInput): Promise<ApiExercise> {
  if (!API_URL) return mockCreateExercise(input)
  return apiFetch('/exercises', { method: 'POST', body: input, idempotencyKey: newIdempotencyKey() })
}

export async function listMachines(): Promise<ApiMachine[]> {
  if (!API_URL) return mockListMachines()
  return apiFetch('/machines')
}

export async function getActiveProgram(memberId: string): Promise<ApiProgram | null> {
  if (!API_URL) return mockGetActiveProgram(memberId)
  return apiFetch(`/members/${memberId}/programs/active`)
}

export async function createProgram(
  memberId: string,
  input: CreateProgramInput,
): Promise<ApiProgram> {
  if (!API_URL) return mockCreateProgram(memberId, input)
  return apiFetch(`/members/${memberId}/programs`, {
    method: 'POST',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function replaceProgramExercises(
  programId: string,
  input: ReplaceProgramExercisesInput,
): Promise<ApiProgram> {
  if (!API_URL) return mockReplaceProgramExercises(programId, input)
  return apiFetch(`/programs/${programId}/exercises`, {
    method: 'PATCH',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function updateProgram(
  programId: string,
  input: UpdateProgramInput,
): Promise<ApiProgram> {
  if (!API_URL) return mockUpdateProgram(programId, input)
  return apiFetch(`/programs/${programId}`, {
    method: 'PATCH',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function getTodayWorkout(memberId: string): Promise<ApiTodayWorkout> {
  if (!API_URL) return mockGetTodayWorkout(memberId)
  return apiFetch(`/members/${memberId}/today-workout`)
}

export async function createWorkoutSession(
  input: CreateWorkoutSessionInput,
): Promise<ApiWorkoutSession> {
  if (!API_URL) return mockCreateWorkoutSession(input)
  return apiFetch('/workout-sessions', {
    method: 'POST',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function getWorkoutSession(sessionId: string): Promise<ApiWorkoutSession> {
  if (!API_URL) return mockGetWorkoutSession(sessionId)
  return apiFetch(`/workout-sessions/${sessionId}`)
}

export async function finishWorkoutSession(
  sessionId: string,
  input: FinishWorkoutSessionInput,
): Promise<ApiWorkoutSession> {
  if (!API_URL) return mockFinishWorkoutSession(sessionId, input)
  return apiFetch(`/workout-sessions/${sessionId}`, {
    method: 'PATCH',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function logSet(sessionId: string, input: LogSetInput): Promise<ApiWorkoutSet> {
  if (!API_URL) return mockLogSet(sessionId, input)
  return apiFetch(`/workout-sessions/${sessionId}/sets`, {
    method: 'POST',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function createNutritionLog(
  memberId: string,
  input: CreateNutritionLogInput,
): Promise<ApiNutritionLog> {
  if (!API_URL) return mockCreateNutritionLog(memberId, input)
  return apiFetch(`/members/${memberId}/nutrition-logs`, {
    method: 'POST',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function listNutritionLogs(memberId: string): Promise<ApiNutritionLog[]> {
  if (!API_URL) return mockListNutritionLogs(memberId)
  return apiFetch(`/members/${memberId}/nutrition-logs`)
}
