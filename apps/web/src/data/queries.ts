/**
 * The only functions manager feature components call for data — never
 * `fetch` directly (client.ts is the one place that lives), and never
 * `@/mocks/data` directly. Each function checks API_URL once and either
 * calls the live API or the mock adapter; the shape returned is identical
 * either way (src/data/types.ts).
 */
import {
  API_URL,
  apiFetch,
  clearTokens,
  newIdempotencyKey,
  offlineFetch,
  setTokens,
  uploadMedia,
  type AuthAs,
} from './client'
import {
  mockApproveAiDraft,
  mockCancelBooking,
  mockCreateBooking,
  mockCreateCheckIn,
  mockCreateExercise,
  mockCreateFoodEntry,
  mockCreateMember,
  mockCreateNutritionLog,
  mockCreateProgram,
  mockCreateProgressPhoto,
  mockCreateStaff,
  mockCreateVideo,
  mockCreateWorkoutSession,
  mockDeleteFoodEntry,
  mockDeleteProgressPhoto,
  mockEstimateFoodEntry,
  mockFinishWorkoutSession,
  mockGenerateAiDraft,
  mockGetActiveProgram,
  mockGetMember,
  mockGetTodayWorkout,
  mockGetVideo,
  mockListWorkoutSessions,
  mockGetWorkoutSession,
  mockLapsedMembers,
  mockListAiDrafts,
  mockListClasses,
  mockListCoaches,
  mockListExercises,
  mockListFoodEntries,
  mockListMachines,
  mockListMembers,
  mockListMyAttendance,
  mockListMyBookings,
  mockListNutritionLogs,
  mockListPayments,
  mockListPlans,
  mockListProgressPhotos,
  mockListSharedPhotos,
  mockListStaff,
  mockListTodaysCheckIns,
  mockListVideos,
  mockLogSet,
  mockRecordPayment,
  mockRejectAiDraft,
  mockReplaceProgramExercises,
  mockSendChatMessage,
  mockUpdateCheckInStatus,
  mockUpdateExercise,
  mockUpdateMyProfile,
  mockUpdateProgram,
  mockUpdateProgressPhoto,
  mockUpdateVideo,
  mockWhatsappReminder,
} from './mockAdapter'
import type { Lang } from '@/i18n'
import type {
  AiDraftKind,
  ApiAiDraft,
  ApiAttendanceDay,
  ApiBooking,
  ApiChatReply,
  ApiCheckIn,
  ApiCoach,
  ApiExercise,
  ApiFoodEntry,
  ApiFoodEstimate,
  ApiGymClass,
  ApiLapsedMember,
  ApiMachine,
  ApiMember,
  ApiMemberDetail,
  ApiMemberProfile,
  ApiNutritionLog,
  ApiPayment,
  ApiPlan,
  ApiProgram,
  ApiProgressPhoto,
  ApiStaff,
  ApiTodayWorkout,
  ApiVideo,
  ApiWorkoutSession,
  ApiWorkoutSet,
  ChatAgent,
  ChatTurnInput,
  CreateBookingInput,
  CreateExerciseInput,
  CreateFoodEntryInput,
  CreateMemberInput,
  CreateNutritionLogInput,
  CreateProgramInput,
  CreateStaffInput,
  CreateVideoInput,
  CreateWorkoutSessionInput,
  ApproveAiDraftInput,
  FinishWorkoutSessionInput,
  LogSetInput,
  RecordPaymentInput,
  ReplaceProgramExercisesInput,
  StaffPasswordResetResult,
  TokenPair,
  UpdateExerciseInput,
  UpdateMyProfileInput,
  UpdateProgramInput,
  UpdateVideoInput,
} from './types'

export async function listMembers(): Promise<ApiMember[]> {
  if (!API_URL) return mockListMembers()
  return apiFetch('/members')
}

export async function getMember(memberId: string): Promise<ApiMemberDetail> {
  if (!API_URL) return mockGetMember(memberId)
  return apiFetch(`/members/${memberId}`)
}

/** A member editing their own body/lifestyle profile — decision 28's
 * /members/me/... pattern, deliberately separate from staff's updateMember
 * (which also edits name/phone/plan-adjacent fields). Excludes
 * daily_kcal_target entirely; that's coach/AI-approval-only. */
