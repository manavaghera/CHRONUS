import { useEffect, useRef } from 'react'

// Accessible dialog behaviour: focus moves into the dialog when it opens,
// Tab stays inside it, Escape closes it, and focus returns to whatever
// opened it when it closes.
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export default function useDialog(open, onClose) {
  const ref = useRef(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  useEffect(() => {
    if (!open || !ref.current) return
    const opener = document.activeElement
    const node = ref.current
    const items = () => [...node.querySelectorAll(FOCUSABLE)].filter(el => el.offsetParent !== null || el === document.activeElement)
    const first = node.querySelector('[autofocus]') || items()[0]
    setTimeout(() => (first || node).focus?.(), 0)
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); closeRef.current?.(); return }
      if (e.key !== 'Tab') return
      const list = items()
      if (!list.length) return
      const [head, tail] = [list[0], list[list.length - 1]]
      if (e.shiftKey && document.activeElement === head) { e.preventDefault(); tail.focus() }
      else if (!e.shiftKey && document.activeElement === tail) { e.preventDefault(); head.focus() }
    }
    node.addEventListener('keydown', onKey)
    return () => {
      node.removeEventListener('keydown', onKey)
      if (opener && document.contains(opener)) opener.focus?.()
    }
  }, [open])

  return ref
}
