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
  injuries: string[]
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
  reps: string
  lastWeightKg: number | null
  videoId: string | null
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
}

export type FoodSource = 'photo' | 'manual' | 'agent'

export interface FoodEntry {
  id: string
  at: string
  label: string
  kcal: number
  protein: number
  carbs: number
  fat: number
  source: FoodSource
  /** Data URL of the meal photo, when the entry came from the camera. */
  photo?: string
}

export interface ProgressPhoto {
  id: string
  at: string
  url: string
  /**
   * Progress photos are private to the member. The coach sees one only when the
   * member shares that specific photo. Default is always false.
   */
  sharedWithCoach: boolean
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
