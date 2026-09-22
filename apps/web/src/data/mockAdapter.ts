/**
 * Adapts src/mocks/data.ts into the exact same shape the live API returns,
 * so feature components read one type (src/data/types.ts) regardless of
 * whether VITE_API_URL is set. Mutations write to a session-only in-memory
 * copy — mock mode has never persisted across reloads, and this keeps it
 * that way; that gap is exactly what running the gym on the real API is
 * for.
 */
import {
  aiDrafts as seedAiDrafts,
  attendance as seedAttendance,
  bookings as seedBookings,
  checkIns as seedCheckIns,
  classes as seedClasses,
  coaches as seedCoaches,
  currentMemberId,
  dayPlans as seedDayPlans,
  daysSinceVisit,
  findPlan,
  foodGuesses,
  machines as seedMachines,
  members as seedMembers,
  nutrition as seedNutrition,
  payments as seedPayments,
  plans,
  videos as seedVideos,
} from '@/mocks/data'
import type {
  CheckIn as MockCheckIn,
  Member as MockMember,
  Payment as MockPayment,
} from '@/mocks/types'
import { ApiError } from './client'
import { waLink } from '@/lib/whatsapp'
import { replyTo } from '@/mocks/agents'
import type { AgentId } from '@/mocks/types'
import { text } from '@/lib/format'
import type { Text } from '@/lib/format'
import type { Lang } from '@/i18n'
import type {
  AiDraftKind,
  ApiAiDraft,
  ApiAnalyticsSummary,
  ApiAttendanceDay,
  ApiBooking,
  ApiCollectionWindow,
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
  ReplaceProgramExercisesInput,
  RecordPaymentInput,
  StaffPasswordOut,
  StaffRole,
  UpdateExerciseInput,
  UpdateProgramInput,
  UpdateVideoInput,
  UpdateMyProfileInput,
} from './types'

let mockMembers: MockMember[] = seedMembers.map((m) => ({ ...m }))
// Session-only, mirrors ai_plan_drafts.approve writing MemberProfile.daily_kcal_target
// on the real backend — a coach can only ever set it by approving a draft.
const mockDailyKcalTargets = new Map<string, number>()
let mockPayments: MockPayment[] = seedPayments.map((p) => ({ ...p }))
let mockCheckIns: MockCheckIn[] = seedCheckIns.map((c) => ({ ...c }))

const newId = () => Math.random().toString(36).slice(2, 10)
const todayIso = () => new Date().toISOString().slice(0, 10)

function toApiMember(m: MockMember): ApiMember {
  const plan = findPlan(m.planId)
  return {
    id: m.id,
    name: m.name,
    name_en: m.nameEn,
    phone: m.phone,
    joined_at: m.joinedAt,
    plan_id: m.planId,
    plan_name: plan ? plan.name : null,
    ends_at: m.endsAt,
    last_visit: m.lastVisit,
    dues: { status: m.status, owed_usd: m.owedUsd },
  }
}

function toApiMemberDetail(m: MockMember): ApiMemberDetail {
  return {
    ...toApiMember(m),
    profile: {
      goal: m.goal,
      level: m.level,
      height_cm: m.heightCm,
      weight_kg: m.weightKg,
      body_fat: m.bodyFat,
      injuries: m.injuries.map((i) => ({
        body_part: i.bodyPart,
        note: i.note,
        severity: i.severity,
      })),
      days_per_week: m.daysPerWeek,
      job: m.job,
      sleep_hours: m.sleepHours,
      weight_trend: m.weightTrend,
      daily_kcal_target: mockDailyKcalTargets.get(m.id) ?? null,
    },
  }
}

export function mockListMembers(): ApiMember[] {
  return mockMembers.map(toApiMember)
}

export function mockGetMember(memberId: string): ApiMemberDetail {
  const m = mockMembers.find((x) => x.id === memberId)
  if (!m) throw new Error('Member not found')
  return toApiMemberDetail(m)
}

export function mockUpdateMyProfile(input: UpdateMyProfileInput): ApiMemberProfile {
  const idx = mockMembers.findIndex((x) => x.id === currentMemberId)
  if (idx === -1) throw new Error('Member not found')
  const existing = mockMembers[idx]
  const updated: MockMember = {
    ...existing,
    goal: input.goal ?? existing.goal,
    level: input.level ?? existing.level,
    heightCm: input.height_cm ?? existing.heightCm,
    weightKg: input.weight_kg ?? existing.weightKg,
    bodyFat: input.body_fat !== undefined ? input.body_fat : existing.bodyFat,
    injuries: input.injuries
      ? input.injuries.map((i) => ({ bodyPart: i.body_part, note: i.note, severity: i.severity }))
      : existing.injuries,
    daysPerWeek: input.days_per_week ?? existing.daysPerWeek,
    job: input.job ?? existing.job,
    sleepHours: input.sleep_hours ?? existing.sleepHours,
  }
  mockMembers = mockMembers.map((x, i) => (i === idx ? updated : x))
  return toApiMemberDetail(updated).profile as ApiMemberProfile
}

export function mockListTodaysCheckIns(): ApiCheckIn[] {
  // The mock checkIns array already represents "today's" front-desk queue
  // (its `at` is a bare time, not a date), so no date filtering to do here.
  return mockCheckIns.map((c) => ({
    id: c.id,
    member_id: c.memberId,
    at: c.at,
    status: c.status,
  }))
}

