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

/** Mirrors app/schemas/injuries.py's MemberInjury. body_part is a
 * canonical key the guardrail logic (Phase 5 stage 3) can reason about —
 * not free text (see docs/DECISIONS.md, decision 30). */
export type InjuryBodyPart =
  | 'lower_back'
  | 'knee_left'
  | 'knee_right'
  | 'shoulder_left'
  | 'shoulder_right'
  | 'hip'
  | 'neck'
  | 'wrist'
  | 'ankle'
  | 'other'

export interface ApiMemberInjury {
  body_part: InjuryBodyPart
  note: { ar: string; en: string }
  severity: 'mild' | 'moderate' | 'severe' | null
}

export interface ApiMemberProfile {
  goal: string
  level: string
  height_cm: number
  weight_kg: number
  body_fat: number | null
  injuries: ApiMemberInjury[]
  days_per_week: number
  job: string
  sleep_hours: number
  weight_trend: number[]
  /** Set only by an approved ai_plan_drafts row (kind='nutrition') — null
   * until then. See app/models/people.py. */
  daily_kcal_target: number | null
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
  injuries: ApiMemberInjury[]
  days_per_week: number
  job: 'desk' | 'active' | 'shift'
  sleep_hours: number
}

export interface UpdateMyProfileInput {
  goal?: 'lose' | 'gain' | 'strength' | 'health'
  level?: 'new' | 'mid' | 'strong'
  height_cm?: number
  weight_kg?: number
  body_fat?: number | null
  injuries?: ApiMemberInjury[]
  days_per_week?: number
  job?: 'desk' | 'active' | 'shift'
  sleep_hours?: number
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

/** Flat, not a hierarchy — `super_admin` is never implied by `manager`.
 * Mirrors app/deps.py's require_role, where every call site has to list
 * super_admin explicitly or silently lock the gym owner out. */
export type StaffRole = 'super_admin' | 'manager' | 'coach'

// ---------------------------------------------------------------------
// Phase 6 stage 8/9 — the gym's own identity. Mirrors app/api/gyms.py.
// Branding only: that response deliberately carries no billing fields,
// and widening it is a failing test on the server side.
// ---------------------------------------------------------------------

export interface ApiGym {
  id: string
  name: { ar: string; en: string }
  slug: string
  /** null until the gym uploads one; the client falls back to the bundled
   * logo rather than showing a gap. */
  logo_key: string | null
}

export interface UpdateGymInput {
  name?: { ar: string; en: string }
  /** Explicit null clears the logo. The server reads which fields were
   * present, so omitting this leaves the logo alone. */
  logo_key?: string | null
}

/** Both languages required, matching app/api/plans.py's BilingualName: a
 * plan saved with only English renders as a blank name on the Arabic side
 * of the app rather than failing anywhere visible. */
export interface CreatePlanInput {
  name: { ar: string; en: string }
  price_usd: number
  days: number
}

export interface UpdatePlanInput {
  name?: { ar: string; en: string }
  price_usd?: number
  days?: number
}

export interface CreateStaffInput {
  username: string
  password: string
  name: string
  phone: string
  role: StaffRole
}

/** A password this service just minted, handed back so a human can send it
 * over a wa.me link (decision 26) rather than the WhatsApp Business API. */
export interface StaffPasswordOut {
  username: string
  password: string
  /** Included so the caller can hand it over on a wa.me link without a
   * second round trip. GET /staff deliberately omits it. */
  phone: string
}

// ---------------------------------------------------------------------
// Phase 4 stage 4 — a member's own food log. Mirrors
// app/api/food_entries.py. Scoped to the signed-in member on the server
// (claims.subject_id), never a member id in the URL.
// ---------------------------------------------------------------------

export interface ApiFoodEntry {
  id: string
  at: string
  label: string
  kcal: number
  protein: number
  carbs: number
  fat: number
  source: 'photo' | 'manual' | 'agent'
  photo_key: string | null
  estimate: { kcal: number; protein: number; carbs: number; fat: number } | null
}

export interface CreateFoodEntryInput {
  label: string
  kcal: number
  protein: number
  carbs: number
  fat: number
  source: 'photo' | 'manual' | 'agent'
  photo_key?: string | null
  estimate?: { kcal: number; protein: number; carbs: number; fat: number } | null
}

export interface MediaUploadResult {
  key: string
}

/** Mirrors app/api/food_entries.py's FoodEstimateOut (Phase 5 stage 8) — a
 * single best-guess reading of an already-uploaded photo. Never a write;
 * the member still confirms or corrects it before createFoodEntry runs
 * (decision 12). */
export interface ApiFoodEstimate {
  label: string
  kcal: number
  protein: number
  carbs: number
  fat: number
}

// ---------------------------------------------------------------------
// Phase 4 stage 5 — a member's own progress photos (decision 11). Mirrors
// app/api/progress_photos.py. Member-scoped writes use claims.subject_id
// on the server, never a member id in the URL; the one staff-facing read
// (GET /members/{id}/shared-photos) only ever returns shared_with_coach
// rows — enforced server-side, not a UI filter.
// ---------------------------------------------------------------------

export interface ApiProgressPhoto {
  id: string
  at: string
  photo_key: string
  shared_with_coach: boolean
}

// ---------------------------------------------------------------------
// Phase 4 stage 6 — coaches, the fixed class schedule, and a member's own
// bookings/attendance. Mirrors app/api/booking.py. Coaches and classes
// are readable by any authenticated caller; bookings and attendance are
// member-scoped on the server (claims.subject_id), never a URL param.
// ---------------------------------------------------------------------

export interface ApiCoach {
  id: string
  name: { ar: string; en: string }
  speciality: { ar: string; en: string }
}

export interface ApiGymClass {
  id: string
  title: { ar: string; en: string }
  coach_id: string
  /** 0 = Sunday, matching Date.getDay() */
  weekdays: number[]
  time: string
  duration_min: number
}

export interface ApiBooking {
  id: string
  coach_id: string
  date: string
  time: string
  kind: 'private' | 'intro'
  status: 'booked' | 'cancelled' | 'done'
}

export interface CreateBookingInput {
  coach_id: string
  date: string
  time: string
  kind: 'private' | 'intro'
}

export interface ApiAttendanceDay {
  date: string
}

// ---------------------------------------------------------------------
// Phase 5 — the AI layer. Mirrors app/api/ai_drafts.py. Decision 10: an
// assistant or a coach's "generate" action never touches a member's
// program or calorie target directly — it writes a pending row here, and
// nothing is applied until a coach approves it.
// ---------------------------------------------------------------------

export type AiDraftKind = 'plan' | 'nutrition' | 'tip'
export type AiDraftStatus = 'pending' | 'approved' | 'rejected'

export interface ApiAiDraft {
  id: string
  member_id: string
  created_by: string
  kind: AiDraftKind
  headline: { ar: string; en: string }
  body: { ar: string; en: string }
  reason: { ar: string; en: string }
  payload: Record<string, unknown> | null
  status: AiDraftStatus
  decided_at: string | null
  original: { headline: { ar: string; en: string }; body: { ar: string; en: string } } | null
}

export interface ApproveAiDraftInput {
  headline?: { ar: string; en: string }
  body?: { ar: string; en: string }
  reason?: { ar: string; en: string }
  payload?: Record<string, unknown>
}

// ---------------------------------------------------------------------
// Phase 5 stage 7 — the member chat assistants. Mirrors app/api/chat.py.
// No server-side chat-history table (decision 29): the client resends
// enough turn history for a stateless per-turn call.
// ---------------------------------------------------------------------

export type ChatAgent = 'nutrition' | 'training'

export interface ChatTurnInput {
  role: 'user' | 'assistant'
  text: string
}

export interface ApiFoodProposal {
  label: string
  kcal: number
  protein: number
  carbs: number
  fat: number
}

export interface ApiChatReply {
  text: string
  food: ApiFoodProposal | null
  /** Collapsed to a bool on the wire — the draft's own content lives in
   * the coach's inbox (ApiAiDraft), not here. */
  draft: boolean
  referred: boolean
}

// ---------------------------------------------------------------------
// Phase 6 — the owner dashboard. Mirrors app/api/analytics.py. Every
// figure carries its preceding equal-length window because the GTM
// guarantee is a before/after claim ("recovers more in missed dues than
// we charge in the first 90 days") — one number on its own settles
// nothing.
// ---------------------------------------------------------------------

export interface ApiCollectionWindow {
  due_count: number
  on_time_count: number
  /** null, not 0, when nothing fell due in the window. "No renewals were
   * due" and "every renewal was missed" are different facts, and the
   * screen has to be able to tell them apart. */
  on_time_rate: number | null
  collected_usd: number
  uncollected_usd: number
}

export interface ApiAnalyticsWeek {
  /** The Monday the week starts on, oldest first across the series. */
  week_start: string
  on_time_rate: number | null
  collected_usd: number
}

export interface ApiAnalyticsSummary {
  weeks: number
  window_start: string
  previous_start: string
  collection: ApiCollectionWindow
  collection_previous: ApiCollectionWindow
  lapsed_now: number
  lapsed_at_window_start: number
  new_members: number
  new_members_previous: number
  active_members: number
  /** Pre-bucketed by the server so the client does no date arithmetic. */
  series: ApiAnalyticsWeek[]
}


// ---------------------------------------------------------------------
// Phase 6 stage 10/11 — importing a gym's existing members. Mirrors
// app/api/member_import.py. The file is parsed on the server, so these
// shapes are the only thing the client knows about a CSV: there is no
// second parser here to drift from the one that does the writing.
// ---------------------------------------------------------------------

export interface ApiImportRow {
  /** 1-based and counting the header, so it is the line the gym owner
   * sees in their own spreadsheet — blank lines included. */
  line: number
  name: string
  name_en: string
  /** Already normalized to +961…, so the manager approves the number that
   * will actually be stored rather than what they typed. */
  phone: string
  /** The plan name as written in the file, kept so a row that failed to
   * match one can show what it said. */
  plan: string
  plan_id: string | null
  ends_at: string | null
  /** Stable keys (`phone_invalid`, `already_a_member`, …), never
   * sentences — the client renders them through t(). */
  errors: string[]
}

export interface ApiImportPreview {
  rows: ApiImportRow[]
  /** Non-empty means the header had no name or phone column, and `rows`
   * is empty: guessing which column held the number is how a gym imports
   * 300 members under the wrong ones. */
  missing_columns: string[]
  truncated: boolean
  ready: number
  blocked: number
}

export interface CommitImportRow {
  line: number
  name: string
  name_en: string
  phone: string
  plan_id: string
  ends_at: string | null
}
