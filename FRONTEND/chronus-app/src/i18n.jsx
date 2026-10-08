import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

// The website in English, Hindi and Gujarati. The English text is the key:
// t('Preserve someone') looks it up in the chosen language and falls back to
// English. {name}-style placeholders are filled from vars. Text kept in data
// arrays is marked with tx() so the coverage test (i18n.test.js) finds it.
// A heading whose word order differs between languages is one key split on
// '|': halves(t('Gather|their words.')) emphasises the second part.
// The Hindi and Gujarati were drafted for CHRONUS; have a native speaker check them.

export const LANGUAGES = [['en', 'English', 'EN'], ['hi', 'हिन्दी', 'हि'], ['gu', 'ગુજરાતી', 'ગુ']]
const KEY = 'chronus-language'

export const tx = (s) => s
export function halves(s) {
  const [a, b = ''] = s.split('|')
  return <>{a} <em>{b}</em></>
}

// The Hindi and Gujarati tables (strings/) download only when someone picks
// one, so English readers never pay for them
let dicts = null
let loading = null
export const loadDictionaries = () => (loading ??= import('./strings/index.js').then(m => (dicts = m.DICTS)))

const fill = (s, vars) => (vars ? s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] ?? m)) : s)
export function translate(lang, text, vars) {
  const d = dicts?.[lang]
  return fill((d && d[text]) || text, vars)
}

export function storedLanguage() {
  try { const v = localStorage.getItem(KEY); return LANGUAGES.some(l => l[0] === v) ? v : 'en' } catch { return 'en' }
}

const Ctx = createContext({ lang: 'en', setLang: () => {}, t: (s, v) => fill(s, v) })

export function LanguageProvider({ children }) {
  const [lang, setLangNow] = useState(storedLanguage)
  useEffect(() => {
    document.documentElement.lang = lang
    try { localStorage.setItem(KEY, lang) } catch { /* storage blocked */ }
  }, [lang])
  // Switch only once the table is here, so the page never flickers through English
  const setLang = useCallback((next) => {
    if (next === 'en') setLangNow(next)
    else loadDictionaries().then(() => setLangNow(next), () => {})
  }, [])
  const t = useCallback((s, v) => translate(lang, s, v), [lang])
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useT = () => useContext(Ctx).t
export const useLanguage = () => useContext(Ctx)