export function mockCreateCheckIn(memberId: string): ApiCheckIn {
  const member = mockMembers.find((m) => m.id === memberId)
  if (!member) throw new Error('Member not found')
  const now = new Date()
  const checkIn: MockCheckIn = {
    id: newId(),
    memberId,
    at: `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`,
    status: 'waiting',
  }
  mockCheckIns = [...mockCheckIns, checkIn]
  return { id: checkIn.id, member_id: checkIn.memberId, at: checkIn.at, status: checkIn.status }
}

export function mockUpdateCheckInStatus(checkInId: string, status: string): ApiCheckIn {
  const idx = mockCheckIns.findIndex((c) => c.id === checkInId)
  if (idx === -1) throw new Error('Check-in not found')
  const updated: MockCheckIn = { ...mockCheckIns[idx], status: status as MockCheckIn['status'] }
  mockCheckIns = mockCheckIns.map((c, i) => (i === idx ? updated : c))
  return { id: updated.id, member_id: updated.memberId, at: updated.at, status: updated.status }
}

export function mockListPlans(): ApiPlan[] {
  return plans.map((p) => ({ id: p.id, name: p.name, price_usd: p.priceUsd, days: p.days }))
}

export function mockLapsedMembers(minDays: number): ApiLapsedMember[] {
  return mockMembers
    .map((m) => ({ member: m, days: daysSinceVisit(m.id) }))
    .filter((row) => row.days >= minDays)
    .sort((a, b) => b.days - a.days)
    .map(({ member: m, days }) => ({
      id: m.id,
      name: m.name,
      name_en: m.nameEn,
      phone: m.phone,
      last_visit: m.lastVisit,
      days_since_visit: Number.isFinite(days) ? days : null,
    }))
}

export function mockCreateMember(input: CreateMemberInput): ApiMemberDetail {
  const plan = plans.find((p) => p.id === input.plan_id)
  const today = todayIso()
  const endsAt = plan
    ? new Date(Date.now() + plan.days * 86_400_000).toISOString().slice(0, 10)
    : today
  const member: MockMember = {
    id: newId(),
    name: input.name,
    nameEn: input.name_en,
    phone: input.phone,
    planId: input.plan_id,
    joinedAt: today,
    endsAt,
    status: 'paid',
    owedUsd: 0,
    lastVisit: null,
    goal: input.goal,
    level: input.level,
    heightCm: input.height_cm,
    weightKg: input.weight_kg,
    bodyFat: input.body_fat,
    injuries: input.injuries.map((i) => ({
      bodyPart: i.body_part,
      note: i.note,
      severity: i.severity,
    })),
    daysPerWeek: input.days_per_week,
    job: input.job,
    sleepHours: input.sleep_hours,
    weightTrend: [],
  }
  mockMembers = [...mockMembers, member]
  return toApiMemberDetail(member)
}

export function mockRecordPayment(memberId: string, input: RecordPaymentInput): ApiMemberDetail {
  const idx = mockMembers.findIndex((m) => m.id === memberId)
  if (idx === -1) throw new Error('Member not found')
  const member = mockMembers[idx]
  const planId = input.plan_id ?? member.planId
  const plan = plans.find((p) => p.id === planId)
  const base = Math.max(new Date(member.endsAt).getTime(), Date.now())
  const newEndsAt = plan
    ? new Date(base + plan.days * 86_400_000).toISOString().slice(0, 10)
    : member.endsAt

  const updated: MockMember = { ...member, planId, endsAt: newEndsAt, status: 'paid', owedUsd: 0 }
  mockMembers = mockMembers.map((m, i) => (i === idx ? updated : m))
  mockPayments = [
    ...mockPayments,
    {
      id: newId(),
      memberId,
      amountUsd: input.amount_usd,
      at: todayIso(),
      method: input.method === 'transfer' ? 'transfer' : 'cash',
      by: 'You',
    },
  ]
  return toApiMemberDetail(updated)
}

export function mockWhatsappReminder(memberId: string, lang: 'ar' | 'en'): { wa_link: string } {
  const m = mockMembers.find((x) => x.id === memberId)
  if (!m) throw new Error('Member not found')
  const name = lang === 'ar' ? m.name : m.nameEn
  const message =
    lang === 'ar'
      ? `مرحبا ${name}، رح تعمل تذكير بسيط إنو المبلغ المتوجب عليك هو ${m.owedUsd}$. شكرا!`
      : `Hi ${name}, a quick reminder that you have $${m.owedUsd} due. Thanks!`
  return { wa_link: waLink(m.phone, message) }
}

export function mockListPayments(): ApiPayment[] {
  const rows: ApiPayment[] = []
  for (const p of mockPayments) {
    // Looked up against the session's mutable copy, not mocks/data's seed
    // export — a payment for a member created this session (not in the
    // original seed) must still resolve here.
    const member = mockMembers.find((m) => m.id === p.memberId)
    if (!member) continue
    rows.push({
      id: p.id,
      member_id: p.memberId,
      member_name: member.name,
      member_name_en: member.nameEn,
      amount_usd: p.amountUsd,
      at: p.at,
      method: p.method,
    })
  }
  return rows.sort((a, b) => b.at.localeCompare(a.at))
}

