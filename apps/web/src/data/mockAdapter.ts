/**
 * Adapts src/mocks/data.ts into the exact same shape the live API returns,
 * so feature components read one type (src/data/types.ts) regardless of
 * whether VITE_API_URL is set. Mutations write to a session-only in-memory
 * copy — mock mode has never persisted across reloads, and this keeps it
 * that way; that gap is exactly what running the gym on the real API is
 * for.
 */
import {
  checkIns as seedCheckIns,
  daysSinceVisit,
  findPlan,
  members as seedMembers,
  payments as seedPayments,
  plans,
} from '@/mocks/data'
import type { Member as MockMember, Payment as MockPayment } from '@/mocks/types'
import { waLink } from '@/lib/whatsapp'
import type {
  ApiCheckIn,
  ApiLapsedMember,
  ApiMember,
  ApiMemberDetail,
  ApiPayment,
  ApiPlan,
  CreateMemberInput,
  RecordPaymentInput,
} from './types'

let mockMembers: MockMember[] = seedMembers.map((m) => ({ ...m }))
let mockPayments: MockPayment[] = seedPayments.map((p) => ({ ...p }))

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
  return seedCheckIns.map((c) => ({
    id: c.id,
    member_id: c.memberId,
    at: c.at,
    status: c.status,
  }))
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
