import { beforeEach, describe, expect, it } from 'vitest'
import { clearHistory, loadHistory, saveHistory, toMarkdown } from './transcript'

describe('toMarkdown', () => {
  it('writes the conversation with sources and without citation markers', () => {
    const md = toMarkdown({ name: 'Kamla Patel' }, [
      { type: 'user', text: 'How did you teach fractions?' },
      { type: 'assistant', text: 'With mangoes [1].', meta: 'Verbatim quotes · high confidence',
        sources: [{ citation: 'Letters to Ravi', quote: 'Teaching fractions with mangoes' }, { source_file: 'diary.txt' }] },
    ])
    const lines = md.split('\n')
    expect(lines[0]).toBe('# Conversation with Kamla Patel (CHRONUS)')
    expect(lines).toContain('**You:** How did you teach fractions?')
    expect(lines).toContain('**Kamla Patel:** With mangoes.')
    expect(lines).toContain('_Verbatim quotes · high confidence_')
    expect(lines).toContain('1. Letters to Ravi — "Teaching fractions with mangoes"')
    expect(lines).toContain('2. diary.txt')
  })
})

describe('history', () => {
  beforeEach(() => localStorage.clear())

  it('keeps finished messages only, the last 100', () => {
    const msgs = Array.from({ length: 120 }, (_, i) => ({ type: 'user', text: `q${i}` }))
    saveHistory('kamla', [...msgs, { type: 'assistant', text: '…', draft: true }, { type: 'assistant', text: 'x', error: true }])
    const saved = loadHistory('kamla')
    expect(saved).toHaveLength(100)
    expect(saved[0].text).toBe('q20')
    expect(saved.at(-1).text).toBe('q119')
  })

  it('is per model, and survives bad data', () => {
    saveHistory('kamla', [{ type: 'user', text: 'hi' }])
    expect(loadHistory('elon_musk')).toBeNull()
    localStorage.setItem('chronus_chat_elon_musk', '{not json')
    expect(loadHistory('elon_musk')).toBeNull()
    localStorage.setItem('chronus_chat_elon_musk', '{"a": 1}')
    expect(loadHistory('elon_musk')).toBeNull()  // not a list
    clearHistory('kamla')
    expect(loadHistory('kamla')).toBeNull()
  })
})