// ---------------------------------------------------------------------
// Phase 3 — the floor. dayPlans/nutrition have no separate exercise
// catalog in mocks/data.ts (each PrescribedExercise carries its own
// name inline), so the mock catalog is derived from them by deduping on
// PrescribedExercise.id; a program's exercises then reference that same id,
// matching the real API's catalog-id relationship.
// ---------------------------------------------------------------------

const toBilingual = (t: Text): { ar: string; en: string } =>
  typeof t === 'string' ? { ar: t, en: t } : t

function seedExerciseCatalog(): ApiExercise[] {
  const seen = new Map<string, ApiExercise>()
  for (const plan of seedDayPlans) {
    for (const e of plan.exercises) {
      if (!seen.has(e.id)) {
        seen.set(e.id, { id: e.id, name: e.name, muscle_group: 'general', video_url: null, active: true })
      }
    }
  }
  return [...seen.values()]
}

function seedPrograms(): ApiProgram[] {
  return seedDayPlans.map((plan) => ({
    id: `program-${plan.memberId}`,
    member_id: plan.memberId,
    title: plan.title,
    archived_at: null,
    exercises: plan.exercises.map((e, i) => ({
      id: `${plan.memberId}-pe-${e.id}`,
      exercise_id: e.id,
      exercise_name: e.name,
      order_index: i,
      sets: e.sets,
      reps: toBilingual(e.reps),
      target_weight_kg: e.lastWeightKg,
    })),
  }))
}

let mockExercises: ApiExercise[] = seedExerciseCatalog()
let mockPrograms: ApiProgram[] = seedPrograms()
let mockWorkoutSessions: ApiWorkoutSession[] = []
let mockNutritionLogs: ApiNutritionLog[] = seedNutrition.map((n, i) => ({
  id: `nutrition-seed-${i}`,
  member_id: n.memberId,
  at: n.date,
  band: n.band,
  meals: n.meals,
  source: n.source === 'coach_asked' ? 'coach' : 'member',
}))

function exerciseName(exerciseId: string): { ar: string; en: string } {
  return mockExercises.find((e) => e.id === exerciseId)?.name ?? { ar: '', en: '' }
}

export function mockListExercises(): ApiExercise[] {
  return mockExercises.filter((e) => e.active)
}

export function mockCreateExercise(input: CreateExerciseInput): ApiExercise {
  const exercise: ApiExercise = {
    id: newId(),
    name: input.name,
    muscle_group: input.muscle_group,
    video_url: input.video_url ?? null,
    active: true,
  }
  mockExercises = [...mockExercises, exercise]
  return exercise
}

export function mockUpdateExercise(exerciseId: string, input: UpdateExerciseInput): ApiExercise {
  const existing = mockExercises.find((e) => e.id === exerciseId)
  if (!existing) throw new Error('Exercise not found')
  const updated: ApiExercise = {
    ...existing,
    video_url: input.video_url !== undefined ? input.video_url : existing.video_url,
  }
  mockExercises = mockExercises.map((e) => (e.id === exerciseId ? updated : e))
  return updated
}

export function mockListMachines(): ApiMachine[] {
  return seedMachines.map((m) => ({ id: m.id, name: toBilingual(m.name), area: m.area }))
}

let mockVideos: ApiVideo[] = seedVideos.map((v) => ({
  id: v.id,
  title: v.title,
  provider: v.provider,
  external_id: v.externalId,
  muscle_group: v.muscle,
  equipment: v.equipment,
  seconds: v.seconds,
  view_count: v.views,
  active: true,
}))

export function mockListVideos(): ApiVideo[] {
  return mockVideos.filter((v) => v.active)
}

export function mockGetVideo(videoId: string): ApiVideo {
  const existing = mockVideos.find((v) => v.id === videoId)
  if (!existing) throw new Error('Video not found')
  const updated: ApiVideo = { ...existing, view_count: existing.view_count + 1 }
  mockVideos = mockVideos.map((v) => (v.id === videoId ? updated : v))
  return updated
}

export function mockCreateVideo(input: CreateVideoInput): ApiVideo {
  const video: ApiVideo = {
    id: newId(),
    title: input.title,
    provider: input.provider,
    external_id: input.external_id,
    muscle_group: input.muscle_group,
    equipment: input.equipment,
    seconds: input.seconds,
    view_count: 0,
    active: true,
  }
  mockVideos = [...mockVideos, video]
  return video
}

export function mockUpdateVideo(videoId: string, input: UpdateVideoInput): ApiVideo {
  const existing = mockVideos.find((v) => v.id === videoId)
  if (!existing) throw new Error('Video not found')
  const updated: ApiVideo = {
    ...existing,
    title: input.title ?? existing.title,
    muscle_group: input.muscle_group ?? existing.muscle_group,
    equipment: input.equipment ?? existing.equipment,
    active: input.active ?? existing.active,
  }
  mockVideos = mockVideos.map((v) => (v.id === videoId ? updated : v))
  return updated
}

export function mockGetActiveProgram(memberId: string): ApiProgram | null {
  return mockPrograms.find((p) => p.member_id === memberId && p.archived_at === null) ?? null
}

