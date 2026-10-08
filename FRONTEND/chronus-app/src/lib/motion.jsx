import { createElement, useEffect, useRef, useState } from 'react'

// Motion primitives. Everything here is decoration: with reduced motion the
// html.motion class is absent and the CSS shows the final state at once.

export const reducedMotion = () => !document.documentElement.classList.contains('motion')

// Calls onEnter once, the first time the element scrolls into view
export function useInView(onEnter, { margin = '0px 0px -8% 0px', threshold = 0.08 } = {}) {
  const ref = useRef(null)
  const cb = useRef(onEnter)
  cb.current = onEnter
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (!('IntersectionObserver' in window)) { cb.current?.(); return }
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { io.disconnect(); cb.current?.() }
    }, { rootMargin: margin, threshold })
    io.observe(el)
    return () => io.disconnect()
  }, [margin, threshold])
  return ref
}

// <Reveal> fades and lifts its content in when it scrolls into view
export function Reveal({ as = 'div', className = '', delay = 0, children, ...rest }) {
  const [inView, setInView] = useState(false)
  const ref = useInView(() => setInView(true))
  const cls = ['rv', delay ? `r${delay}` : '', inView ? 'is-in' : '', className].filter(Boolean).join(' ')
  return createElement(as, { ref, className: cls, ...rest }, children)
}

// A heading whose words rise out of a blur one after another.
// text: plain part; em: the italic serif tail.
export function SplitWords({ as = 'h2', className = '', text = '', em = '', id }) {
  const [inView, setInView] = useState(false)
  const ref = useInView(() => setInView(true))
  let i = 0
  const words = (s) => s.split(/(\s+)/).map((w, k) => (/^\s+$/.test(w) || !w ? w : <span key={k} className="w" style={{ '--i': i++ }}>{w}</span>))
  return createElement(as, { ref, id, className: `split ${inView ? 'is-in' : ''} ${className}`.trim() },
    words(text), em ? ' ' : null, em ? <em>{words(em)}</em> : null)
}

// Text that decodes from random glyphs when it scrolls into view
const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&*+/<>'
// Whole characters as the reader sees them, so a Hindi or Gujarati syllable
// and its vowel signs are never split apart mid-animation
const graphemes = (s) => (typeof Intl !== 'undefined' && Intl.Segmenter
  ? [...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(s)].map(g => g.segment)
  : [...s])
export function Scramble({ text, className = 'over', as = 'span' }) {
  // null between animations, so a new text (another language) shows at once
  const [shown, setShown] = useState(null)
  const raf = useRef(0)
  const ref = useInView(() => {
    if (reducedMotion()) return
    const chars = graphemes(text)
    const start = performance.now()
    const dur = 700 + chars.length * 18
    const tick = (now) => {
      const k = Math.min(1, (now - start) / dur)
      const fixed = Math.floor(k * chars.length)
      setShown(k < 1 ? chars.map((ch, j) => (j < fixed || ch === ' ' || ch === '—' ? ch : GLYPHS[(Math.random() * GLYPHS.length) | 0])).join('') : null)
      if (k < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
  })
  useEffect(() => () => cancelAnimationFrame(raf.current), [])
  return createElement(as, { ref, className: `${className} scramble`, 'aria-label': text },
    <span aria-hidden="true">{shown ?? text}</span>)
}

// Pulls its child toward the pointer while the pointer is near
export function Magnetic({ children, strength = 0.28, className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el || reducedMotion() || window.matchMedia?.('(hover: none)').matches) return
    const move = (e) => {
      const r = el.getBoundingClientRect()
      const x = e.clientX - (r.left + r.width / 2)
      const y = e.clientY - (r.top + r.height / 2)
      el.classList.add('is-on')
      el.style.transform = `translate(${(x * strength).toFixed(1)}px, ${(y * strength * 1.2).toFixed(1)}px)`
    }
    const leave = () => { el.classList.remove('is-on'); el.style.transform = '' }
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerleave', leave)
    return () => { el.removeEventListener('pointermove', move); el.removeEventListener('pointerleave', leave) }
  }, [strength])
  return <span ref={ref} className={`magnet ${className}`.trim()}>{children}</span>
}

// Pointer-follow tilt + glare for cards (sets --rx/--ry/--tx/--ty)
export function tiltHandlers(max = 10) {
  return {
    onPointerMove: (e) => {
      if (reducedMotion()) return
      const el = e.currentTarget
      const r = el.getBoundingClientRect()
      const x = (e.clientX - r.left) / r.width
      const y = (e.clientY - r.top) / r.height
      el.style.setProperty('--rx', ((x - 0.5) * max).toFixed(2))
      el.style.setProperty('--ry', ((0.5 - y) * max * 0.8).toFixed(2))
      el.style.setProperty('--tx', (x * 100).toFixed(1))
      el.style.setProperty('--ty', (y * 100).toFixed(1))
    },
    onPointerLeave: (e) => {
      e.currentTarget.style.setProperty('--rx', '0')
      e.currentTarget.style.setProperty('--ry', '0')
    },
  }
}

// 0..1 progress of an element through a pinned scroll range, eased with a lerp.
// Writes the value as a CSS variable on the element (no React re-render).
export function usePinnedProgress(ref, varName = '--p', onFrame) {
  const frame = useRef(onFrame)
  frame.current = onFrame
  useEffect(() => {
    const el = ref.current
    if (!el) return
    let target = 0, cur = 0, raf = 0
    const measure = () => {
      const r = el.getBoundingClientRect()
      const span = r.height - window.innerHeight
      target = span > 0 ? Math.min(1, Math.max(0, -r.top / span)) : 0
      if (!raf) raf = requestAnimationFrame(step)
    }
    const step = () => {
      raf = 0
      const d = target - cur
      cur = Math.abs(d) < 0.0005 || reducedMotion() ? target : cur + d * 0.14
      el.style.setProperty(varName, cur.toFixed(4))
      frame.current?.(cur)
      if (cur !== target) raf = requestAnimationFrame(step)
    }
    measure()
    window.addEventListener('scroll', measure, { passive: true })
    window.addEventListener('resize', measure)
    return () => { window.removeEventListener('scroll', measure); window.removeEventListener('resize', measure); cancelAnimationFrame(raf) }
  }, [ref, varName])
}

// Counts from 0 to each value when the element scrolls into view
export function useCountUp(duration = 1600) {
  const [k, setK] = useState(0)
  const ref = useInView(() => {
    if (reducedMotion()) { setK(1); return }
    const t0 = performance.now()
    const step = (t) => {
      const x = Math.min(1, (t - t0) / duration)
      setK(1 - Math.pow(1 - x, 4))
      if (x < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  })
  return [ref, k]
}