export async function updateMyProfile(input: UpdateMyProfileInput): Promise<ApiMemberProfile> {
  if (!API_URL) return mockUpdateMyProfile(input)
  return apiFetch('/members/me/profile', {
    method: 'PATCH',
    body: input,
    authAs: 'member',
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function listPlans(): Promise<ApiPlan[]> {
  if (!API_URL) return mockListPlans()
  return apiFetch('/plans')
}

export async function listTodaysCheckIns(): Promise<ApiCheckIn[]> {
  if (!API_URL) return mockListTodaysCheckIns()
  return apiFetch('/check-ins/today')
}

/** Deliberately NOT offline-tolerant, unlike the rest of the floor writes
 * below: check-in ids are always server-minted (no client-id field on
 * POST /check-ins, unlike workout sessions/sets/nutrition logs), so there
 * is no safe local echo to hand back — a queued check-in would show the
 * coach an id that the real row will never actually have. Front-desk
 * check-in also happens where connectivity is least likely to be the
 * problem; fails visibly like before, same as every other manager write. */
export async function createCheckIn(memberId: string): Promise<ApiCheckIn> {
  if (!API_URL) return mockCreateCheckIn(memberId)
  return apiFetch('/check-ins', {
    method: 'POST',
    body: { member_id: memberId },
    idempotencyKey: newIdempotencyKey(),
  })
}

/** Takes the check-in as the caller already has it (not just its id) so the
 * local echo used when offline is a real, complete ApiCheckIn rather than a
 * guess — this is floor data (part of the coach's session flow), so it goes
 * through the outbox like sessions/sets/nutrition. */
export async function updateCheckInStatus(
  checkIn: ApiCheckIn,
  status: string,
): Promise<ApiCheckIn> {
  if (!API_URL) return mockUpdateCheckInStatus(checkIn.id, status)
  return offlineFetch(`/check-ins/${checkIn.id}`, {
    method: 'PATCH',
    body: { status },
    localEcho: { ...checkIn, status },
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
// Phase 4 — member self-service auth (decision 13, decision 28). Mock
// mode keeps today's tap-through behavior — see RequireMember in App.tsx
// — these only do anything real once API_URL is set.
// ---------------------------------------------------------------------

/** Always resolves — the endpoint itself never reveals whether `phone`
 * matched a member (see app/api/auth.py's request_own_member_code), so
 * there's nothing meaningful to branch on here either. */
export async function requestMemberCode(phone: string): Promise<void> {
  if (!API_URL) return
  await apiFetch('/auth/member/code', { method: 'POST', body: { phone } })
}

export async function memberLogin(phone: string, code: string): Promise<void> {
  if (!API_URL) return
  const tokens = await apiFetch<TokenPair>('/auth/member/login', {
    method: 'POST',
    body: { phone, code },
    authAs: 'member',
  })
  setTokens(tokens, 'member')
}

export function memberSignOut() {
  clearTokens('member')
}

export { getCurrentMemberId, isMemberSignedIn } from './client'

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

export async function updateExercise(
  exerciseId: string,
  input: UpdateExerciseInput,
): Promise<ApiExercise> {
  if (!API_URL) return mockUpdateExercise(exerciseId, input)
  return apiFetch(`/exercises/${exerciseId}`, {
    method: 'PATCH',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function listMachines(): Promise<ApiMachine[]> {
  if (!API_URL) return mockListMachines()
  return apiFetch('/machines')
}

// ---------------------------------------------------------------------
// Phase 4 stage 3 — the video library. Readable by staff and members
// alike (pass authAs to match the caller), writable by staff only.
// ---------------------------------------------------------------------

export async function listVideos(authAs: AuthAs = 'staff'): Promise<ApiVideo[]> {
  if (!API_URL) return mockListVideos()
  return apiFetch('/videos', { authAs })
}

export async function getVideo(videoId: string, authAs: AuthAs = 'staff'): Promise<ApiVideo> {
  if (!API_URL) return mockGetVideo(videoId)
  return apiFetch(`/videos/${videoId}`, { authAs })
}

export async function createVideo(input: CreateVideoInput): Promise<ApiVideo> {
  if (!API_URL) return mockCreateVideo(input)
  return apiFetch('/videos', { method: 'POST', body: input, idempotencyKey: newIdempotencyKey() })
}

export async function updateVideo(videoId: string, input: UpdateVideoInput): Promise<ApiVideo> {
  if (!API_URL) return mockUpdateVideo(videoId, input)
  return apiFetch(`/videos/${videoId}`, {
    method: 'PATCH',
    body: input,
    idempotencyKey: newIdempotencyKey(),
  })
}

// ---------------------------------------------------------------------
// Phase 4 stage 4 — a member's own food log. All member-scoped (authAs
// 'member'); the server derives "which member" from the token, never a
// URL parameter (decision 28).
// ---------------------------------------------------------------------

export async function listFoodEntries(): Promise<ApiFoodEntry[]> {
  if (!API_URL) return mockListFoodEntries()
  return apiFetch('/members/me/food-entries', { authAs: 'member' })
}

export async function createFoodEntry(input: CreateFoodEntryInput): Promise<ApiFoodEntry> {
  if (!API_URL) return mockCreateFoodEntry(input)
  return apiFetch('/members/me/food-entries', {
    method: 'POST',
    body: input,
    idempotencyKey: newIdempotencyKey(),
    authAs: 'member',
  })
}

export async function deleteFoodEntry(entryId: string): Promise<void> {
  if (!API_URL) return mockDeleteFoodEntry(entryId)
  await apiFetch(`/members/me/food-entries/${entryId}`, {
    method: 'DELETE',
    idempotencyKey: newIdempotencyKey(),
    authAs: 'member',
  })
}

/** `dataUrl` is the already-computed FileReader preview MemberFood.tsx
 * builds for the confirm-card thumbnail either way; mock mode reuses it
 * as the food entry's photo_key (there's no real object store to
 * round-trip through) instead of re-deriving it from `file`. */
export async function uploadFoodPhoto(file: File, dataUrl: string): Promise<string> {
  if (!API_URL) return dataUrl
  const result = await uploadMedia(file, 'member')
  return result.key
}

/** Phase 5 stage 8 — a single best-guess read of an already-uploaded
 * photo, never a write (decision 12's confirm step is untouched). Food.tsx
 * uploads the photo first (uploadFoodPhoto) so this has a real photo_key
 * to send. */
export async function estimateFoodEntry(photoKey: string, lang: Lang): Promise<ApiFoodEstimate> {
  if (!API_URL) return mockEstimateFoodEntry(lang)
  return apiFetch('/members/me/food-entries/estimate', {
    method: 'POST',
    body: { photo_key: photoKey, lang },
    idempotencyKey: newIdempotencyKey(),
    authAs: 'member',
  })
}

// ---------------------------------------------------------------------
// Phase 4 stage 5 — a member's own progress photos (decision 11). Member-
// scoped writes (authAs 'member'); the one staff-facing read below is
// intentionally separate and stays on the default 'staff' auth.
// ---------------------------------------------------------------------

export async function listProgressPhotos(): Promise<ApiProgressPhoto[]> {
  if (!API_URL) return mockListProgressPhotos()
  return apiFetch('/members/me/progress-photos', { authAs: 'member' })
}

/** Same reasoning as uploadFoodPhoto: `dataUrl` stands in for a real
 * storage key in mock mode. */
export async function uploadProgressPhoto(file: File, dataUrl: string): Promise<string> {
  if (!API_URL) return dataUrl
  const result = await uploadMedia(file, 'member')
  return result.key
}

export async function createProgressPhoto(photoKey: string): Promise<ApiProgressPhoto> {
  if (!API_URL) return mockCreateProgressPhoto(photoKey)
  return apiFetch('/members/me/progress-photos', {
    method: 'POST',
    body: { photo_key: photoKey },
    idempotencyKey: newIdempotencyKey(),
    authAs: 'member',
  })
}

export async function setProgressPhotoShared(
  photoId: string,
  sharedWithCoach: boolean,
): Promise<ApiProgressPhoto> {
  if (!API_URL) return mockUpdateProgressPhoto(photoId, sharedWithCoach)
  return apiFetch(`/members/me/progress-photos/${photoId}`, {
    method: 'PATCH',
    body: { shared_with_coach: sharedWithCoach },
    idempotencyKey: newIdempotencyKey(),
    authAs: 'member',
  })
}

export async function deleteProgressPhoto(photoId: string): Promise<void> {
  if (!API_URL) return mockDeleteProgressPhoto(photoId)
  await apiFetch(`/members/me/progress-photos/${photoId}`, {
    method: 'DELETE',
    idempotencyKey: newIdempotencyKey(),
    authAs: 'member',
  })
}

/** The one staff-facing read of this data — only ever rows the member
 * explicitly shared (decision 11), enforced server-side. Staff-scoped
 * (default authAs), unlike everything else in this section. */
export async function listSharedPhotos(memberId: string): Promise<ApiProgressPhoto[]> {
  if (!API_URL) return mockListSharedPhotos()
  return apiFetch(`/members/${memberId}/shared-photos`)
}

// ---------------------------------------------------------------------
// Phase 4 stage 6 — coaches, the class schedule, and a member's own
// bookings/attendance. Coaches/classes are readable by any signed-in
// role; bookings/attendance are member-scoped (authAs 'member').
// ---------------------------------------------------------------------

export async function listCoaches(): Promise<ApiCoach[]> {
  if (!API_URL) return mockListCoaches()
  return apiFetch('/coaches')
}

export async function listClasses(): Promise<ApiGymClass[]> {
  if (!API_URL) return mockListClasses()
  return apiFetch('/classes')
}

export async function listMyBookings(): Promise<ApiBooking[]> {
  if (!API_URL) return mockListMyBookings()
  return apiFetch('/members/me/bookings', { authAs: 'member' })
}

export async function createBooking(input: CreateBookingInput): Promise<ApiBooking> {
  if (!API_URL) return mockCreateBooking(input)
  return apiFetch('/members/me/bookings', {
    method: 'POST',
    body: input,
    idempotencyKey: newIdempotencyKey(),
    authAs: 'member',
  })
}

export async function cancelBooking(bookingId: string): Promise<ApiBooking> {
  if (!API_URL) return mockCancelBooking(bookingId)
  return apiFetch(`/members/me/bookings/${bookingId}`, {
    method: 'PATCH',
    idempotencyKey: newIdempotencyKey(),
    authAs: 'member',
  })
}

export async function listMyAttendance(): Promise<ApiAttendanceDay[]> {
  if (!API_URL) return mockListMyAttendance()
  return apiFetch('/members/me/attendance', { authAs: 'member' })
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

/** Finished sessions only, most recent first — the coach's "last workout"
 * summary. Never offline-tolerant: it's a read, not a floor write. */
export async function listWorkoutSessions(
  memberId: string,
  limit = 5,
  authAs: AuthAs = 'staff',
): Promise<ApiWorkoutSession[]> {
  if (!API_URL) return mockListWorkoutSessions(memberId, limit)
  return apiFetch(`/members/${memberId}/workout-sessions?limit=${limit}`, { authAs })
}

/** Client-mints the session id up front (docs/DECISIONS.md) so the local
 * echo used when offline carries the same id the very next queued "log a
 * set" call will reference — the id is real either way, never a
 * placeholder swapped out later. */
export async function createWorkoutSession(
  input: CreateWorkoutSessionInput,
): Promise<ApiWorkoutSession> {
  if (!API_URL) return mockCreateWorkoutSession(input)
  const id = input.id ?? crypto.randomUUID()
  const body = { ...input, id }
  const localEcho: ApiWorkoutSession = {
    id,
    member_id: input.member_id,
    check_in_id: input.check_in_id ?? null,
    started_at: input.started_at,
    finished_at: null,
    effort_band: null,
    sets: [],
  }
  return offlineFetch('/workout-sessions', { method: 'POST', body, localEcho })
}

export async function getWorkoutSession(sessionId: string): Promise<ApiWorkoutSession> {
  if (!API_URL) return mockGetWorkoutSession(sessionId)
  return apiFetch(`/workout-sessions/${sessionId}`)
}

/** `session` is the caller's current copy — the echo is built by applying
 * this finish onto it, since a PATCH response has no other way to know
 * what the session's sets looked like before finishing. */
export async function finishWorkoutSession(
  session: ApiWorkoutSession,
  input: FinishWorkoutSessionInput,
): Promise<ApiWorkoutSession> {
  if (!API_URL) return mockFinishWorkoutSession(session.id, input)
  const localEcho: ApiWorkoutSession = {
    ...session,
    finished_at: input.finished_at,
    effort_band: input.effort_band ?? session.effort_band,
  }
  return offlineFetch(`/workout-sessions/${session.id}`, { method: 'PATCH', body: input, localEcho })
}

export async function logSet(sessionId: string, input: LogSetInput): Promise<ApiWorkoutSet> {
  if (!API_URL) return mockLogSet(sessionId, input)
  const id = input.id ?? crypto.randomUUID()
  const body = { ...input, id }
  const localEcho: ApiWorkoutSet = {
    id,
    exercise_id: input.exercise_id,
    set_number: input.set_number,
    reps: input.reps,
    weight_kg: input.weight_kg,
    machine_id: input.machine_id ?? null,
    at: input.at,
  }
  return offlineFetch(`/workout-sessions/${sessionId}/sets`, { method: 'POST', body, localEcho })
}

export async function createNutritionLog(
  memberId: string,
  input: CreateNutritionLogInput,
): Promise<ApiNutritionLog> {
  if (!API_URL) return mockCreateNutritionLog(memberId, input)
  const id = input.id ?? crypto.randomUUID()
  const body = { ...input, id }
  const localEcho: ApiNutritionLog = {
    id,
    member_id: memberId,
    at: input.at,
    band: input.band,
    meals: input.meals ?? [],
    source: input.source,
  }
  return offlineFetch(`/members/${memberId}/nutrition-logs`, { method: 'POST', body, localEcho })
}

export async function listNutritionLogs(memberId: string): Promise<ApiNutritionLog[]> {
  if (!API_URL) return mockListNutritionLogs(memberId)
  return apiFetch(`/members/${memberId}/nutrition-logs`)
}

export async function listStaff(): Promise<ApiStaff[]> {
  if (!API_URL) return mockListStaff()
  return apiFetch('/staff')
}

export async function createStaff(input: CreateStaffInput): Promise<ApiStaff> {
  if (!API_URL) return mockCreateStaff(input)
  return apiFetch('/staff', { method: 'POST', body: input, idempotencyKey: newIdempotencyKey() })
}

// ---------------------------------------------------------------------
// Phase 5 — the coach's AI draft inbox (decision 10). Nothing an assistant
// or a coach's "generate" action proposes reaches a member's program or
// calorie target until approved here.
// ---------------------------------------------------------------------

export async function listAiDrafts(): Promise<ApiAiDraft[]> {
  if (!API_URL) return mockListAiDrafts()
  return apiFetch('/ai-drafts')
}

export async function approveAiDraft(
  draftId: string,
  edits?: ApproveAiDraftInput,
): Promise<ApiAiDraft> {
  if (!API_URL) return mockApproveAiDraft(draftId, edits)
  return apiFetch(`/ai-drafts/${draftId}/approve`, {
    method: 'POST',
    body: edits ?? {},
    idempotencyKey: newIdempotencyKey(),
  })
}

export async function rejectAiDraft(draftId: string): Promise<ApiAiDraft> {
  if (!API_URL) return mockRejectAiDraft(draftId)
  return apiFetch(`/ai-drafts/${draftId}/reject`, {
    method: 'POST',
    idempotencyKey: newIdempotencyKey(),
  })
}

/** Phase 5 stage 9 — a coach action, not a chat message, but the same
 * mechanism either way (decision 31): this always writes a new pending
 * draft into the inbox above, never applies anything directly. */
export async function generateAiDraft(
  memberId: string,
  kind: AiDraftKind,
  lang: Lang,
): Promise<ApiAiDraft> {
  if (!API_URL) return mockGenerateAiDraft(memberId, kind)
  return apiFetch(`/members/${memberId}/ai-drafts/generate`, {
    method: 'POST',
    body: { kind, lang },
    idempotencyKey: newIdempotencyKey(),
  })
}

// ---------------------------------------------------------------------
// Phase 5 stage 7 — the member chat assistants. The only place `fetch`
// (via apiFetch) reaches Claude; mocks/agents.ts's replyTo() stays the
// mock branch, unchanged.
// ---------------------------------------------------------------------

export async function sendChatMessage(
  agent: ChatAgent,
  message: string,
  history: ChatTurnInput[],
  lang: Lang,
): Promise<ApiChatReply> {
  if (!API_URL) return mockSendChatMessage(agent, message, lang)
  return apiFetch(`/members/me/chat/${agent}`, {
    method: 'POST',
    body: { text: message, history, lang },
    authAs: 'member',
    idempotencyKey: newIdempotencyKey(),
  })
}
