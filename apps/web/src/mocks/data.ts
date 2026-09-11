import type { Lang } from '@/i18n'
import type {
  AiDraft,
  AttendanceDay,
  Booking,
  Coach,
  GymClass,
  Machine,
  SessionFeedback,
  CheckIn,
  DayPlan,
  Member,
  NutritionEntry,
  Payment,
  Plan,
  Video,
} from './types'

export const gym = {
  name: { ar: 'نادي تريبل إي — عرمون', en: 'Triple A Gym — Aaramoun' },
  coach: { ar: 'الكوتش عساف', en: 'Coach Assaf' },
}

export const plans: Plan[] = [
  { id: 'p1', name: { ar: 'اشتراك شهري', en: 'Monthly' }, priceUsd: 35, days: 30 },
  { id: 'p3', name: { ar: 'اشتراك ٣ أشهر', en: '3 Months' }, priceUsd: 90, days: 90 },
  { id: 'p12', name: { ar: 'اشتراك سنوي', en: 'Yearly' }, priceUsd: 300, days: 365 },
  { id: 'pt', name: { ar: 'تدريب خاص', en: 'Personal Training' }, priceUsd: 150, days: 30 },
]

export const members: Member[] = [
  {
    id: 'm0', name: 'قاسم شحادي', nameEn: 'Kassem Shehady', phone: '+96170622211',
    planId: 'pt', joinedAt: '2026-03-02', endsAt: '2026-10-02', status: 'paid', owedUsd: 0,
    lastVisit: '2026-09-10', goal: 'strength', level: 'mid', heightCm: 177, weightKg: 80,
    bodyFat: 19, injuries: [], daysPerWeek: 3, job: 'desk', sleepHours: 7,
    weightTrend: [84, 83, 83, 82, 81, 81, 80],
  },
  {
    id: 'm1', name: 'رامي حداد', nameEn: 'Rami Haddad', phone: '+96170123456',
    planId: 'p1', joinedAt: '2025-11-02', endsAt: '2026-09-08', status: 'due', owedUsd: 35,
    lastVisit: '2026-09-08', goal: 'lose', level: 'mid', heightCm: 178, weightKg: 92,
    bodyFat: 26, injuries: [{ ar: 'أسفل الظهر', en: 'Lower back' }], daysPerWeek: 3, job: 'desk', sleepHours: 6,
    weightTrend: [98, 97, 96, 95, 94, 93, 92],
  },
  {
    id: 'm2', name: 'نور عبدالله', nameEn: 'Nour Abdallah', phone: '+96176334521',
    planId: 'p3', joinedAt: '2026-06-14', endsAt: '2026-09-14', status: 'soon', owedUsd: 0,
    lastVisit: '2026-09-09', goal: 'strength', level: 'strong', heightCm: 165, weightKg: 61,
    bodyFat: 21, injuries: [], daysPerWeek: 5, job: 'active', sleepHours: 8,
    weightTrend: [58, 58, 59, 59, 60, 60, 61],
  },
  {
    id: 'm3', name: 'جاد خوري', nameEn: 'Jad Khoury', phone: '+96171889012',
    planId: 'p12', joinedAt: '2026-01-08', endsAt: '2027-01-08', status: 'paid', owedUsd: 0,
    lastVisit: '2026-09-10', goal: 'gain', level: 'mid', heightCm: 182, weightKg: 74,
    bodyFat: 14, injuries: [], daysPerWeek: 4, job: 'desk', sleepHours: 7,
    weightTrend: [70, 70, 71, 72, 72, 73, 74],
  },
  {
    id: 'm4', name: 'مايا شمعون', nameEn: 'Maya Chamoun', phone: '+96103445566',
    planId: 'p1', joinedAt: '2026-08-01', endsAt: '2026-09-01', status: 'due', owedUsd: 35,
    lastVisit: '2026-08-29', goal: 'health', level: 'new', heightCm: 170, weightKg: 68,
    bodyFat: 29, injuries: [{ ar: 'ركبة يمين', en: 'Right knee' }], daysPerWeek: 2, job: 'shift', sleepHours: 5,
    weightTrend: [69, 69, 69, 68, 68, 68, 68],
  },
  {
    id: 'm5', name: 'علي حمدان', nameEn: 'Ali Hamdan', phone: '+96181220034',
    planId: 'pt', joinedAt: '2026-05-20', endsAt: '2026-09-20', status: 'paid', owedUsd: 0,
    lastVisit: '2026-09-10', goal: 'strength', level: 'strong', heightCm: 175, weightKg: 84,
    bodyFat: 16, injuries: [{ ar: 'كتف يسار', en: 'Left shoulder' }], daysPerWeek: 5, job: 'active', sleepHours: 7,
    weightTrend: [82, 82, 83, 83, 83, 84, 84],
  },
  {
    id: 'm6', name: 'سيرين نصار', nameEn: 'Sirine Nassar', phone: '+96170998877',
    planId: 'p3', joinedAt: '2026-07-05', endsAt: '2026-10-05', status: 'paid', owedUsd: 0,
    lastVisit: '2026-09-09', goal: 'lose', level: 'new', heightCm: 162, weightKg: 71,
    bodyFat: 31, injuries: [], daysPerWeek: 3, job: 'desk', sleepHours: 6,
    weightTrend: [75, 74, 74, 73, 72, 72, 71],
  },
  {
    id: 'm7', name: 'طوني عون', nameEn: 'Tony Aoun', phone: '+96176112233',
    planId: 'p1', joinedAt: '2026-04-11', endsAt: '2026-09-11', status: 'soon', owedUsd: 0,
    lastVisit: '2026-09-07', goal: 'gain', level: 'mid', heightCm: 180, weightKg: 79,
    bodyFat: 18, injuries: [], daysPerWeek: 4, job: 'shift', sleepHours: 6,
    weightTrend: [76, 76, 77, 77, 78, 79, 79],
  },
  {
    id: 'm8', name: 'ليلى مراد', nameEn: 'Layla Mrad', phone: '+96171445599',
    planId: 'p1', joinedAt: '2026-02-19', endsAt: '2026-08-19', status: 'due', owedUsd: 70,
    lastVisit: '2026-08-17', goal: 'health', level: 'mid', heightCm: 168, weightKg: 64,
    bodyFat: 24, injuries: [], daysPerWeek: 2, job: 'desk', sleepHours: 7,
    weightTrend: [66, 66, 65, 65, 65, 64, 64],
  },
]

