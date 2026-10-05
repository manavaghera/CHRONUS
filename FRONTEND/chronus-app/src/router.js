import { useEffect, useState } from 'react'

// Tiny hash router: pages live at #/models, #/create, #/chat/<id>...
// Hash routing needs no server config and no extra dependency. Plain anchors
// like #demo (landing-page sections) don't start with "/" and stay on home.
function currentPath() {
  const hash = window.location.hash
  return hash.startsWith('#/') ? hash.slice(1) : '/'
}

export function navigate(path) {
  window.location.hash = path === '/' ? '' : path
}

export function useRoute() {
  const [path, setPath] = useState(currentPath)
  useEffect(() => {
    const onChange = () => setPath(currentPath())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const [, page = '', id = ''] = path.split('/')
  return { path, page, id: decodeURIComponent(id) }
}
