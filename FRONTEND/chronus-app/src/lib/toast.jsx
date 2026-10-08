import { createContext, useCallback, useContext, useRef, useState } from 'react'

const ToastContext = createContext(() => {})

// One status message at a time, announced to screen readers
export function ToastProvider({ children }) {
  const [msg, setMsg] = useState('')
  const [on, setOn] = useState(false)
  const timer = useRef(0)
  const show = useCallback((text) => {
    setMsg(text); setOn(true)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setOn(false), 2800)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className={`toast${on ? ' is-on' : ''}`} role="status" aria-live="polite">{msg}</div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