export function mockCreateProgram(memberId: string, input: CreateProgramInput): ApiProgram {
  const now = new Date().toISOString()
  mockPrograms = mockPrograms.map((p) =>
    p.member_id === memberId && p.archived_at === null ? { ...p, archived_at: now } : p,
  )
  const program: ApiProgram = {
    id: newId(),
    member_id: memberId,
    title: input.title,
    archived_at: null,
    exercises: input.exercises.map((ex, i) => ({
      id: newId(),
      exercise_id: ex.exercise_id,
      exercise_name: exerciseName(ex.exercise_id),
      order_index: i,
      sets: ex.sets,
      reps: ex.reps,
      target_weight_kg: ex.target_weight_kg ?? null,
    })),
  }
  mockPrograms = [...mockPrograms, program]
  return program
}

export function mockReplaceProgramExercises(
  programId: string,
  input: ReplaceProgramExercisesInput,
): ApiProgram {
  const idx = mockPrograms.findIndex((p) => p.id === programId)
  if (idx === -1) throw new Error('Program not found')
  const updated: ApiProgram = {
    ...mockPrograms[idx],
    exercises: input.exercises.map((ex, i) => ({
      id: newId(),
      exercise_id: ex.exercise_id,
      exercise_name: exerciseName(ex.exercise_id),
      order_index: i,
      sets: ex.sets,
      reps: ex.reps,
      target_weight_kg: ex.target_weight_kg ?? null,
    })),
  }
  mockPrograms = mockPrograms.map((p, i) => (i === idx ? updated : p))
  return updated
}

export function mockUpdateProgram(programId: string, input: UpdateProgramInput): ApiProgram {
  const idx = mockPrograms.findIndex((p) => p.id === programId)
  if (idx === -1) throw new Error('Program not found')
  const current = mockPrograms[idx]
  const updated: ApiProgram = {
    ...current,
    title: input.title ?? current.title,
    archived_at:
      input.archived === true
        ? new Date().toISOString()
        : input.archived === false
          ? null
          : current.archived_at,
  }
  mockPrograms = mockPrograms.map((p, i) => (i === idx ? updated : p))
  return updated
}

export function mockGetTodayWorkout(memberId: string): ApiTodayWorkout {
  const program = mockGetActiveProgram(memberId)
  const openSession =
    mockWorkoutSessions.find((s) => s.member_id === memberId && s.finished_at === null) ?? null

  if (!program) {
    return {
      program_id: null,
      program_title: null,
      exercises: [],
      open_session_id: openSession?.id ?? null,
    }
  }

  const lastWeights = new Map<string, number>()
  const allSets = mockWorkoutSessions
    .filter((s) => s.member_id === memberId)
    .flatMap((s) => s.sets)
    .sort((a, b) => a.at.localeCompare(b.at))
  for (const s of allSets) lastWeights.set(s.exercise_id, s.weight_kg)

  return {
    program_id: program.id,
    program_title: program.title,
    exercises: program.exercises.map((pe) => ({
      program_exercise_id: pe.id,
      exercise_id: pe.exercise_id,
      exercise_name: pe.exercise_name,
      order_index: pe.order_index,
      sets: pe.sets,
      reps: pe.reps,
      target_weight_kg: pe.target_weight_kg,
      last_weight_kg: lastWeights.get(pe.exercise_id) ?? null,
    })),
    open_session_id: openSession?.id ?? null,
  }
}

export function mockListWorkoutSessions(memberId: string, limit: number): ApiWorkoutSession[] {
  return mockWorkoutSessions
    .filter((s) => s.member_id === memberId && s.finished_at !== null)
    .sort((a, b) => b.started_at.localeCompare(a.started_at))
    .slice(0, limit)
}

export function mockCreateWorkoutSession(input: CreateWorkoutSessionInput): ApiWorkoutSession {
  const session: ApiWorkoutSession = {
    id: input.id ?? newId(),
    member_id: input.member_id,
    check_in_id: input.check_in_id ?? null,
    started_at: input.started_at,
    finished_at: null,
    effort_band: null,
    sets: [],
  }
  mockWorkoutSessions = [...mockWorkoutSessions, session]
  return session
}

export function mockGetWorkoutSession(sessionId: string): ApiWorkoutSession {
  const session = mockWorkoutSessions.find((s) => s.id === sessionId)
  if (!session) throw new Error('Workout session not found')
  return session
}

export function mockFinishWorkoutSession(
  sessionId: string,
  input: FinishWorkoutSessionInput,
): ApiWorkoutSession {
  const idx = mockWorkoutSessions.findIndex((s) => s.id === sessionId)
  if (idx === -1) throw new Error('Workout session not found')
  const updated: ApiWorkoutSession = {
    ...mockWorkoutSessions[idx],
    finished_at: input.finished_at,
    effort_band: input.effort_band ?? mockWorkoutSessions[idx].effort_band,
  }
  mockWorkoutSessions = mockWorkoutSessions.map((s, i) => (i === idx ? updated : s))
  return updated
}

