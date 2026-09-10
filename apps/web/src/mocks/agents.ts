import type { AgentId, FoodEntry } from './types'
import type { Lang } from '@/i18n'

/**
 * Prototype stand-in for the Phase 5 agents. The real ones call Claude with the member's
 * body data, lifestyle, injuries, and recent sessions as context; this matches on keywords
 * so the conversation can be walked end to end without a backend.
 *
 * The boundary encoded here is the product rule, not a prototype shortcut:
 * an agent answers freely and may log what the member reports, but it can never change
 * the program or the calorie targets — that leaves as a draft for the coach to approve.
 */

export interface AgentReply {
  text: { ar: string; en: string }
  /** Logging what the member said they ate is inside the agent's authority. */
  food?: Omit<FoodEntry, 'id' | 'at' | 'source'>
  /** Changing the plan is not: it becomes a pending draft in the coach's inbox. */
  draft?: boolean
}

export const AGENTS: Record<AgentId, { name: { ar: string; en: string }; blurb: { ar: string; en: string } }> = {
  nutrition: {
    name: { ar: 'مساعد التغذية', en: 'Nutrition assistant' },
    blurb: {
      ar: 'اسأله عن الأكل، السعرات، والبروتين. بيقدر يسجّل أكلك بالشات.',
      en: 'Ask about food, calories, and protein. It can log your meals from the chat.',
    },
  },
  training: {
    name: { ar: 'مساعد كمال الأجسام', en: 'Bodybuilding assistant' },
    blurb: {
      ar: 'اسأله عن التمارين، الوضعية الصح، والاستشفاء.',
      en: 'Ask about exercises, correct form, and recovery.',
    },
  },
}

export const SUGGESTIONS: Record<AgentId, { ar: string; en: string }[]> = {
  nutrition: [
    { ar: 'قديش لازم آكل بروتين باليوم؟', en: 'How much protein should I eat a day?' },
    { ar: 'أكلت دجاج مع رز عالغدا', en: 'I had chicken and rice for lunch' },
    { ar: 'شو آكل قبل التمرين؟', en: 'What should I eat before training?' },
  ],
  training: [
    { ar: 'ظهري بيوجعني بالسكوات', en: 'My back hurts during squats' },
    { ar: 'كم يوم لازم إرتاح بالأسبوع؟', en: 'How many rest days per week?' },
    { ar: 'بدي زيد وزن البنش', en: 'I want to add weight to my bench' },
  ],
}

