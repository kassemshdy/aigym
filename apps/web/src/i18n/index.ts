import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import ar from './ar.json'
import en from './en.json'

export const LANGS = ['ar', 'en'] as const
export type Lang = (typeof LANGS)[number]

const STORAGE_KEY = 'aigym.lang'

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'ar' || saved === 'en') return saved
  } catch {
    /* private mode — fall through to the default */
  }
  return 'en'
}

/** The whole app mirrors from this one attribute; no component reads the language to pick sides. */
export function applyDir(lang: Lang) {
  const html = document.documentElement
  html.lang = lang
  html.dir = lang === 'ar' ? 'rtl' : 'ltr'
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    /* nothing to do — the choice just won't survive a reload */
  }
}

void i18n.use(initReactI18next).init({
  resources: { ar: { translation: ar }, en: { translation: en } },
  lng: initialLang(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

applyDir(i18n.language as Lang)
i18n.on('languageChanged', (lng) => applyDir(lng as Lang))

export default i18n