export const payments: Payment[] = [
  { id: 'y1', memberId: 'm3', amountUsd: 300, at: '2026-01-08', method: 'cash', by: 'كسام' },
  { id: 'y2', memberId: 'm6', amountUsd: 90, at: '2026-07-05', method: 'cash', by: 'كسام' },
  { id: 'y3', memberId: 'm5', amountUsd: 150, at: '2026-08-20', method: 'transfer', by: 'كسام' },
  { id: 'y4', memberId: 'm2', amountUsd: 90, at: '2026-06-14', method: 'cash', by: 'كسام' },
  { id: 'y5', memberId: 'm7', amountUsd: 35, at: '2026-08-11', method: 'cash', by: 'كسام' },
]

export const checkIns: CheckIn[] = [
  { id: 'c1', memberId: 'm3', at: '17:05', status: 'waiting' },
  { id: 'c2', memberId: 'm1', at: '17:12', status: 'waiting' },
  { id: 'c3', memberId: 'm5', at: '17:20', status: 'training' },
  { id: 'c4', memberId: 'm2', at: '16:40', status: 'done' },
  { id: 'c5', memberId: 'm6', at: '16:15', status: 'done' },
]

export const dayPlans: DayPlan[] = [
  {
    memberId: 'm0',
    title: { ar: 'دفع — صدر وكتف', en: 'Push — Chest and Shoulders' },
    exercises: [
      { id: 'k1', name: { ar: 'بنش برس', en: 'Bench Press' }, sets: 4, reps: '6-8', lastWeightKg: 70, videoId: 'v1', machineId: 'mc-bench' },
      { id: 'k2', name: { ar: 'ضغط كتف بالدمبل', en: 'Dumbbell Shoulder Press' }, sets: 3, reps: '10', lastWeightKg: 22, videoId: 'v8', machineId: 'mc-dumbbell' },
      { id: 'k3', name: { ar: 'تفتيح كابل', en: 'Cable Fly' }, sets: 3, reps: '12', lastWeightKg: 20, videoId: 'v2', machineId: 'mc-cable' },
      { id: 'k4', name: { ar: 'بلانك', en: 'Plank' }, sets: 3, reps: { ar: '45 ثانية', en: '45 sec' }, lastWeightKg: null, videoId: 'v3', machineId: 'mc-floor' },
    ],
  },
  {
    memberId: 'm1',
    title: { ar: 'صدر + بطن', en: 'Chest + Core' },
    exercises: [
      { id: 'e1', name: { ar: 'بنش برس', en: 'Bench Press' }, sets: 4, reps: '8-10', lastWeightKg: 60, videoId: 'v1' , machineId: 'mc-bench'},
      { id: 'e2', name: { ar: 'تفتيح دمبل', en: 'Dumbbell Fly' }, sets: 3, reps: '12', lastWeightKg: 12, videoId: 'v2' , machineId: 'mc-dumbbell'},
      { id: 'e3', name: { ar: 'ضغط مائل', en: 'Incline Press' }, sets: 3, reps: '10', lastWeightKg: 40, videoId: null , machineId: 'mc-incline'},
      { id: 'e4', name: { ar: 'بلانك', en: 'Plank' }, sets: 3, reps: { ar: '45 ثانية', en: '45 sec' }, lastWeightKg: null, videoId: 'v3' , machineId: 'mc-floor'},
    ],
  },
  {
    memberId: 'm3',
    title: { ar: 'ظهر + باي', en: 'Back + Biceps' },
    exercises: [
      { id: 'e5', name: { ar: 'سحب أرضي', en: 'Seated Row' }, sets: 4, reps: '10', lastWeightKg: 45, videoId: 'v4' , machineId: 'mc-cable'},
      { id: 'e6', name: { ar: 'عقلة بمساعدة', en: 'Assisted Pull-up' }, sets: 3, reps: '8', lastWeightKg: 20, videoId: 'v5' , machineId: 'mc-assist'},
      { id: 'e7', name: { ar: 'مرجحة باي', en: 'Bicep Curl' }, sets: 3, reps: '12', lastWeightKg: 14, videoId: null , machineId: 'mc-dumbbell'},
    ],
  },
  {
    memberId: 'm5',
    title: { ar: 'رجل', en: 'Legs' },
    exercises: [
      { id: 'e8', name: { ar: 'سكوات', en: 'Back Squat' }, sets: 5, reps: '5', lastWeightKg: 100, videoId: 'v6' , machineId: 'mc-rack'},
      { id: 'e9', name: { ar: 'رفعة ميتة رومانية', en: 'Romanian Deadlift' }, sets: 3, reps: '8', lastWeightKg: 80, videoId: 'v7' , machineId: 'mc-barbell'},
      { id: 'e10', name: { ar: 'ضغط أرجل', en: 'Leg Press' }, sets: 3, reps: '12', lastWeightKg: 140, videoId: null , machineId: 'mc-legpress'},
    ],
  },
]

