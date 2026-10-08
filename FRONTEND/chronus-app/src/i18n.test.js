import { describe, expect, it } from 'vitest'
import { loadDictionaries, translate } from './i18n'
import { DICTS, TRIPLES } from './strings/index.js'

// Every English string the app passes to t('…') or tx('…') must have a
// Hindi and a Gujarati entry, with the same {placeholders} and | splits.
const sources = import.meta.glob(['./**/*.{js,jsx}', '!./**/*.test.*', '!./strings/**'], { query: '?raw', import: 'default', eager: true })
const CALL = /\bt[x]?\(\s*'((?:[^'\\]|\\.)*)'/g
const used = new Set()
for (const text of Object.values(sources)) for (const m of text.matchAll(CALL)) used.add(m[1].replace(/\\'/g, "'"))

const vars = (s) => (s.match(/\{\w+\}/g) || []).sort().join(' ')
const bars = (s) => s.split('|').length

describe('translations', () => {
  it('finds the strings in the source', () => {
    expect(used.size).toBeGreaterThan(500)
    expect(used.has('Preserve someone')).toBe(true)
  })

  it.each(['hi', 'gu'])('covers every UI string in %s', (lang) => {
    expect([...used].filter(s => !DICTS[lang][s])).toEqual([])
  })

  it('keeps placeholders and | splits intact', () => {
    const broken = TRIPLES.filter(([en, hi, gu]) => [hi, gu].some(s => !s || vars(s) !== vars(en) || bars(s) !== bars(en)))
    expect(broken).toEqual([])
  })

  it('has no duplicate English keys', () => {
    const seen = new Set()
    expect(TRIPLES.map(r => r[0]).filter(k => seen.has(k) || !seen.add(k))).toEqual([])
  })

  it('falls back to English and fills placeholders', async () => {
    expect(translate('hi', 'Talk to {name}', { name: 'Ada' })).toBe('Talk to Ada') // not loaded yet
    await loadDictionaries()
    expect(translate('hi', 'Not a translated line {n}', { n: 3 })).toBe('Not a translated line 3')
    expect(translate('en', 'Talk to {name}', { name: 'Ada' })).toBe('Talk to Ada')
    expect(translate('gu', 'Talk to {name}', { name: 'Ada' })).toBe('Ada સાથે વાત કરો')
    expect(translate('hi', 'Talk to {name}', { name: 'Ada' })).toBe('Ada से बात करें')
    expect(translate('xx', 'Talk to {name}', { name: 'Ada' })).toBe('Talk to Ada')
  })
})
