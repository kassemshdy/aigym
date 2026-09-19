/**
 * Mirrors apps/api's pydantic response models exactly (app/api/members.py,
 * app/api/plans.py). Both the live client (client.ts) and the mock adapter
 * (mockAdapter.ts) return this same shape, so feature components read one
 * type regardless of whether VITE_API_URL is set.
 */

export type DuesStatus = 'paid' | 'soon' | 'due'

export interface ApiDues {
  status: DuesStatus
  owed_usd: number
}

export interface ApiPlan {
  id: string
  name: { ar: string; en: string }
  price_usd: number
  days: number
}

export interface ApiMember {
  id: string
  name: string
  name_en: string
  phone: string
  joined_at: string
  plan_id: string | null
  plan_name: { ar: string; en: string } | null
  ends_at: string | null
  last_visit: string | null
  dues: ApiDues | null
}

export interface ApiMemberProfile {
  goal: string
  level: string
  height_cm: number
  weight_kg: number
  body_fat: number | null
  injuries: unknown[]
  days_per_week: number
  job: string
  sleep_hours: number
  weight_trend: number[]
}

export interface ApiMemberDetail extends ApiMember {
  profile: ApiMemberProfile | null
}

export interface ApiLapsedMember {
  id: string
  name: string
  name_en: string
  phone: string
  last_visit: string | null
  days_since_visit: number | null
}

export interface CreateMemberInput {
  name: string
  name_en: string
  phone: string
  plan_id: string
  goal: 'lose' | 'gain' | 'strength' | 'health'
  level: 'new' | 'mid' | 'strong'
  height_cm: number
  weight_kg: number
  body_fat: number | null
  injuries: unknown[]
  days_per_week: number
  job: 'desk' | 'active' | 'shift'
  sleep_hours: number
}

export interface RecordPaymentInput {
  amount_usd: number
  method: string
  plan_id?: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
}

export interface ApiCheckIn {
  id: string
  member_id: string
  at: string
  status: string
}

export interface ApiPayment {
  id: string
  member_id: string
  member_name: string
  member_name_en: string
  amount_usd: number
  at: string
  method: string
}

export interface StaffPasswordResetResult {
  sent: boolean
}

// ---------------------------------------------------------------------
// Phase 3 — the floor: exercises, programs, sessions/sets, nutrition.
// Mirrors app/api/{exercises,programs,sessions,nutrition}.py exactly.
// ---------------------------------------------------------------------

export interface ApiExercise {
  id: string
  name: { ar: string; en: string }
  muscle_group: string
  video_url: string | null
  active: boolean
}

export interface CreateExerciseInput {
  name: { ar: string; en: string }
  muscle_group: string
  video_url?: string | null
}

export interface UpdateExerciseInput {
  video_url?: string | null
}

export interface ApiMachine {
  id: string
  name: { ar: string; en: string }
  area: string
}

// ---------------------------------------------------------------------
// Phase 4 stage 3 — the member video library. Mirrors app/api/videos.py.
// ---------------------------------------------------------------------

export interface ApiVideo {
  id: string
  title: { ar: string; en: string }
  provider: string
  external_id: string
  muscle_group: string
  equipment: string
  seconds: number
  view_count: number
  active: boolean
}

export interface CreateVideoInput {
  title: { ar: string; en: string }
  provider: string
  external_id: string
  muscle_group: string
  equipment: string
  seconds: number
}

export interface UpdateVideoInput {
  title?: { ar: string; en: string }
  muscle_group?: string
  equipment?: string
  active?: boolean
}

export interface ApiProgramExercise {
  id: string
  exercise_id: string
  exercise_name: { ar: string; en: string }
  order_index: number
  sets: number
  reps: { ar: string; en: string }
  target_weight_kg: number | null
}

export interface ApiProgram {
  id: string
  member_id: string
  title: { ar: string; en: string }
  archived_at: string | null
  exercises: ApiProgramExercise[]
}

export interface ProgramExerciseInput {
  exercise_id: string
  sets: number
  reps: { ar: string; en: string }
  target_weight_kg?: number | null
}

export interface CreateProgramInput {
  title: { ar: string; en: string }
  exercises: ProgramExerciseInput[]
}

export interface ReplaceProgramExercisesInput {
  exercises: ProgramExerciseInput[]
}

export interface UpdateProgramInput {
  title?: { ar: string; en: string }
  archived?: boolean
}

export interface ApiWorkoutSet {
  id: string
  exercise_id: string
  set_number: number
  reps: number
  weight_kg: number
  machine_id: string | null
  at: string
}

export interface ApiWorkoutSession {
  id: string
  member_id: string
  check_in_id: string | null
  started_at: string
  finished_at: string | null
  effort_band: string | null
  sets: ApiWorkoutSet[]
}

export interface CreateWorkoutSessionInput {
  id?: string
  member_id: string
  check_in_id?: string | null
  started_at: string
}

export interface FinishWorkoutSessionInput {
  finished_at: string
  effort_band?: string | null
}

export interface LogSetInput {
  id?: string
  exercise_id: string
  set_number: number
  reps: number
  weight_kg: number
  machine_id?: string | null
  at: string
}

export interface ApiTodayExercise {
  program_exercise_id: string
  exercise_id: string
  exercise_name: { ar: string; en: string }
  order_index: number
  sets: number
  reps: { ar: string; en: string }
  target_weight_kg: number | null
  last_weight_kg: number | null
}

export interface ApiTodayWorkout {
  program_id: string | null
  program_title: { ar: string; en: string } | null
  exercises: ApiTodayExercise[]
  open_session_id: string | null
}

export interface ApiNutritionLog {
  id: string
  member_id: string
  at: string
  band: string
  meals: unknown[]
  source: string
}

export interface CreateNutritionLogInput {
  id?: string
  at: string
  band: string
  meals?: unknown[]
  source: string
}

// ---------------------------------------------------------------------
// Staff accounts (decision 21). A manager may only create role "coach";
// the server enforces this too — this is UX, not the real gate.
// ---------------------------------------------------------------------

export interface ApiStaff {
  id: string
  username: string
  name: string
  role: string
}

export interface CreateStaffInput {
  username: string
  password: string
  name: string
  phone: string
  role: 'manager' | 'coach' | 'super_admin'
}
