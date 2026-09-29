import type { ProgramDay } from '@/data/types'

/**
 * Ready-made plans a coach starts from and then adjusts. Decision 53.
 *
 * Exercises are named, not referenced by id: a template has to work at any
 * gym, and each gym's catalog has its own ids. Applying one finds each
 * exercise in the gym's catalog by name and adds any the gym lacks, so a
 * template never fails because a gym renamed or never had an exercise.
 * The names match the starter catalog in apps/api/scripts/seed.py.
 *
 * Kept in the client rather than served: it is fixed content, it has to
 * work in the prototype with no API, and it is a couple of kilobytes.
 */

type MuscleGroup = 'chest' | 'back' | 'legs' | 'shoulders' | 'arms' | 'core'

export interface TemplateExercise {
  name: { ar: string; en: string }
  muscle: MuscleGroup
  sets: number
  reps: { ar: string; en: string }
}

export interface ProgramTemplate {
  id: string
  title: { ar: string; en: string }
  /** One line under the title: who it is for, how often. */
  note: { ar: string; en: string }
  days: { title: ProgramDay; exercises: TemplateExercise[] }[]
}

const ex = (
  en: string,
  ar: string,
  muscle: MuscleGroup,
  sets: number,
  reps: string,
  repsAr = reps,
): TemplateExercise => ({ name: { ar, en }, muscle, sets, reps: { ar: repsAr, en: reps } })

const SQUAT = (sets: number, reps: string) => ex('Squat', 'سكوات', 'legs', sets, reps)
const BENCH = (sets: number, reps: string) => ex('Bench Press', 'بنش برس', 'chest', sets, reps)
const PLANK = (sets: number, secs: number) =>
  ex('Plank', 'بلانك', 'core', sets, `${secs} sec`, `${secs} ثانية`)

export const PROGRAM_TEMPLATES: ProgramTemplate[] = [
  {
    id: 'beginner',
    title: { ar: 'مبتدئ — كل الجسم', en: 'Beginner — full body' },
    note: { ar: 'يومين بالتناوب، 2–3 مرات بالأسبوع', en: 'Two days in turn, 2–3 times a week' },
    days: [
      {
        title: { ar: 'اليوم أ', en: 'Day A' },
        exercises: [
          SQUAT(3, '10'),
          BENCH(3, '10'),
          ex('Seated Cable Row', 'تجديف جالس', 'back', 3, '12'),
          PLANK(3, 30),
        ],
      },
      {
        title: { ar: 'اليوم ب', en: 'Day B' },
        exercises: [
          ex('Leg Press', 'ضغط أرجل', 'legs', 3, '12'),
          ex('Dumbbell Shoulder Press', 'ضغط كتف دمبل', 'shoulders', 3, '10'),
          ex('Lat Pulldown', 'سحب علوي', 'back', 3, '12'),
          ex('Lunge', 'لنج', 'legs', 3, '10'),
        ],
      },
    ],
  },
  {
    id: 'ppl',
    title: { ar: 'دفع / سحب / أرجل', en: 'Push / Pull / Legs' },
    note: { ar: 'ثلاث أيام بالتناوب، 3–6 مرات بالأسبوع', en: 'Three days in turn, 3–6 times a week' },
    days: [
      {
        title: { ar: 'دفع', en: 'Push' },
        exercises: [
          BENCH(4, '8'),
          ex('Incline Bench Press', 'بنش مائل', 'chest', 3, '10'),
          ex('Dumbbell Shoulder Press', 'ضغط كتف دمبل', 'shoulders', 3, '10'),
          ex('Cable Fly', 'فتح كابل', 'chest', 3, '12'),
          ex('Triceps Pushdown', 'ترايسبس كابل', 'arms', 3, '12'),
        ],
      },
      {
        title: { ar: 'سحب', en: 'Pull' },
        exercises: [
          ex('Deadlift', 'رفعة ميتة', 'back', 3, '5'),
          ex('Pull-Up', 'عقلة', 'back', 3, '8'),
          ex('Barbell Row', 'تجديف بالبار', 'back', 3, '10'),
          ex('Seated Cable Row', 'تجديف جالس', 'back', 3, '12'),
          ex('Dumbbell Bicep Curl', 'بايسبس دمبل', 'arms', 3, '12'),
        ],
      },
      {
        title: { ar: 'أرجل', en: 'Legs' },
        exercises: [
          SQUAT(4, '8'),
          ex('Leg Press', 'ضغط أرجل', 'legs', 3, '12'),
          ex('Leg Curl', 'ثني أرجل', 'legs', 3, '12'),
          ex('Leg Extension', 'فرد أرجل', 'legs', 3, '12'),
          ex('Calf Raise', 'رفع كعب', 'legs', 4, '15'),
        ],
      },
    ],
  },
  {
    id: 'upper-lower',
    title: { ar: 'علوي / سفلي', en: 'Upper / Lower' },
    note: { ar: 'يومين بالتناوب، 4 مرات بالأسبوع', en: 'Two days in turn, 4 times a week' },
    days: [
      {
        title: { ar: 'علوي', en: 'Upper' },
        exercises: [
          BENCH(4, '8'),
          ex('Barbell Row', 'تجديف بالبار', 'back', 4, '8'),
          ex('Overhead Press', 'ضغط كتف واقف', 'shoulders', 3, '10'),
          ex('Lat Pulldown', 'سحب علوي', 'back', 3, '10'),
          ex('Dumbbell Bicep Curl', 'بايسبس دمبل', 'arms', 2, '12'),
          ex('Triceps Pushdown', 'ترايسبس كابل', 'arms', 2, '12'),
        ],
      },
      {
        title: { ar: 'سفلي', en: 'Lower' },
        exercises: [
          SQUAT(4, '8'),
          ex('Deadlift', 'رفعة ميتة', 'back', 3, '6'),
          ex('Leg Press', 'ضغط أرجل', 'legs', 3, '12'),
          ex('Leg Curl', 'ثني أرجل', 'legs', 3, '12'),
          ex('Calf Raise', 'رفع كعب', 'legs', 3, '15'),
          PLANK(3, 45),
        ],
      },
    ],
  },
]
