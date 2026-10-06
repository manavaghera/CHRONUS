import { beforeEach, describe, expect, it, vi } from 'vitest'
import { applyTheme, isDark, storedTheme, THEME_EVENT } from './theme'

const systemDark = (dark) => { window.matchMedia = vi.fn(() => ({ matches: dark })) }

describe('theme', () => {
  beforeEach(() => { localStorage.clear(); delete document.documentElement.dataset.theme })

  it('follows the system until a theme is picked', () => {
    expect(storedTheme()).toBe('auto')
    systemDark(true)
    expect(isDark()).toBe(true)
    systemDark(false)
    expect(isDark()).toBe(false)
  })

  it('forces and remembers a picked theme, and tells listeners', () => {
    const heard = vi.fn()
    window.addEventListener(THEME_EVENT, heard)
    systemDark(false)
    applyTheme('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(storedTheme()).toBe('dark')
    expect(isDark()).toBe(true)
    applyTheme('auto')
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(localStorage.getItem('chronus_theme')).toBeNull()
    expect(heard).toHaveBeenCalledTimes(2)
    window.removeEventListener(THEME_EVENT, heard)
  })
})
