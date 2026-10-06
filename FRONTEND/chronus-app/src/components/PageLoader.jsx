import { useEffect, useRef } from 'react'

export default function PageLoader({ stopScroll, onReady }) {
  const elRef = useRef(null)

  useEffect(() => {
    stopScroll()
    const fill = elRef.current?.querySelector('.loader-fill')
    const count = elRef.current?.querySelector('.loader-count')
    const center = elRef.current?.querySelector('.loader-center')
    const el = elRef.current
    const FILL_MS = 1300
    const ease = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2
    const start = performance.now()

    function animate(now) {
      const t = Math.min((now - start) / FILL_MS, 1)
      const p = Math.round(ease(t) * 100)
      if (fill) fill.style.width = p + '%'
      if (count) count.textContent = String(p).padStart(3, '0')
      if (t < 1) requestAnimationFrame(animate); else exit()
    }
    requestAnimationFrame(animate)

    function exit() {
      if (center) { center.style.opacity = '0'; center.style.transform = 'translateY(-12px)' }
      el.style.transition = 'transform .7s cubic-bezier(.22,1,.36,1)'
      el.style.transform = 'translateY(-100%)'
      function onEnd(e) { if (e.propertyName !== 'transform') return; el.removeEventListener('transitionend', onEnd); onReady(); el.remove() }
      el.addEventListener('transitionend', onEnd)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- runs once on page load

  return (
    <div id="page-loader" ref={elRef}>
      <div className="loader-center">
        <div className="loader-brand">
          <svg viewBox="0 0 48 48" fill="currentColor"><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z"/></svg>
          CHRONUS
        </div>
        <p className="loader-tagline">Their words. Their voice. Their memory — never invented.</p>
      </div>
      <div className="loader-progress">
        <div className="loader-track"><div className="loader-fill" /></div>
        <div className="loader-info"><span>Initializing</span><span className="loader-count">000</span></div>
      </div>
    </div>
  )
}