export function mockLogSet(sessionId: string, input: LogSetInput): ApiWorkoutSet {
  const idx = mockWorkoutSessions.findIndex((s) => s.id === sessionId)
  if (idx === -1) throw new Error('Workout session not found')
  const set: ApiWorkoutSet = {
    id: input.id ?? newId(),
    exercise_id: input.exercise_id,
    set_number: input.set_number,
    reps: input.reps,
    weight_kg: input.weight_kg,
    machine_id: input.machine_id ?? null,
    at: input.at,
  }
  const updated: ApiWorkoutSession = {
    ...mockWorkoutSessions[idx],
    sets: [...mockWorkoutSessions[idx].sets, set],
  }
  mockWorkoutSessions = mockWorkoutSessions.map((s, i) => (i === idx ? updated : s))
  return set
}

export function mockCreateNutritionLog(
  memberId: string,
  input: CreateNutritionLogInput,
): ApiNutritionLog {
  const log: ApiNutritionLog = {
    id: input.id ?? newId(),
    member_id: memberId,
    at: input.at,
    band: input.band,
    meals: input.meals ?? [],
    source: input.source,
  }
  mockNutritionLogs = [...mockNutritionLogs, log]
  return log
}

export function mockListNutritionLogs(memberId: string): ApiNutritionLog[] {
  return mockNutritionLogs
    .filter((n) => n.member_id === memberId)
    .sort((a, b) => b.at.localeCompare(a.at))
}

// ---------------------------------------------------------------------
// Staff accounts. Seeded from the existing coach roster plus one manager
// so the screen has something to show; mock mode has no real login, so
// there's no "current user" to exclude from the list.
// ---------------------------------------------------------------------

let mockStaff: ApiStaff[] = [
  // super_admin, not manager: onboarding.py grants the gym's first account
  // that role, and a roster without one cannot demonstrate the floor that
  // stops a gym being left with nobody who can grant access.
  { id: 'staff-kassem', username: 'kassem', name: 'Kassem Shehady', role: 'super_admin' },
  ...seedCoaches.map((c) => ({
    id: `staff-${c.id}`,
    username: c.id.replace('c-', ''),
    name: toBilingual(c.name).en,
    role: 'coach',
  })),
]

export function mockListStaff(): ApiStaff[] {
  return mockStaff
}

export function mockCreateStaff(input: CreateStaffInput): ApiStaff {
  if (mockStaff.some((s) => s.username === input.username)) {
    throw new ApiError(409, 'Username already taken')
  }
  const staff: ApiStaff = { id: newId(), username: input.username, name: input.name, role: input.role }
  mockStaff = [...mockStaff, staff]
  return staff
}

// ---------------------------------------------------------------------
// Phase 6 stage 5/6 — changing and revoking access. These mirror
// app/api/staff.py's guards rather than just mutating the array: a demo
// that lets the owner do something the server refuses teaches the wrong
// thing, and the screen branches on the 409 either way.
// ---------------------------------------------------------------------

function mockStaffOr404(staffId: string): ApiStaff {
  const found = mockStaff.find((s) => s.id === staffId)
  if (!found) throw new ApiError(404, 'No staff member with that id at this gym')
  return found
}

function mockRefuseLastSuperAdmin(staff: ApiStaff, becoming: StaffRole | null): void {
  if (staff.role !== 'super_admin' || becoming === 'super_admin') return
  const others = mockStaff.filter((s) => s.id !== staff.id && s.role === 'super_admin')
  if (others.length === 0) {
    throw new ApiError(409, 'This gym would be left with no super_admin')
  }
}

export function mockUpdateStaffRole(staffId: string, role: StaffRole): ApiStaff {
  const staff = mockStaffOr404(staffId)
  mockRefuseLastSuperAdmin(staff, role)
  const updated = { ...staff, role }
  mockStaff = mockStaff.map((s) => (s.id === staffId ? updated : s))
  return updated
}

export function mockRevokeStaffAccess(staffId: string): void {
  const staff = mockStaffOr404(staffId)
  mockRefuseLastSuperAdmin(staff, null)
  mockStaff = mockStaff.filter((s) => s.id !== staffId)
}

export function mockResetStaffPassword(staffId: string): StaffPasswordOut {
  const staff = mockStaffOr404(staffId)
  // Not crypto — mock mode never authenticates anyone. The real password
  // comes from app/security/hashing.py's generate_password.
  const password = Math.random().toString(16).slice(2, 10)
  // The roster has no phone numbers; the live endpoint reads the real one
  // off staff_users. A placeholder keeps the wa.me link shape intact.
  return { username: staff.username, password, phone: '+96170000000' }
}

// ---------------------------------------------------------------------
// Phase 4 stage 4 — a member's own food log. Seeded with one entry so the
// screen isn't empty on first load, matching the old state.food seed.
// photo_key holds the raw data URL in mock mode (there's no real object
// store to round-trip through) — real API mode never sees that shape,
// since app/api/food_entries.py only ever hands back opaque storage keys.
// ---------------------------------------------------------------------

let mockFoodEntries: ApiFoodEntry[] = [
  {
    id: 'food-seed-1',
    at: new Date().toISOString(),
    label: 'Eggs with bread',
    kcal: 340,
    protein: 22,
    carbs: 34,
    fat: 12,
    source: 'manual',
    photo_key: null,
    estimate: null,
  },
]

export function mockListFoodEntries(): ApiFoodEntry[] {
  return mockFoodEntries
}

