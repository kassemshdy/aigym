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

export interface StaffPinResetResult {
  sent: boolean
}
