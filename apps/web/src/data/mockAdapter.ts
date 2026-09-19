/**
 * Adapts src/mocks/data.ts into the exact same shape the live API returns,
 * so feature components read one type (src/data/types.ts) regardless of
 * whether VITE_API_URL is set. Mutations write to a session-only in-memory
 * copy — mock mode has never persisted across reloads, and this keeps it
 * that way; that gap is exactly what running the gym on the real API is
 * for.
 */
import {
  attendance as seedAttendance,
  bookings as seedBookings,
  checkIns as seedCheckIns,
  classes as seedClasses,
  coaches as seedCoaches,
  currentMemberId,
  dayPlans as seedDayPlans,
  daysSinceVisit,
  findPlan,
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
import { waLink } from '@/lib/whatsapp'
import type { Text } from '@/lib/format'
import type {
  ApiAttendanceDay,
  ApiBooking,
  ApiCheckIn,
  ApiCoach,
  ApiExercise,
  ApiFoodEntry,
  ApiGymClass,
  ApiLapsedMember,
  ApiMachine,
  ApiMember,
  ApiMemberDetail,
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
  FinishWorkoutSessionInput,
  LogSetInput,
  ReplaceProgramExercisesInput,
  RecordPaymentInput,
  UpdateExerciseInput,
  UpdateProgramInput,
  UpdateVideoInput,
} from './types'

let mockMembers: MockMember[] = seedMembers.map((m) => ({ ...m }))
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
      injuries: m.injuries,
      days_per_week: m.daysPerWeek,
      job: m.job,
      sleep_hours: m.sleepHours,
      weight_trend: m.weightTrend,
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
    injuries: [],
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
  { id: 'staff-kassem', username: 'kassem', name: 'Kassem Shehady', role: 'manager' },
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
    throw new Error('Username already taken')
  }
  const staff: ApiStaff = { id: newId(), username: input.username, name: input.name, role: input.role }
  mockStaff = [...mockStaff, staff]
  return staff
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