export function mockCreateFoodEntry(input: CreateFoodEntryInput): ApiFoodEntry {
  const entry: ApiFoodEntry = {
    id: newId(),
    at: new Date().toISOString(),
    label: input.label,
    kcal: input.kcal,
    protein: input.protein,
    carbs: input.carbs,
    fat: input.fat,
    source: input.source,
    photo_key: input.photo_key ?? null,
    estimate: input.estimate ?? null,
  }
  mockFoodEntries = [...mockFoodEntries, entry]
  return entry
}

export function mockDeleteFoodEntry(entryId: string): void {
  mockFoodEntries = mockFoodEntries.filter((f) => f.id !== entryId)
}

/** Mock branch of estimateFoodEntry — no photo to actually look at, so it
 * picks one of foodGuesses at random, same behavior Food.tsx's onPhoto()
 * had inline before Phase 5 stage 8 moved the vision call server-side. */
export function mockEstimateFoodEntry(lang: Lang): ApiFoodEstimate {
  const guess = foodGuesses[Math.floor(Math.random() * foodGuesses.length)]
  return { label: text(guess.label, lang), kcal: guess.kcal, protein: guess.protein, carbs: guess.carbs, fat: guess.fat }
}

// ---------------------------------------------------------------------
// Phase 4 stage 5 — a member's own progress photos (decision 11). No
// per-member scoping in mock mode (there's only ever one signed-in
// member), matching mockFoodEntries. photo_key holds the raw data URL,
// same reasoning as mockCreateFoodEntry.
// ---------------------------------------------------------------------

let mockProgressPhotos: ApiProgressPhoto[] = []

export function mockListProgressPhotos(): ApiProgressPhoto[] {
  return mockProgressPhotos
}

export function mockCreateProgressPhoto(photoKey: string): ApiProgressPhoto {
  const photo: ApiProgressPhoto = {
    id: newId(),
    at: new Date().toISOString(),
    photo_key: photoKey,
    shared_with_coach: false,
  }
  mockProgressPhotos = [photo, ...mockProgressPhotos]
  return photo
}

export function mockUpdateProgressPhoto(photoId: string, sharedWithCoach: boolean): ApiProgressPhoto {
  const existing = mockProgressPhotos.find((p) => p.id === photoId)
  if (!existing) throw new Error('Progress photo not found')
  const updated: ApiProgressPhoto = { ...existing, shared_with_coach: sharedWithCoach }
  mockProgressPhotos = mockProgressPhotos.map((p) => (p.id === photoId ? updated : p))
  return updated
}

export function mockDeleteProgressPhoto(photoId: string): void {
  mockProgressPhotos = mockProgressPhotos.filter((p) => p.id !== photoId)
}

export function mockListSharedPhotos(): ApiProgressPhoto[] {
  return mockProgressPhotos.filter((p) => p.shared_with_coach)
}

// ---------------------------------------------------------------------
// Phase 4 stage 6 — coaches, the class schedule, and a member's own
// bookings/attendance. Coaches and classes are read straight from the
// seed data (no mutation ever touches them in mock mode, staff or
// member); bookings are seeded from mocks/data's `bookings`, filtered to
// currentMemberId — mock mode only ever represents the one signed-in
// member, same reasoning as mockFoodEntries/mockProgressPhotos.
// ---------------------------------------------------------------------

export function mockListCoaches(): ApiCoach[] {
  return seedCoaches.map((c) => ({ id: c.id, name: toBilingual(c.name), speciality: toBilingual(c.speciality) }))
}

export function mockListClasses(): ApiGymClass[] {
  return seedClasses.map((c) => ({
    id: c.id,
    title: toBilingual(c.title),
    coach_id: c.coachId,
    weekdays: c.weekdays,
    time: c.time,
    duration_min: c.durationMin,
  }))
}

let mockBookings: ApiBooking[] = seedBookings
  .filter((b) => b.memberId === currentMemberId)
  .map((b) => ({ id: b.id, coach_id: b.coachId, date: b.date, time: b.time, kind: b.kind, status: b.status }))

export function mockListMyBookings(): ApiBooking[] {
  return mockBookings
}

export function mockCreateBooking(input: CreateBookingInput): ApiBooking {
  const booking: ApiBooking = {
    id: newId(),
    coach_id: input.coach_id,
    date: input.date,
    time: input.time,
    kind: input.kind,
    status: 'booked',
  }
  mockBookings = [...mockBookings, booking]
  return booking
}

export function mockCancelBooking(bookingId: string): ApiBooking {
  const existing = mockBookings.find((b) => b.id === bookingId)
  if (!existing) throw new Error('Booking not found')
  const updated: ApiBooking = { ...existing, status: 'cancelled' }
  mockBookings = mockBookings.map((b) => (b.id === bookingId ? updated : b))
  return updated
}

export function mockListMyAttendance(): ApiAttendanceDay[] {
  return seedAttendance.filter((a) => a.memberId === currentMemberId).map((a) => ({ date: a.date }))
}

let mockAiDrafts: ApiAiDraft[] = seedAiDrafts.map((d) => ({
  id: d.id,
  member_id: d.memberId,
  created_by:
    d.kind === 'plan' ? 'coach_plan' : d.kind === 'nutrition' ? 'coach_nutrition' : 'coach_recommendation',
  kind: d.kind,
  headline: d.headline,
  body: d.body,
  reason: d.reason,
  payload: d.payload ?? null,
  status: d.status,
  decided_at: null,
  original: null,
}))