export const nutrition: NutritionEntry[] = [
  { memberId: 'm5', date: '2026-09-10', band: 'ok', meals: ['فطور: بيض + خبز', 'غدا: دجاج + رز'], source: 'coach_asked' },
  { memberId: 'm3', date: '2026-09-10', band: 'low', meals: ['قهوة بس'], source: 'coach_asked' },
]

export const videos: Video[] = [
  { id: 'v1', title: { ar: 'بنش برس — الوضعية الصح', en: 'Bench Press — Correct Form' }, provider: 'youtube', externalId: 'gRVjAtPip0Y', seconds: 214, muscle: 'chest', equipment: 'barbell', views: 148 },
  { id: 'v2', title: { ar: 'تفتيح دمبل بدون إصابة', en: 'Dumbbell Fly Without Injury' }, provider: 'youtube', externalId: 'eozdVDA78K0', seconds: 176, muscle: 'chest', equipment: 'dumbbell', views: 96 },
  { id: 'v3', title: { ar: 'بلانك — غلطات شائعة', en: 'Plank — Common Mistakes' }, provider: 'youtube', externalId: 'pSHjTRCQxIw', seconds: 132, muscle: 'core', equipment: 'bodyweight', views: 203 },
  { id: 'v4', title: { ar: 'سحب أرضي للظهر', en: 'Seated Row for Back' }, provider: 'youtube', externalId: 'GZbfZ033f74', seconds: 188, muscle: 'back', equipment: 'machine', views: 77 },
  { id: 'v5', title: { ar: 'من صفر لأول عقلة', en: 'Zero to First Pull-up' }, provider: 'youtube', externalId: 'eGo4IYlbE5g', seconds: 341, muscle: 'back', equipment: 'bodyweight', views: 312 },
  { id: 'v6', title: { ar: 'سكوات — عمق وركبة', en: 'Squat — Depth and Knees' }, provider: 'youtube', externalId: 'ultWZbUMPL8', seconds: 265, muscle: 'legs', equipment: 'barbell', views: 259 },
  { id: 'v7', title: { ar: 'رفعة ميتة رومانية', en: 'Romanian Deadlift' }, provider: 'youtube', externalId: '2SHsk9AzdjA', seconds: 199, muscle: 'legs', equipment: 'barbell', views: 134 },
  { id: 'v8', title: { ar: 'تسخين الكتف قبل التمرين', en: 'Shoulder Warm-up' }, provider: 'youtube', externalId: 'Cv6mtHMFsdA', seconds: 154, muscle: 'shoulders', equipment: 'bodyweight', views: 88 },
]

