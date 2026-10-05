import { useEffect, useRef, useState, useCallback } from 'react'

const ASSET = 'https://api.getlayers.ai/storage/v1/object/public/public/assets/lumora-e8b711fc68'
const CARDS = [
  { cap: 'Grounded Responses', title: 'Every answer has a source.' },
  { cap: 'Honest Limits', title: "If it doesn't know, it says so." },
  { cap: 'Built with Permission', title: 'Not a resurrection. A remembering.' },
]
const PARTNERS = ['SBERT','ChromaDB','Flask','XTTS-v2','React','Qdrant','MLflow']
const Star = () => <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em"><path d="M12 2.5l2.9 5.88 6.49.94-4.7 4.58 1.11 6.46L12 17.9l-5.8 3.05 1.1-6.46-4.69-4.58 6.49-.94L12 2.5z"/></svg>

function LiquidReveal() {
  const containerRef = useRef(null), canvasRef = useRef(null)
  const animRef = useRef(null)
  const cleanupRef = useRef(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const container = containerRef.current, canvas = canvasRef.current
    if (!container || !canvas) return
    const ctx = canvas.getContext('2d')
    const BR = 143, DECAY = .016, DPR = Math.min(devicePixelRatio, 2), FF = 120
    let coverC, coverX, brushC, brushX, pts = [], lp = null, idle = 0, rad, diam, bL = false, aL = false
    let destroyed = false

    const bi = new Image()
    bi.crossOrigin = 'anonymous'
    bi.onload = () => { bL = true; if (aL && !destroyed) startC() }
    bi.onerror = () => { bL = true }
    bi.src = ASSET + '/hero/after.jpg'

    const ai = new Image()
    ai.crossOrigin = 'anonymous'
    ai.onload = () => { aL = true; if (bL && !destroyed) startC() }
    ai.onerror = () => { aL = true }
    ai.src = ASSET + '/hero/before.jpg'

    function startC() { resize(); setupP(); tick() }

    function resize() {
      if (destroyed) return
      const r = container.getBoundingClientRect()
      canvas.width = Math.round(r.width * DPR)
      canvas.height = Math.round(r.height * DPR)
      canvas.style.width = r.width + 'px'
      canvas.style.height = r.height + 'px'
      rad = Math.round(BR * DPR)
      diam = Math.ceil(rad * 2)
      coverC = document.createElement('canvas')
      coverC.width = canvas.width
      coverC.height = canvas.height
      coverX = coverC.getContext('2d')
      const sc = Math.max(coverC.width / ai.naturalWidth, coverC.height / ai.naturalHeight)
      coverX.drawImage(ai, (coverC.width - ai.naturalWidth * sc) / 2, (coverC.height - ai.naturalHeight * sc) / 2, ai.naturalWidth * sc, ai.naturalHeight * sc)
      brushC = document.createElement('canvas')
      brushC.width = diam
      brushC.height = diam
      brushX = brushC.getContext('2d')
    }

    const ro = new ResizeObserver(() => { if (bL && aL && !destroyed) resize() })
    ro.observe(container)

    function handlePointerMove(e) {
      if (destroyed) return
      const r = canvas.getBoundingClientRect()
      const x = (e.clientX - r.left) * DPR
      const y = (e.clientY - r.top) * DPR
      if (x < -rad || x > canvas.width + rad || y < -rad || y > canvas.height + rad) { lp = null; return }
      if (lp) {
        const dx = x - lp.x, dy = y - lp.y, d = Math.hypot(dx, dy), st = Math.max(rad * .3, 1), n = Math.min(Math.ceil(d / st), 60)
        for (let i = 1; i <= n; i++) pts.push({ x: lp.x + dx * i / n, y: lp.y + dy * i / n })
      } else {
        pts.push({ x, y })
      }
      lp = { x, y }
      idle = 0
    }

    function setupP() { addEventListener('pointermove', handlePointerMove) }

    function stamp(x, y) {
      const c = rad
      brushX.clearRect(0, 0, diam, diam)
      brushX.globalCompositeOperation = 'source-over'
      const g = brushX.createRadialGradient(c, c, 0, c, c, c)
      g.addColorStop(0, 'rgba(255,255,255,1)')
      g.addColorStop(.55, 'rgba(255,255,255,.82)')
      g.addColorStop(1, 'rgba(255,255,255,0)')
      brushX.fillStyle = g
      brushX.fillRect(0, 0, diam, diam)
      brushX.globalCompositeOperation = 'source-in'
      brushX.drawImage(coverC, x - c, y - c, diam, diam, 0, 0, diam, diam)
      ctx.globalCompositeOperation = 'source-over'
      ctx.drawImage(brushC, x - c, y - c)
    }

    function tick() {
      if (destroyed) return
      animRef.current = requestAnimationFrame(tick)
      if (!pts.length) {
        idle++
        if (idle > FF) { ctx.clearRect(0, 0, canvas.width, canvas.height); return }
      } else {
        idle = 0
      }
      ctx.globalCompositeOperation = 'destination-out'
      ctx.fillStyle = `rgba(0,0,0,${pts.length ? DECAY : Math.min(DECAY + idle * .004, .5)})`
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      if (pts.length) {
        ctx.globalCompositeOperation = 'source-over'
        pts.forEach(p => stamp(p.x, p.y))
        pts = []
      }
    }

    cleanupRef.current = () => {
      destroyed = true
      if (animRef.current) cancelAnimationFrame(animRef.current)
      removeEventListener('pointermove', handlePointerMove)
      ro.disconnect()
    }

    return () => { if (cleanupRef.current) cleanupRef.current() }
  }, [])

  return (
    <div className="hero-liquid" ref={containerRef}>
      <img src={ASSET + '/hero/after.jpg'} alt="" loading="eager" />
      <canvas ref={canvasRef} aria-hidden="true" />
    </div>
  )
}

