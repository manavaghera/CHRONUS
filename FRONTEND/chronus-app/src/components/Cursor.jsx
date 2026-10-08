import { useEffect, useRef } from 'react'

// A soft ring that trails the pointer, grows over anything clickable and
// shows a label over elements with data-cursor="Label". The system cursor
// stays visible; this only decorates it. Off for touch and reduced motion.
export default function Cursor() {
  const dot = useRef(null)
  const ring = useRef(null)
  const label = useRef(null)

  useEffect(() => {
    if (!document.documentElement.classList.contains('motion') || window.matchMedia?.('(hover: none)').matches) return
    const root = document.documentElement
    let x = -100, y = -100, rx = -100, ry = -100, raf = 0
    const loop = () => {
      rx += (x - rx) * 0.18
      ry += (y - ry) * 0.18
      if (ring.current) ring.current.style.translate = `${rx.toFixed(1)}px ${ry.toFixed(1)}px`
      raf = Math.abs(x - rx) + Math.abs(y - ry) > 0.2 ? requestAnimationFrame(loop) : 0
    }
    const move = (e) => {
      x = e.clientX; y = e.clientY
      root.classList.add('cur-on')
      if (dot.current) dot.current.style.translate = `${x}px ${y}px`
      const target = e.target.closest?.('[data-cursor], a, button, label, input[type="range"], canvas')
      const text = target?.closest?.('[data-cursor]')?.dataset.cursor || ''
      ring.current?.classList.toggle('is-hover', !!target && !text)
      ring.current?.classList.toggle('is-label', !!text)
      if (label.current && label.current.textContent !== text) label.current.textContent = text
      if (!raf) raf = requestAnimationFrame(loop)
    }
    const leave = () => root.classList.remove('cur-on')
    const down = () => ring.current?.classList.add('is-down')
    const up = () => ring.current?.classList.remove('is-down')
    window.addEventListener('pointermove', move, { passive: true })
    document.addEventListener('pointerleave', leave)
    window.addEventListener('pointerdown', down)
    window.addEventListener('pointerup', up)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', move)
      document.removeEventListener('pointerleave', leave)
      window.removeEventListener('pointerdown', down)
      window.removeEventListener('pointerup', up)
      root.classList.remove('cur-on')
    }
  }, [])

  return (
    <>
      <div className="cur-dot" ref={dot} aria-hidden="true" />
      <div className="cur-ring" ref={ring} aria-hidden="true"><span ref={label} /></div>
    </>
  )
}
