import { useEffect, useRef } from 'react'

// Hero background: a slowly drifting constellation of "memories". Nearby
// memories link up, the pointer pulls a few closer, and every so often a
// pulse travels along a link, like a memory being retrieved. Drawn on a
// canvas with no images, so nothing can fail to load. Pauses when off
// screen or in a background tab; a single still frame for reduced motion.

import { THEME_EVENT } from '../theme'

// Colours come from the theme (index.css / dark.css tokens)
const cssRgb = (name, fallback) => {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  const parts = v.startsWith('#') ? [1, 3, 5].map(i => parseInt(v.slice(i, i + 2), 16)) : v.split(/\s+/).map(Number)
  return parts.length === 3 && parts.every(n => Number.isFinite(n)) ? parts : fallback
}
let ACCENT = [177, 95, 44]
let INK = [17, 17, 17]

function readColors() {
  ACCENT = cssRgb('--accent', [177, 95, 44])
  INK = cssRgb('--ink-rgb', [17, 17, 17])
}

function makeNodes(w, h, count) {
  return Array.from({ length: count }, () => {
    const warm = Math.random() < 0.35
    return {
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.12, vy: (Math.random() - 0.5) * 0.12,
      r: warm ? 1.6 + Math.random() * 2.2 : 1 + Math.random() * 1.4,
      warm,
      alpha: warm ? 0.55 + Math.random() * 0.35 : 0.18 + Math.random() * 0.2,
      phase: Math.random() * Math.PI * 2,
    }
  })
}

export default function MemoryField() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 0, h = 0, nodes = [], link = 140, frame = 0, raf = 0, visible = true
    const pointer = { x: -1e4, y: -1e4, active: false }
    const pulses = []

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      w = rect.width; h = rect.height
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const count = Math.round(Math.min(90, Math.max(28, (w * h) / 16000)))
      link = w < 640 ? 110 : 150
      nodes = makeNodes(w, h, count)
    }

    const draw = (t) => {
      ctx.clearRect(0, 0, w, h)
      // links
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j]
          const dx = a.x - b.x, dy = a.y - b.y
          const d2 = dx * dx + dy * dy
          if (d2 > link * link) continue
          const k = 1 - Math.sqrt(d2) / link
          const warm = a.warm && b.warm
          ctx.strokeStyle = `rgba(${(warm ? ACCENT : INK).join(',')},${(warm ? 0.32 : 0.1) * k})`
          ctx.lineWidth = warm ? 1 : 0.7
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke()
        }
        // pointer links
        if (pointer.active) {
          const dx = a.x - pointer.x, dy = a.y - pointer.y, d = Math.hypot(dx, dy)
          if (d < 180) {
            ctx.strokeStyle = `rgba(${ACCENT.join(',')},${0.35 * (1 - d / 180)})`
            ctx.lineWidth = 1
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(pointer.x, pointer.y); ctx.stroke()
          }
        }
      }
      // nodes
      for (const n of nodes) {
        const glow = 0.75 + 0.25 * Math.sin(t / 900 + n.phase)
        ctx.fillStyle = `rgba(${(n.warm ? ACCENT : INK).join(',')},${n.alpha * glow})`
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill()
        if (n.warm && n.r > 3) {
          ctx.fillStyle = `rgba(${ACCENT.join(',')},${0.08 * glow})`
          ctx.beginPath(); ctx.arc(n.x, n.y, n.r * 4, 0, Math.PI * 2); ctx.fill()
        }
      }
      // retrieval pulses
      for (let i = pulses.length - 1; i >= 0; i--) {
        const p = pulses[i]
        p.t += 0.018
        if (p.t >= 1) { pulses.splice(i, 1); continue }
        const x = p.a.x + (p.b.x - p.a.x) * p.t, y = p.a.y + (p.b.y - p.a.y) * p.t
        const g = ctx.createRadialGradient(x, y, 0, x, y, 10)
        g.addColorStop(0, `rgba(${ACCENT.join(',')},.9)`); g.addColorStop(1, `rgba(${ACCENT.join(',')},0)`)
        ctx.fillStyle = g
        ctx.beginPath(); ctx.arc(x, y, 10, 0, Math.PI * 2); ctx.fill()
      }
    }

    const step = (t) => {
      raf = requestAnimationFrame(step)
      if (!visible) return
      frame++
      for (const n of nodes) {
        if (pointer.active) {
          const dx = pointer.x - n.x, dy = pointer.y - n.y, d = Math.hypot(dx, dy)
          if (d < 180 && d > 1) { n.vx += (dx / d) * 0.006; n.vy += (dy / d) * 0.006 }
        }
        n.vx *= 0.985; n.vy *= 0.985
        n.vx += (Math.random() - 0.5) * 0.008; n.vy += (Math.random() - 0.5) * 0.008
        n.x += n.vx; n.y += n.vy
        if (n.x < -20) n.x = w + 20; else if (n.x > w + 20) n.x = -20
        if (n.y < -20) n.y = h + 20; else if (n.y > h + 20) n.y = -20
      }
      if (frame % 70 === 0 && pulses.length < 4) {
        const a = nodes[Math.floor(Math.random() * nodes.length)]
        const near = nodes.filter(b => b !== a && Math.hypot(a.x - b.x, a.y - b.y) < link)
        if (near.length) pulses.push({ a, b: near[Math.floor(Math.random() * near.length)], t: 0 })
      }
      draw(t)
    }

    const onMove = (e) => {
      const rect = canvas.getBoundingClientRect()
      pointer.x = e.clientX - rect.left; pointer.y = e.clientY - rect.top
      pointer.active = pointer.y >= 0 && pointer.y <= rect.height
    }
    const onLeave = () => { pointer.active = false }

    readColors()
    resize()
    const onTheme = () => { setTimeout(() => { readColors(); if (reduced) draw(0) }, 0) }
    window.addEventListener(THEME_EVENT, onTheme)
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener?.('change', onTheme)
    if (reduced) { draw(0); return () => { window.removeEventListener(THEME_EVENT, onTheme); mq.removeEventListener?.('change', onTheme) } }

    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting && !document.hidden })
    io.observe(canvas)
    const onVis = () => { visible = !document.hidden }
    document.addEventListener('visibilitychange', onVis)
    window.addEventListener('pointermove', onMove, { passive: true })
    document.documentElement.addEventListener('pointerleave', onLeave)
    raf = requestAnimationFrame(step)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect(); io.disconnect()
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('pointermove', onMove)
      document.documentElement.removeEventListener('pointerleave', onLeave)
      window.removeEventListener(THEME_EVENT, onTheme)
      mq.removeEventListener?.('change', onTheme)
    }
  }, [])

  return <canvas ref={canvasRef} className="memory-field" aria-hidden="true" />
}