export const aiDrafts: AiDraft[] = [
  {
    id: 'a1', memberId: 'm1', kind: 'plan', status: 'pending', createdAt: '2026-09-10',
    headline: { ar: 'خطة ٣ أيام — ضغط أقل على أسفل الظهر', en: '3-day plan — less load on lower back' },
    body: {
      ar: 'استبدال السكوات بالحر بضغط الأرجل، وإضافة تقوية للحزام الأساسي يومين بالأسبوع. زيادة الوزن ٢.٥ كغ كل أسبوعين مش كل أسبوع.',
      en: 'Swap free squats for leg press, add core bracing twice a week. Progress weight 2.5 kg every two weeks, not weekly.',
    },
    reason: {
      ar: 'مسجّل عنده إصابة أسفل الظهر، بينام ٦ ساعات، وشغله مكتبي — الاستشفاء أبطأ من المعدل.',
      en: 'Recorded lower-back injury, sleeps 6h, desk job — recovery slower than average.',
    },
  },
  {
    id: 'a2', memberId: 'm4', kind: 'nutrition', status: 'pending', createdAt: '2026-09-10',
    headline: { ar: 'هدف بروتين ١٠٥ غ باليوم', en: 'Protein target 105 g/day' },
    body: {
      ar: 'توزيع البروتين على ٣ وجبات، والتركيز على وجبة بعد التمرين مباشرة. ما في داعي لعدّ كل شي — بس الوجبات الثلاث.',
      en: 'Split protein across 3 meals, one right after training. No need to count everything — just the three meals.',
    },
    reason: {
      ar: 'وزن ٦٨ كغ وهدفها صحة عامة، وشغلها ورديات — أبسط خطة هي الأنجح.',
      en: '68 kg, general-health goal, shift work — the simplest plan is the one that sticks.',
    },
  },
  {
    id: 'a3', memberId: 'm5', kind: 'tip', status: 'pending', createdAt: '2026-09-10',
    headline: { ar: 'خفّف حجم تمرين الكتف هالأسبوع', en: 'Reduce shoulder volume this week' },
    body: {
      ar: 'آخر ٣ حصص الوزن نزل بالضغط العلوي. خفّف مجموعة وحدة ورجاع الأسبوع الجاي.',
      en: 'Overhead press weight dropped across the last 3 sessions. Cut one set, rebuild next week.',
    },
    reason: {
      ar: 'إصابة كتف يسار مسجّلة + تراجع بالأداء ٣ حصص متتالية.',
      en: 'Recorded left-shoulder injury plus 3 consecutive sessions of declining performance.',
    },
  },
]

/** The one place a member's display name is chosen. Avatars use it too, so initials match. */
export const memberName = (m: Member, lang: Lang) => (lang === 'ar' ? m.name : m.nameEn)

export const findMember = (id: string) => members.find((m) => m.id === id)
export const findPlan = (id: string) => plans.find((p) => p.id === id)
export const findVideo = (id: string) => videos.find((v) => v.id === id)
export const planForMember = (id: string) => dayPlans.find((d) => d.memberId === id)

/** The member the "member app" tab is signed in as — the gym owner testing it. */
export const currentMemberId = 'm0'

/* ------------------------------------------------------------------ the gym */

export const coaches: Coach[] = [
  {
    id: 'c-assaf',
    name: { ar: 'الكوتش عساف', en: 'Coach Assaf' },
    speciality: { ar: 'قوة وتقنية الرفع', en: 'Strength and lifting technique' },
  },
  {
    id: 'c-karim',
    name: { ar: 'الكوتش كريم', en: 'Coach Karim' },
    speciality: { ar: 'تنحيف وكارديو', en: 'Fat loss and conditioning' },
  },
  {
    id: 'c-abed',
    name: { ar: 'الكوتش عبد', en: 'Coach Abed' },
    speciality: { ar: 'كمال أجسام وتضخيم', en: 'Bodybuilding and hypertrophy' },
  },
]

