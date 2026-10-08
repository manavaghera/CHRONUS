import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AnswerText, { plain } from './AnswerText'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
const sources = [{ citation: 'Interview, 2015' }, { source_file: 'letters.txt' }]
const html = (text, s = sources) => renderToStaticMarkup(<AnswerText text={text} sources={s} />)

describe('AnswerText', () => {
  afterEach(() => { document.body.innerHTML = '' })

  it('turns [n] into a button for each source that exists', () => {
    const out = html('Mars matters [1]. So do letters [2].')
    expect(out).toContain('aria-label="Source 1"')
    expect(out).toContain('title="Source 1: Interview, 2015"')
    expect(out).toContain('title="Source 2: letters.txt"')  // falls back to the file name
    expect(out.match(/<button/g)).toHaveLength(2)
  })

  it('leaves markers without a source as text', () => {
    expect(html('Unsourced [3] and [0].')).toBe('Unsourced [3] and [0].')
    expect(html('No sources [1].', [])).toBe('No sources [1].')
  })

  it('never renders answer text as HTML', () => {
    const out = html('<img src=x onerror=alert(1)> [1]')
    expect(out).toContain('&lt;img src=x onerror=alert(1)&gt;')
    expect(out).not.toContain('<img')
  })

  it('reports which source was clicked', () => {
    const onCite = vi.fn()
    const root = document.createElement('div')
    document.body.append(root)
    act(() => createRoot(root).render(<AnswerText text="A [1] B [2]" sources={sources} onCite={onCite} />))
    act(() => root.querySelectorAll('button')[1].click())
    expect(onCite).toHaveBeenCalledWith(1)  // zero-based index into sources
  })
})

describe('plain', () => {
  it('drops citation markers and the space before them', () => {
    expect(plain('Hello [1] world [12].')).toBe('Hello world.')
    expect(plain('No markers here.')).toBe('No markers here.')
  })
})
