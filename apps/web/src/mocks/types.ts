import type { Text } from '@/lib/format'

export type Role = 'manager' | 'coach' | 'member'

/** Derived on the server in Phase 2 from end date + latest payment. Never stored. */
export type DuesStatus = 'paid' | 'soon' | 'due'

export interface Plan {
  id: string
  name: { ar: string; en: string }
  priceUsd: number
  days: number
}

export interface Member {
  id: string
  name: string
  nameEn: string
  phone: string
  planId: string
  joinedAt: string
  endsAt: string
  status: DuesStatus
  owedUsd: number
  lastVisit: string | null
  goal: 'lose' | 'gain' | 'strength' | 'health'
  level: 'new' | 'mid' | 'strong'
  heightCm: number
  weightKg: number
  bodyFat: number | null
  injuries: Text[]
  daysPerWeek: number
  job: 'desk' | 'active' | 'shift'
  sleepHours: number
  weightTrend: number[]
}

export interface Payment {
  id: string
  memberId: string
  amountUsd: number
  at: string
  method: 'cash' | 'transfer'
  by: string
}

export interface CheckIn {
  id: string
  memberId: string
  at: string
  status: 'waiting' | 'training' | 'done'
}

export interface PrescribedExercise {
  id: string
  name: { ar: string; en: string }
  sets: number
  reps: Text
  lastWeightKg: number | null
  videoId: string | null
  machineId: string | null
}

export interface DayPlan {
  memberId: string
  title: { ar: string; en: string }
  exercises: PrescribedExercise[]
}

export interface LoggedSet {
  exerciseId: string
  set: number
  reps: number
  weightKg: number
}

/** The coach taps a band; an exact number is optional and rarely entered. */
export type CalorieBand = 'low' | 'ok' | 'high' | 'unknown'

export interface NutritionEntry {
  memberId: string
  date: string
  band: CalorieBand
  meals: string[]
  source: 'coach_asked' | 'member_logged'
}

export interface Video {
  id: string
  title: { ar: string; en: string }
  provider: 'youtube' | 'vimeo'
  externalId: string
  seconds: number
  muscle: 'chest' | 'back' | 'legs' | 'shoulders' | 'arms' | 'core'
  equipment: 'barbell' | 'dumbbell' | 'machine' | 'bodyweight'
  views: number
}

export interface AiDraft {
  id: string
  memberId: string
  kind: 'plan' | 'nutrition' | 'tip'
  headline: { ar: string; en: string }
  body: { ar: string; en: string }
  reason: { ar: string; en: string }
  status: 'pending' | 'approved' | 'rejected'
  createdAt: string
  /** The machine-actionable proposal a coach's approve applies — mirrors
   * app/domain/ai_drafts.py's payload shapes. Absent for kind:'tip'. */
  payload?: { type: 'calorie_target_update'; daily_kcal_target: number }
}

export type FoodSource = 'photo' | 'manual' | 'agent'

export interface FoodEntry {
  id: string
  at: string
  label: Text
  kcal: number
  protein: number
  carbs: number
  fat: number
  source: FoodSource
  /** Data URL of the meal photo, when the entry came from the camera. */
  photo?: string
}

export type AgentId = 'nutrition' | 'training'

export interface ChatMessage {
  id: string
  role: 'member' | 'agent'
  text: string
  at: string
  /** Set when the reply had a side effect worth showing in the transcript. */
  note?: 'food_logged' | 'draft_sent'
}

export interface Coach {
  id: string
  name: Text
  speciality: Text
}

/** A physical station on the gym floor. The coach records which one was used. */
export interface Machine {
  id: string
  name: Text
  area: 'free-weights' | 'machines' | 'cardio' | 'floor'
}

export interface GymClass {
  id: string
  title: Text
  coachId: string
  /** 0 = Sunday, matching Date.getDay() */
  weekdays: number[]
  time: string
  durationMin: number
}

export type BookingKind = 'private' | 'intro'

export interface Booking {
  id: string
  memberId: string
  coachId: string
  /** ISO date */
  date: string
  time: string
  kind: BookingKind
  status: 'booked' | 'done' | 'cancelled'
}

/** How the member handled the session — tapped by the coach as they finish. */
export type EffortBand = 'easy' | 'good' | 'hard' | 'struggled'

export interface SessionFeedback {
  memberId: string
  date: string
  band: EffortBand
  note?: string
}

export interface AttendanceDay {
  memberId: string
  /** ISO date */
  date: string
}

export type SupplementId = 'protein' | 'creatine' | 'vitamins'
