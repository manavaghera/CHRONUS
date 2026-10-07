import { describe, expect, it } from 'vitest'
import { LANGUAGE_STRINGS, LANGUAGES, STRING_KEYS, STRING_SOURCES, translate } from './i18n'

describe('i18n', () => {
  it('has every string in Hindi and Gujarati, and nothing extra', () => {
    for (const [code] of LANGUAGES) {
      expect(Object.keys(LANGUAGE_STRINGS[code]).sort()).toEqual([...STRING_KEYS].sort())
    }
  })

  it('keeps the same placeholders in every language', () => {
    const names = (text) => [...text.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort()
    for (const key of STRING_KEYS) {
      for (const [code] of LANGUAGES) {
        expect(names(LANGUAGE_STRINGS[code][key]), `${code} ${key}`).toEqual(names(LANGUAGE_STRINGS.en[key]))
      }
    }
  })

  it('defines each string in one file only', () => {
    const keys = Object.values(STRING_SOURCES).flatMap(s => Object.keys(s.en))
    expect(keys.filter((k, i) => keys.indexOf(k) !== i)).toEqual([])
  })

  it('fills placeholders and falls back to English', () => {
    expect(translate('gu', 'create.chatWith', { name: 'Amma' })).toBe('Amma સાથે વાત કરો')
    expect(translate('hi', 'create.chatWith', { name: 'Amma' })).toBe('Amma से बात करें')
    expect(translate('xx', 'nav.models')).toBe('Models')
    expect(translate('gu', 'no.such.key')).toBe('no.such.key')
  })
})