export default function Hero({ scrollToId, openModal }) {
  const [ci, setCi] = useState(0), [ex, setEx] = useState(null), [dir, setDir] = useState(1)
  const goTo = useCallback(n => { setEx(ci); setDir(n > ci ? 1 : -1); setCi(n); setTimeout(() => setEx(null), 350) }, [ci])
  return (
    <section id="home">
      <LiquidReveal />
      <div className="hero-vignette" />
      <div className="hero-watermark">CHRONUS</div>
      <div className="shell hero-content">
        <div className="hero-left">
          <div className="hero-eyebrow">Memory, not mimicry</div>
          <h1 className="hero-h1">
            <span className="line-clip hero-line"><span>Their words.</span></span>
            <span className="line-clip hero-line"><span style={{ transitionDelay: '.12s' }}>Their voice.</span></span>
            <span className="line-clip hero-line"><span style={{ transitionDelay: '.24s' }}>Never invented.</span></span>
          </h1>
          <div className="hero-rating"><span className="stars">{[...Array(5)].map((_, i) => <Star key={i} />)}</span><span className="rating-text">A consent-built archive you can talk to</span></div>
          <div className="hero-ctas">
            <button className="pill-btn pill-btn--dark pill-btn--with-arrow" onClick={openModal}><span className="pill-inner">Start with Consent<span className="pill-badge pill-arrow-upright"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9" /></svg></span></span></button>
            <button className="pill-btn pill-btn--outline" onClick={() => scrollToId('demo')}><span className="pill-inner">Try Live Demo</span></button>
          </div>
          <div className="hero-trust">Consent-first <span>&middot;</span> Human-reviewed <span>&middot;</span> Nothing invented</div>
        </div>
        <div className="hero-right">
          <div className="hero-card">
            <div className="hero-card-inner" onClick={() => goTo((ci + 1) % 3)}>
              <div className="hero-card-tile"><svg viewBox="0 0 48 48" fill="currentColor" width="2rem" height="2rem" style={{ color: 'var(--accent-from)' }}><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z" /></svg></div>
              <div className="hero-card-panel">
                <div className="hero-card-slot">
                  {CARDS.map((c, i) => { let cls = 'hero-card-item'; if (i === ci) cls += ' active'; else if (i === ex) cls += (dir > 0 ? ' exit-up' : ' exit-down'); else cls += ' hidden'; return <div key={i} className={cls}><span className="card-caption">{c.cap}</span><span className="card-title">{c.title}</span></div> })}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', marginTop: '.5rem' }}>
                  <div className="hero-card-dots">{CARDS.map((_, i) => <span key={i} className={`dot${i === ci ? ' active' : ''}`} />)}</div>
                  <div className="card-nav-btns">
                    <button className="card-nav-btn" onClick={e => { e.stopPropagation(); goTo((ci - 1 + 3) % 3) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: 'rotate(180deg)' }}><path d="M5 12h14M13 6l6 6-6 6" /></svg></button>
                    <button className="card-nav-btn" onClick={e => { e.stopPropagation(); goTo((ci + 1) % 3) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg></button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="hero-partners">
            <div className="partners-label">Built on</div>
            <div className="partners-grid">{PARTNERS.map(n => <span key={n} className="partner-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none" /></svg>{n}</span>)}</div>
          </div>
        </div>
      </div>
      <div className="hero-status"><div className="shell hero-status-inner"><span>Research since 2024</span><span className="status-center">Parul University — B.Tech Project</span><span>Scroll to explore &darr;</span></div></div>
    </section>
  )
}