const REPLIES: Record<AgentId, { match: RegExp; reply: AgentReply }[]> = {
  nutrition: [
    {
      match: /بروتين|protein/i,
      reply: {
        text: {
          ar: 'لوزنك ووضعك، هدف معقول هو ١٫٦ غ بروتين لكل كيلو — يعني حوالي ١٤٥ غ باليوم. وزّعها على ٣ وجبات بدل ما تركّز كل شي بوجبة وحدة. أسهل مصادر عنا: دجاج، لبنة، بيض، وتونة.',
          en: 'For your weight and goal, 1.6 g of protein per kilo is a sensible target — about 145 g a day. Split it across 3 meals rather than loading one. Easiest local sources: chicken, labneh, eggs, tuna.',
        },
      },
    },
    {
      match: /دجاج|رز|chicken|rice/i,
      reply: {
        text: {
          ar: 'سجّلتها: دجاج مشوي مع رز — تقريباً ٦٢٠ سعرة، ٤٥ غ بروتين. ضلّك ٨٠ غ بروتين لليوم.',
          en: "Logged it: grilled chicken with rice — roughly 620 kcal, 45 g protein. You have about 80 g of protein left today.",
        },
        food: { label: { ar: 'دجاج مع رز', en: 'Chicken with rice' }, kcal: 620, protein: 45, carbs: 68, fat: 14 },
      },
    },
    {
      match: /قبل التمرين|before train|pre.?workout/i,
      reply: {
        text: {
          ar: 'قبل التمرين بساعة: شي بسيط فيه نشويات وبروتين خفيف — موزة مع لبنة، أو خبز مع بيضة. تجنّب الدهون الكتيرة قبل التمرين مباشرة لأنها بتبطّئ الهضم.',
          en: 'About an hour before: something light with carbs and a little protein — a banana with labneh, or bread with an egg. Avoid heavy fats right before, they slow digestion.',
        },
      },
    },
    {
      match: /غيّر|رجيم|دايت|خطة|target|change|diet|plan/i,
      reply: {
        text: {
          ar: 'هيدا تغيير بأهدافك الغذائية، وما بقدر عملو لحالي. بعتّه كاقتراح للكوتش عساف — رح يراجعه ويوافق عليه، وبيوصلك أول ما يوافق.',
          en: "That changes your nutrition targets, which I can't do on my own. I've sent it to Coach Assaf as a suggestion — he'll review it, and you'll get it once he approves.",
        },
        draft: true,
      },
    },
  ],
  training: [
    {
      match: /ظهر|سكوات|back|squat/i,
      reply: {
        text: {
          ar: 'مسجّل عندك إصابة أسفل الظهر، فما بنجازف. جرّب ضغط الأرجل بدل السكوات الحر هالفترة، وخلّي بطنك مشدود قبل ما تنزل. إذا الوجع حاد أو نازل لرجلك، وقّف وخبّر الكوتش.',
          en: "You have a recorded lower-back injury, so let's not gamble. Use the leg press instead of free squats for now, and brace your core before descending. If the pain is sharp or runs down your leg, stop and tell the coach.",
        },
      },
    },
    {
      match: /ارتاح|راحة|rest|recover/i,
      reply: {
        text: {
          ar: 'انت متمرّن ٣ أيام بالأسبوع وبتنام ٦ ساعات. يومين راحة كاملة أحسن شي، وحاول توصل النوم لـ٧. الاستشفاء عندك أبطأ من المعدل لأن النوم قليل مش لأن التمرين قليل.',
          en: "You train 3 days a week and sleep 6 hours. Two full rest days is right, and try to get sleep up to 7. Your recovery is slower than average because sleep is short, not because training is light.",
        },
      },
    },
    {
      match: /زيد|وزن|بنش|add|increase|bench|program|برنامج/i,
      reply: {
        text: {
          ar: 'زيادة وزن البنش يعني تعديل ببرنامجك، وهاد قرار الكوتش. بعتّه كاقتراح للكوتش عساف مع أرقام آخر ٣ حصص — بيراجعه وبيوافق.',
          en: "Adding bench weight means changing your program, and that's the coach's call. I've sent it to Coach Assaf as a suggestion with your last 3 sessions' numbers — he'll review and approve.",
        },
        draft: true,
      },
    },
  ],
}

const FALLBACK: Record<AgentId, AgentReply> = {
  nutrition: {
    text: {
      ar: 'سؤال منيح. احكيلي شو أكلت اليوم أو شو هدفك، وبساعدك أحسب. وإذا بتحب، صوّر الأكل وأنا بقدّرلك السعرات.',
      en: "Good question. Tell me what you ate today or what your goal is and I'll work it out. You can also photograph the meal and I'll estimate it.",
    },
  },
  training: {
    text: {
      ar: 'خبّرني عن التمرين أو الوجع اللي عم تحسّ فيه بالتفصيل، وبقلّك شو المفروض تعمل. تذكّر إني بشوف إصاباتك المسجّلة قبل ما جاوب.',
      en: "Tell me more about the exercise or the pain you're feeling and I'll walk you through it. I check your recorded injuries before answering.",
    },
  },
}

export function replyTo(agent: AgentId, text: string, lang: Lang) {
  const found = REPLIES[agent].find((r) => r.match.test(text))
  const reply = found?.reply ?? FALLBACK[agent]
  return { ...reply, body: reply.text[lang] }
}