/** Stations on the floor. The coach records which one was actually used. */
export const machines: Machine[] = [
  { id: 'mc-bench', name: { ar: 'بنش', en: 'Bench' }, area: 'free-weights' },
  { id: 'mc-incline', name: { ar: 'بنش مائل', en: 'Incline bench' }, area: 'free-weights' },
  { id: 'mc-rack', name: { ar: 'قفص السكوات', en: 'Squat rack' }, area: 'free-weights' },
  { id: 'mc-barbell', name: { ar: 'بار حر', en: 'Barbell' }, area: 'free-weights' },
  { id: 'mc-dumbbell', name: { ar: 'دمبل', en: 'Dumbbells' }, area: 'free-weights' },
  { id: 'mc-cable', name: { ar: 'جهاز الكابل', en: 'Cable tower' }, area: 'machines' },
  { id: 'mc-legpress', name: { ar: 'ضغط أرجل', en: 'Leg press' }, area: 'machines' },
  { id: 'mc-assist', name: { ar: 'جهاز العقلة المساعد', en: 'Assisted pull-up' }, area: 'machines' },
  { id: 'mc-tread', name: { ar: 'مشاية', en: 'Treadmill' }, area: 'cardio' },
  { id: 'mc-bike', name: { ar: 'بسكليت', en: 'Bike' }, area: 'cardio' },
  { id: 'mc-floor', name: { ar: 'أرض التمرين', en: 'Floor' }, area: 'floor' },
]

/** The gym's real class schedule. 0 = Sunday. */
export const classes: GymClass[] = [
  {
    id: 'cl-cardio',
    title: { ar: 'كارديو وبطن', en: 'Cardio & Abs' },
    coachId: 'c-karim',
    weekdays: [2, 5],
    time: '19:00',
    durationMin: 45,
  },
  {
    id: 'cl-strength',
    title: { ar: 'قوة للمبتدئين', en: 'Strength Basics' },
    coachId: 'c-assaf',
    weekdays: [1, 3],
    time: '18:00',
    durationMin: 60,
  },
  {
    id: 'cl-hyper',
    title: { ar: 'تضخيم', en: 'Hypertrophy' },
    coachId: 'c-abed',
    weekdays: [0, 4],
    time: '20:00',
    durationMin: 60,
  },
]

const iso = (daysFromToday: number) => {
  const d = new Date()
  d.setDate(d.getDate() + daysFromToday)
  return d.toISOString().slice(0, 10)
}

export const bookings: Booking[] = [
  { id: 'b1', memberId: 'm0', coachId: 'c-abed', date: iso(1), time: '18:00', kind: 'private', status: 'booked' },
  { id: 'b2', memberId: 'm0', coachId: 'c-karim', date: iso(4), time: '19:00', kind: 'private', status: 'booked' },
  { id: 'b3', memberId: 'm4', coachId: 'c-karim', date: iso(2), time: '17:00', kind: 'intro', status: 'booked' },
]

/**
 * Attendance for the last eight weeks. Some members are deliberately lapsed so the
 * "stopped coming" list has something true to show rather than an empty state.
 */
export const attendance: AttendanceDay[] = (() => {
  const out: AttendanceDay[] = []
  const pattern: Record<string, { days: number[]; until: number }> = {
    m0: { days: [0, 2, 4], until: 0 },
    m1: { days: [1, 4], until: 2 },
    m2: { days: [0, 2, 3, 5], until: 1 },
    m3: { days: [1, 3, 5], until: 0 },
    m4: { days: [2], until: 23 }, // stopped coming three weeks ago
    m5: { days: [0, 1, 3, 4], until: 1 },
    m6: { days: [2, 5], until: 4 },
    m7: { days: [1, 4], until: 12 }, // slipping
    m8: { days: [3], until: 31 }, // gone a month
  }
  for (const [memberId, { days, until }] of Object.entries(pattern)) {
    for (let back = until; back < 56; back++) {
      const d = new Date()
      d.setDate(d.getDate() - back)
      if (days.includes(d.getDay())) out.push({ memberId, date: d.toISOString().slice(0, 10) })
    }
  }
  return out
})()

export const sessionFeedback: SessionFeedback[] = [
  { memberId: 'm0', date: iso(-2), band: 'good' },
  { memberId: 'm0', date: iso(-5), band: 'hard', note: 'آخر مجموعتين كانوا صعبين' },
  { memberId: 'm0', date: iso(-7), band: 'good' },
  { memberId: 'm5', date: iso(-1), band: 'struggled', note: 'الكتف عم يوجع' },
]

export const findCoach = (id: string) => coaches.find((c) => c.id === id)
export const findMachine = (id: string | null) => (id ? machines.find((m) => m.id === id) : undefined)

/** Days since the member last showed up. Drives the "stopped coming" list. */
export function daysSinceVisit(memberId: string) {
  const days = attendance
    .filter((a) => a.memberId === memberId)
    .map((a) => a.date)
    .sort()
  const last = days[days.length - 1]
  if (!last) return Infinity
  return Math.round((Date.now() - new Date(last).getTime()) / 86_400_000)
}
