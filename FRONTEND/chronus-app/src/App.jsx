import { lazy, Suspense, useEffect } from 'react'
import { useRoute } from './router'
import { ToastProvider } from './lib/toast'
import { useT } from './i18n'
import Nav from './components/Nav'
import Footer from './components/Footer'
import Cursor from './components/Cursor'
import CommandPalette from './components/CommandPalette'
import LoginGate from './components/LoginGate'
import ScrollChrome from './components/ScrollChrome'
import { Intro, NotFound, Shortcuts } from './components/Extras'
import Home from './pages/Home'

// Pages load on first visit, so the landing page downloads less
const ModelsPage = lazy(() => import('./pages/ModelsPage'))
const CreatePage = lazy(() => import('./pages/CreatePage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const PretrainedPage = lazy(() => import('./pages/PretrainedPage'))
const VoicePage = lazy(() => import('./pages/VoicePage'))
const MemoriesPage = lazy(() => import('./pages/MemoriesPage'))
const InsightsPage = lazy(() => import('./pages/InsightsPage'))
const RoundtablePage = lazy(() => import('./pages/RoundtablePage'))
const PersonPage = lazy(() => import('./pages/PersonPage'))

const PAGES = {
  models: () => <ModelsPage />,
  create: (id) => <CreatePage key={id || 'new'} id={id} />,
  chat: (id) => <ChatPage key={id} id={id} />,
  pretrained: () => <PretrainedPage />,
  voice: () => <VoicePage />,
  'clone-voice': () => <VoicePage />,
  memories: (id) => <MemoriesPage key={id} id={id} />,
  insights: (id) => <InsightsPage id={id} />,
  person: (id) => <PersonPage key={id} id={id} />,
  roundtable: (id) => <RoundtablePage key={id || 'all'} id={id} />,
}

export default function App() {
  const t = useT()
  const { page, id } = useRoute()
  const render = PAGES[page]

  // A new page starts at the top; a section link (#how) from another page
  // scrolls once the home page has rendered
  useEffect(() => {
    if (page) { window.scrollTo(0, 0); return }
    const anchor = window.location.hash.slice(1)
    if (anchor && !anchor.startsWith('/')) setTimeout(() => document.getElementById(anchor)?.scrollIntoView({ behavior: 'smooth' }), 120)
  }, [page, id])

  return (
    <ToastProvider>
      <a className="skip-link" href="#main" onClick={e => { e.preventDefault(); document.getElementById('main')?.focus() }}>{t('Skip to content')}</a>
      <ScrollChrome home={!page} />
      <Nav page={render ? page : ''} />
      <main id="main" tabIndex={-1}>
        <div className="route" key={page || 'home'}>
          <Suspense fallback={<div className="page-loading" role="status"><span className="spinner" />{t('Loading…')}</div>}>
            {!page ? <Home /> : render ? render(id) : <NotFound />}
          </Suspense>
        </div>
      </main>
      <Footer />
      <CommandPalette />
      <Shortcuts />
      <Cursor />
      <LoginGate />
      <Intro />
    </ToastProvider>
  )
}