export function mockListAiDrafts(): ApiAiDraft[] {
  return mockAiDrafts
}

function mockDecideAiDraft(
  draftId: string,
  status: 'approved' | 'rejected',
  edits?: ApproveAiDraftInput,
): ApiAiDraft {
  const existing = mockAiDrafts.find((d) => d.id === draftId)
  if (!existing) throw new Error('Draft not found')
  if (existing.status !== 'pending') throw new Error('Draft already decided')

  const edited = edits ? Object.values(edits).some((v) => v !== undefined) : false
  const original =
    edited && !existing.original ? { headline: existing.headline, body: existing.body } : existing.original

  const updated: ApiAiDraft = {
    ...existing,
    headline: edits?.headline ?? existing.headline,
    body: edits?.body ?? existing.body,
    reason: edits?.reason ?? existing.reason,
    payload: edits?.payload ?? existing.payload,
    status,
    decided_at: new Date().toISOString(),
    original,
  }

  if (status === 'approved' && updated.payload?.type === 'calorie_target_update') {
    mockDailyKcalTargets.set(updated.member_id, updated.payload.daily_kcal_target as number)
  }

  mockAiDrafts = mockAiDrafts.map((d) => (d.id === draftId ? updated : d))
  return updated
}

export function mockApproveAiDraft(draftId: string, edits?: ApproveAiDraftInput): ApiAiDraft {
  return mockDecideAiDraft(draftId, 'approved', edits)
}

export function mockRejectAiDraft(draftId: string): ApiAiDraft {
  return mockDecideAiDraft(draftId, 'rejected')
}

/** Mock branch of generateAiDraft — no LLM to call, so it writes a
 * plausible, always-bilingual pending draft straight into the same
 * mockAiDrafts list the inbox above already reads (decision 31: one
 * mechanism, coach-triggered or chat-triggered). `lang` isn't needed here
 * since these fixtures are genuinely bilingual already, unlike a model's
 * single-language reply. */
export function mockGenerateAiDraft(memberId: string, kind: AiDraftKind): ApiAiDraft {
  const member = seedMembers.find((m) => m.id === memberId)
  const base = {
    id: newId(), member_id: memberId, status: 'pending' as const,
    decided_at: null, original: null,
  }

  let draft: ApiAiDraft
  if (kind === 'plan') {
    const picks = mockExercises.filter((e) => e.active).slice(0, 4)
    draft = {
      ...base,
      created_by: 'generate_plan',
      kind: 'plan',
      headline: { ar: 'خطة مقترحة من الذكاء الاصطناعي', en: 'AI-suggested plan' },
      body: {
        ar: 'خطة بـ٤ تمارين بالاعتماد على هدف العضو ومستواه.',
        en: "A 4-exercise plan based on the member's goal and level.",
      },
      reason: {
        ar: 'مبني على هدف العضو ومستواه وجلساته الأخيرة.',
        en: "Based on the member's goal, level, and recent sessions.",
      },
      payload: {
        type: 'program_exercise_update',
        title: { ar: 'برنامج مقترح', en: 'Suggested program' },
        exercises: picks.map((e) => ({
          exercise_id: e.id, sets: 3, reps: { ar: '٨-١٢', en: '8-12' }, target_weight_kg: null,
        })),
      },
    }
  } else if (kind === 'nutrition') {
    const weight = member?.weightKg ?? 75
    const target = Math.max(1200, Math.round((weight * 28) / 50) * 50)
    draft = {
      ...base,
      created_by: 'generate_nutrition',
      kind: 'nutrition',
      headline: { ar: 'هدف سعرات جديد مقترح', en: 'New suggested calorie target' },
      body: {
        ar: `اقتراح ${target} سعرة باليوم بالاعتماد على وزن العضو وهدفه.`,
        en: `Suggesting ${target} kcal/day based on the member's weight and goal.`,
      },
      reason: {
        ar: 'محسوب من وزن العضو وهدفه الحالي.',
        en: "Calculated from the member's current weight and goal.",
      },
      payload: { type: 'calorie_target_update', daily_kcal_target: target },
    }
  } else {
    draft = {
      ...base,
      created_by: 'generate_tip',
      kind: 'tip',
      headline: { ar: 'نصيحة سريعة', en: 'Quick tip' },
      body: {
        ar: 'شرب مي أكتر بأيام التمرين ممكن يحسّن الأداء.',
        en: 'Drinking more water on training days may help performance.',
      },
      reason: {
        ar: 'بناءً على آخر الجلسات المسجلة.',
        en: 'Based on recently logged sessions.',
      },
      payload: null,
    }
  }

  mockAiDrafts = [draft, ...mockAiDrafts]
  return draft
}

/** The mock branch of sendChatMessage — calls the existing replyTo()
 * unchanged, so mock-mode chat behavior is bit-for-bit identical to
 * before Phase 5 stage 7 closed the `fetch`-in-a-feature-file boundary
 * violation mocks/agents.ts's replyTo() used to be called through
 * directly. */
