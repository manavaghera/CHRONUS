// Memory field: a 2-D sketch of one person's archive. The pointer is the
// question; the k nearest memories inside the threshold θ light up.
// onReadout({ hits, idk, near }) is called a few times a second when it changes.
import { tx } from '../i18n'

export const CLUSTERS = [
  { label: tx('Letters'), x: 0.12, y: 0.42, n: 18, prov: 'own' },
  { label: tx('Journals'), x: 0.27, y: 0.74, n: 16, prov: 'own' },
  { label: tx('Voice notes'), x: 0.4, y: 0.3, n: 16, prov: 'own' },
  { label: tx('Interview: personality'), x: 0.53, y: 0.68, n: 14, prov: 'own' },
  { label: tx('Interview: memories'), x: 0.66, y: 0.32, n: 14, prov: 'own' },
  { label: tx('Family’s memories'), x: 0.78, y: 0.7, n: 14, prov: 'others' },
  { label: tx('Reviewed answers'), x: 0.9, y: 0.36, n: 10, prov: 'synth' },
]

export function startField(canvas, getParams, onReadout) {
  const ctx = canvas?.getContext?.('2d')
  if (!ctx) return { stop() {}, pick() { return null } }
  const still = !document.documentElement.classList.contains('motion')
  let seed = 20261008
  const rnd = () => {
    seed = (seed + 0x6D2B79F5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const gauss = () => { let u = 0, v = 0; while (!u) u = rnd(); while (!v) v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v) }
  const pts = []
  CLUSTERS.forEach((c, ci) => {
    for (let i = 0; i < c.n; i++) {
      pts.push({ x: Math.min(0.97, Math.max(0.03, c.x + gauss() * 0.03)), y: Math.min(0.9, Math.max(0.12, c.y + gauss() * 0.075)), c: ci, prov: c.prov, ph: rnd() * 6.283, X: 0, Y: 0 })
    }
  })
  const edges = []
  pts.forEach((p, i) => {
    pts.map((q, j) => ({ j, d: q.c === p.c && j !== i ? Math.hypot((q.x - p.x) * 2.2, q.y - p.y) : 9 }))
      .sort((a, b) => a.d - b.d).slice(0, 2).forEach(nb => { if (nb.d < 9 && nb.j > i) edges.push([i, nb.j]) })
  })

  let W = 0, H = 0, dpr = 1, raf = 0, visible = true, hover = false, mx = 0, my = 0, qx = 0, qy = 0, last = 0, key = '', colors = null
  const readColors = () => {
    const cs = getComputedStyle(document.documentElement)
    const g = (n) => cs.getPropertyValue(n).trim()
    return { ink: g('--ink'), ink2: g('--ink-2'), ink3: g('--ink-3'), line: g('--line-2'), accent: g('--accent'), soft: g('--accent-soft') }
  }

  const frame = (t) => {
    raf = 0
    if (!W || !H) return
    t ||= performance.now()
    colors ||= readColors()
    const c = colors
    const { k, theta, pick, label = (s) => s } = getParams()
    let tx, ty
    if (hover) { tx = mx; ty = my } else if (still) { tx = W * 0.4; ty = H * 0.36 } else {
      const a = t * 0.0003
      tx = W * (0.5 + 0.36 * Math.sin(a)); ty = H * (0.52 + 0.26 * Math.sin(a * 1.7 + 1))
    }
    const ease = hover ? 0.3 : still ? 1 : 0.06
    qx += (tx - qx) * ease; qy += (ty - qy) * ease
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, W, H)
    pts.forEach(p => {
      p.X = p.x * W + (still ? 0 : Math.sin(t * 0.0006 + p.ph) * 3.5)
      p.Y = p.y * H + (still ? 0 : Math.cos(t * 0.0005 + p.ph) * 3.5)
    })
    ctx.lineWidth = 1; ctx.strokeStyle = c.line; ctx.globalAlpha = 0.9
    edges.forEach(([a, b]) => { ctx.beginPath(); ctx.moveTo(pts[a].X, pts[a].Y); ctx.lineTo(pts[b].X, pts[b].Y); ctx.stroke() })
    ctx.font = '500 10px "Geist Mono", ui-monospace, monospace'; ctx.textAlign = 'center'; ctx.fillStyle = c.ink3
    CLUSTERS.forEach(cl => ctx.fillText(label(cl.label).toUpperCase(), cl.x * W, Math.max(16, cl.y * H - 0.2 * H)))

    const cand = pts.map((p, i) => ({ i, d: Math.hypot(p.X - qx, p.Y - qy) / H })).sort((a, b) => a.d - b.d)
    const hits = cand.filter(x => x.d <= theta).slice(0, k)
    const near = cand[0]
    ctx.beginPath(); ctx.arc(qx, qy, theta * H, 0, Math.PI * 2)
    if (hits.length) { ctx.fillStyle = c.soft; ctx.globalAlpha = 1; ctx.fill() }
    ctx.setLineDash([4, 5]); ctx.lineWidth = 1.2; ctx.strokeStyle = hits.length ? c.accent : c.ink3; ctx.globalAlpha = 0.85; ctx.stroke(); ctx.setLineDash([])
    ctx.globalAlpha = 1
    if (hits.length) {
      ctx.strokeStyle = c.accent; ctx.lineWidth = 1.3
      hits.forEach(h => { ctx.beginPath(); ctx.moveTo(qx, qy); ctx.lineTo(pts[h.i].X, pts[h.i].Y); ctx.stroke() })
    } else if (near) {
      ctx.setLineDash([2, 4]); ctx.strokeStyle = c.ink3; ctx.lineWidth = 1
      ctx.beginPath(); ctx.moveTo(qx, qy); ctx.lineTo(pts[near.i].X, pts[near.i].Y); ctx.stroke(); ctx.setLineDash([])
    }
    const rank = {}
    hits.forEach((h, n) => { rank[h.i] = n + 1 })
    pts.forEach((p, i) => {
      if (rank[i]) {
        ctx.fillStyle = c.accent
        ctx.globalAlpha = 0.22; ctx.beginPath(); ctx.arc(p.X, p.Y, 11, 0, 6.283); ctx.fill()
        ctx.globalAlpha = 1; ctx.beginPath(); ctx.arc(p.X, p.Y, 5, 0, 6.283); ctx.fill()
        ctx.fillStyle = c.ink; ctx.fillText(String(rank[i]), p.X, p.Y - 15)
        return
      }
      ctx.globalAlpha = 1
      if (p.prov === 'others') { ctx.strokeStyle = c.ink2; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(p.X, p.Y, 3, 0, 6.283); ctx.stroke() }
      else if (p.prov === 'synth') { ctx.fillStyle = c.ink3; ctx.fillRect(p.X - 2.4, p.Y - 2.4, 4.8, 4.8) }
      else { ctx.fillStyle = c.ink2; ctx.beginPath(); ctx.arc(p.X, p.Y, 2.5, 0, 6.283); ctx.fill() }
    })
    if (pick != null && pts[pick]) { ctx.strokeStyle = c.ink; ctx.lineWidth = 1.3; ctx.beginPath(); ctx.arc(pts[pick].X, pts[pick].Y, 9, 0, 6.283); ctx.stroke() }
    ctx.strokeStyle = c.accent; ctx.fillStyle = c.accent; ctx.lineWidth = 1.6
    ctx.beginPath(); ctx.arc(qx, qy, 4, 0, 6.283); ctx.fill()
    ctx.beginPath()
    ctx.moveTo(qx - 15, qy); ctx.lineTo(qx - 8, qy); ctx.moveTo(qx + 8, qy); ctx.lineTo(qx + 15, qy)
    ctx.moveTo(qx, qy - 15); ctx.lineTo(qx, qy - 8); ctx.moveTo(qx, qy + 8); ctx.lineTo(qx, qy + 15)
    ctx.stroke()

    if (t - last > 160) {
      last = t
      const next = `${k}|${theta}|${hits.map(h => `${h.i}:${h.d.toFixed(2)}`).join(',')}|${hits.length ? '' : near?.d.toFixed(2)}`
      if (next !== key) {
        key = next
        onReadout({
          hits: hits.map((h, n) => ({ n: n + 1, label: CLUSTERS[pts[h.i].c].label, prov: pts[h.i].prov, d: h.d.toFixed(3) })),
          idk: !hits.length, near: near ? near.d.toFixed(3) : '',
        })
      }
    }
    const settled = Math.abs(tx - qx) < 0.5 && Math.abs(ty - qy) < 0.5
    if (visible && (!still || hover || !settled)) raf = requestAnimationFrame(frame)
  }
  const kick = () => { if (!raf && visible) raf = requestAnimationFrame(frame) }
  const size = () => {
    const r = canvas.getBoundingClientRect()
    dpr = Math.min(2, window.devicePixelRatio || 1)
    W = r.width; H = r.height
    canvas.width = Math.max(1, Math.round(W * dpr)); canvas.height = Math.max(1, Math.round(H * dpr))
    if (!qx) { qx = W * 0.4; qy = H * 0.4 }
    kick()
  }
  const move = (e) => { const r = canvas.getBoundingClientRect(); mx = e.clientX - r.left; my = e.clientY - r.top; hover = true; kick() }
  const leave = () => { hover = false; kick() }
  const recolor = () => { colors = null; kick() }
  size()
  const ro = window.ResizeObserver ? new ResizeObserver(size) : null
  ro?.observe(canvas)
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick() }) : null
  io?.observe(canvas)
  canvas.addEventListener('pointermove', move)
  canvas.addEventListener('pointerleave', leave)
  window.addEventListener('chronus:theme', recolor)
  const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
  mq?.addEventListener?.('change', recolor)

  return {
    kick,
    pick(clientX, clientY) {
      const r = canvas.getBoundingClientRect()
      let best = null, bd = 16
      pts.forEach((p, i) => { const d = Math.hypot(p.X - (clientX - r.left), p.Y - (clientY - r.top)); if (d < bd) { bd = d; best = i } })
      return best == null ? null : { i: best, label: CLUSTERS[pts[best].c].label, prov: pts[best].prov }
    },
    stop() {
      cancelAnimationFrame(raf); ro?.disconnect(); io?.disconnect()
      canvas.removeEventListener('pointermove', move); canvas.removeEventListener('pointerleave', leave)
      window.removeEventListener('chronus:theme', recolor); mq?.removeEventListener?.('change', recolor)
    },
  }
}
