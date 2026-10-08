// The hero's background: flowing lines like a voice spectrum. The pointer
// bends them like a lens; scrolling pulls them together into one voiceprint.
// Returns a cleanup function. Draws a single still frame for reduced motion.
export function startVoiceField(canvas, stage, getProgress) {
  const ctx = canvas?.getContext?.('2d')
  if (!ctx || !stage) return () => {}
  const still = !document.documentElement.classList.contains('motion')
  const LINES = 30
  let W = 0, H = 0, dpr = 1, raf = 0, visible = true, colors = null
  let mx = -9999, my = -9999, tx = -9999, ty = -9999

  const readColors = () => {
    const cs = getComputedStyle(document.documentElement)
    return { ink: cs.getPropertyValue('--ink').trim() || '#111', accent: cs.getPropertyValue('--accent').trim() || '#cf3d10' }
  }

  const draw = (t) => {
    colors ||= readColors()
    const p = getProgress()
    mx += (tx - mx) * 0.12
    my += (ty - my) * 0.12
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, W, H)
    const gap = H / (LINES + 1)
    const squeeze = Math.min(1, p / 0.45)
    const cy = H * 0.52
    for (let i = 0; i < LINES; i++) {
      const base = gap * (i + 1)
      const y0 = base + (cy - base) * squeeze * 0.78
      const accent = i % 7 === 3
      const amp = (accent ? 13 : 7) + squeeze * 16
      ctx.beginPath()
      for (let x = -12; x <= W + 12; x += 12) {
        const nx = x / W
        const env = Math.sin(Math.PI * Math.min(1, Math.max(0, nx)))
        // speech-like bursts once the lines have gathered
        const talk = squeeze * Math.abs(Math.sin(nx * 5 + t * 0.0013)) * Math.sin(nx * 41 + t * 0.004 + i * 0.7) * 12
        let y = y0 + Math.sin(nx * 9 + t * 0.0006 + i * 0.5) * amp * env * 0.6 +
          Math.sin(nx * 23 - t * 0.0011 + i) * amp * 0.25 * env + talk * env
        const dx = x - mx, dy = y - my
        const f = Math.exp(-(dx * dx + dy * dy) / (2 * 120 * 120))
        y += (dy >= 0 ? 1 : -1) * f * 48
        if (x === -12) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.strokeStyle = accent ? colors.accent : colors.ink
      ctx.globalAlpha = accent ? 0.5 : 0.1 + 0.05 * Math.sin(i * 1.7)
      ctx.lineWidth = accent ? 1.3 : 1
      ctx.stroke()
    }
    ctx.globalAlpha = 1
  }

  const loop = (t) => {
    raf = 0
    draw(t)
    if (!still && visible) raf = requestAnimationFrame(loop)
  }
  const kick = () => { if (!raf) raf = requestAnimationFrame(loop) }

  const size = () => {
    const r = canvas.getBoundingClientRect()
    dpr = Math.min(2, window.devicePixelRatio || 1)
    W = r.width; H = r.height
    canvas.width = Math.max(1, Math.round(W * dpr))
    canvas.height = Math.max(1, Math.round(H * dpr))
    draw(performance.now())
  }

  const move = (e) => {
    const r = canvas.getBoundingClientRect()
    tx = e.clientX - r.left; ty = e.clientY - r.top
    if (mx < -9000) { mx = tx; my = ty }
    stage.style.setProperty('--mx', (((e.clientX - r.left) / r.width) * 2 - 1).toFixed(3))
    stage.style.setProperty('--my', (((e.clientY - r.top) / r.height) * 2 - 1).toFixed(3))
    if (still) draw(performance.now())
  }
  const leave = () => {
    tx = ty = mx = my = -9999
    stage.style.setProperty('--mx', '0'); stage.style.setProperty('--my', '0')
    if (still) draw(performance.now())
  }
  const recolor = () => { colors = null; kick() }

  size()
  const ro = window.ResizeObserver ? new ResizeObserver(size) : null
  ro?.observe(canvas)
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) kick() }) : null
  io?.observe(canvas)
  stage.addEventListener('pointermove', move)
  stage.addEventListener('pointerleave', leave)
  window.addEventListener('chronus:theme', recolor)
  const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
  mq?.addEventListener?.('change', recolor)
  kick()

  return () => {
    cancelAnimationFrame(raf)
    ro?.disconnect(); io?.disconnect()
    stage.removeEventListener('pointermove', move)
    stage.removeEventListener('pointerleave', leave)
    window.removeEventListener('chronus:theme', recolor)
    mq?.removeEventListener?.('change', recolor)
  }
}