export function mockSendChatMessage(agent: AgentId, message: string, lang: Lang): ApiChatReply {
  const reply = replyTo(agent, message, lang)
  return {
    text: reply.body,
    food: reply.food
      ? {
          label: text(reply.food.label, lang),
          kcal: reply.food.kcal,
          protein: reply.food.protein,
          carbs: reply.food.carbs,
          fat: reply.food.fat,
        }
      : null,
    draft: Boolean(reply.draft),
    referred: false,
  }
}

// ---------------------------------------------------------------------
// Phase 6 — the owner dashboard (app/api/analytics.py).
//
// Mock mode has no subscription history: a member carries one `endsAt` and
// a status, not the renewal chain the real endpoint walks. So this
// approximates rather than mirrors — a period that has already ended counts
// as fallen due, and a member the seed still marks `paid` counts as having
// renewed it. The bucketing and the null-vs-zero rate do match the server
// exactly, since those are what the screen branches on.
//
// Derived from the seed rather than frozen as a literal, so registering a
// member in the demo moves the numbers the way the live screen would.
// ---------------------------------------------------------------------

const DAY_MS = 86_400_000

/** Midnight UTC for a bare `YYYY-MM-DD`, so comparisons never drift by a
 * timezone offset the way `new Date(iso)` arithmetic can. */
const dayMs = (iso: string) => Date.parse(`${iso}T00:00:00Z`)

const todayMs = () => {
  const now = new Date()
  return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
}

/** The Monday of each of the last `weeks` weeks, oldest first — the same
 * series week_starts() produces in app/domain/analytics.py. JS counts
 * Sunday as 0, hence the shift. */
function mockWeekStarts(weeks: number): number[] {
  const today = todayMs()
  const monday = today - ((new Date(today).getUTCDay() + 6) % 7) * DAY_MS
  return Array.from({ length: weeks }, (_, i) => monday - (weeks - 1 - i) * 7 * DAY_MS)
}

type DuePeriod = { dueAt: number; priceUsd: number; renewed: boolean }

function mockCollectionStats(periods: DuePeriod[]): ApiCollectionWindow {
  const onTime = periods.filter((p) => p.renewed)
  return {
    due_count: periods.length,
    on_time_count: onTime.length,
    on_time_rate: periods.length
      ? Math.round((onTime.length / periods.length) * 10_000) / 10_000
      : null,
    collected_usd: onTime.reduce((sum, p) => sum + p.priceUsd, 0),
    uncollected_usd: periods
      .filter((p) => !p.renewed)
      .reduce((sum, p) => sum + p.priceUsd, 0),
  }
}

/** Each member's most recent attendance on or before `cutoff`, or null. */
function mockLastVisitBefore(memberId: string, cutoff: number): number | null {
  const days = seedAttendance
    .filter((a) => a.memberId === memberId)
    .map((a) => dayMs(a.date))
    .filter((d) => d <= cutoff)
  return days.length ? Math.max(...days) : null
}

function mockLapsedCount(members: MockMember[], asOf: number, minDays: number): number {
  return members.filter((m) => {
    const last = mockLastVisitBefore(m.id, asOf)
    return last === null || (asOf - last) / DAY_MS >= minDays
  }).length
}

export function mockAnalyticsSummary(weeks: number, lapsedAfterDays: number): ApiAnalyticsSummary {
  const span = weeks * 7 * DAY_MS
  const today = todayMs()
  const windowStart = today - span
  const previousStart = windowStart - span

  const periods: DuePeriod[] = mockMembers
    .map((m) => ({
      dueAt: dayMs(m.endsAt),
      // Plan price, not owedUsd: the server measures a period by what it
      // was worth, and owedUsd answers the different question of what the
      // member owes right now (decision 17).
      priceUsd: findPlan(m.planId)?.priceUsd ?? 0,
      renewed: m.status === 'paid',
    }))
    .filter((p) => p.dueAt >= previousStart && p.dueAt <= today)

  const current = periods.filter((p) => p.dueAt >= windowStart)
  const starts = mockWeekStarts(weeks)

  return {
    weeks,
    window_start: new Date(windowStart).toISOString().slice(0, 10),
    previous_start: new Date(previousStart).toISOString().slice(0, 10),
    collection: mockCollectionStats(current),
    collection_previous: mockCollectionStats(periods.filter((p) => p.dueAt < windowStart)),
    lapsed_now: mockLapsedCount(mockMembers, today, lapsedAfterDays),
    // Only members who had already joined — measuring today's roster
    // against a date before they existed would invent churn.
    lapsed_at_window_start: mockLapsedCount(
      mockMembers.filter((m) => dayMs(m.joinedAt) < windowStart),
      windowStart,
      lapsedAfterDays,
    ),
    new_members: mockMembers.filter((m) => dayMs(m.joinedAt) >= windowStart).length,
    new_members_previous: mockMembers.filter(
      (m) => dayMs(m.joinedAt) >= previousStart && dayMs(m.joinedAt) < windowStart,
    ).length,
    active_members: mockMembers.length,
    series: starts.map((start, i) => {
      const next = starts[i + 1] ?? Infinity
      const stats = mockCollectionStats(
        current.filter((p) => p.dueAt >= start && p.dueAt < next),
      )
      return {
        week_start: new Date(start).toISOString().slice(0, 10),
        on_time_rate: stats.on_time_rate,
        collected_usd: stats.collected_usd,
      }
    }),
  }
}
