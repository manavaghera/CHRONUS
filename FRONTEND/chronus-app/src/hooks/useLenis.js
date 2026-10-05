import { useEffect } from 'react'
import Lenis from 'lenis'

let lenisInstance = null

export function getLenis() { return lenisInstance }

export function useLenis() {
  useEffect(() => {
    window.scrollTo(0, 0)
    const lenis = new Lenis({ smoothWheel: true })
    lenisInstance = lenis
    function raf(t) { lenis.raf(t); requestAnimationFrame(raf) }
    requestAnimationFrame(raf)
    return () => { lenis.destroy(); lenisInstance = null }
  }, [])
}