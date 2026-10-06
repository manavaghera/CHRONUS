import { useState, useCallback, useEffect } from 'react'
import { useLenis, getLenis } from './hooks/useLenis'
import PageLoader from './components/PageLoader'
import Header from './components/Header'
import Hero from './components/Hero'
import Marquee from './components/Marquee'
import LiveDemo from './components/LiveDemo'
import WhySection from './components/WhySection'
import Band from './components/Band'
import TrustSection from './components/TrustSection'
import UnderHood from './components/UnderHood'
import Roadmap from './components/Roadmap'
import FAQ from './components/FAQ'
import Footer from './components/Footer'
import NavMenu from './components/NavMenu'
import RequestModal from './components/RequestModal'
import LoginGate from './components/LoginGate'
import TrainYourModel from './components/TrainYourModel'
import ModelGallery from './components/ModelGallery'
import ModelsPage from './pages/ModelsPage'
import ChatPage from './pages/ChatPage'
import CreatePage from './pages/CreatePage'
import CloneVoicePage from './pages/CloneVoicePage'
import { navigate, useRoute } from './router'
import './pages.css'

// Header/menu targets that are pages rather than landing-page sections
const PAGES = new Set(['models', 'create', 'clone-voice'])

function App() {
  useLenis()
  const { page, id } = useRoute()
  const [ready, setReady] = useState(false)
  const [navOpen, setNavOpen] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)

  const stopScroll = useCallback(() => {
    getLenis()?.stop()
    Object.assign(document.documentElement.style, { position: 'relative', overflow: 'hidden', height: '100%' })
  }, [])

  const startScroll = useCallback(() => {
    getLenis()?.start()
    ;['position', 'overflow', 'height'].forEach(p => document.documentElement.style.removeProperty(p))
  }, [])

  const scrollToId = useCallback((id) => {
    const el = document.getElementById(id)
    if (!el) return
    getLenis()?.stop()
    setTimeout(() => window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset, behavior: 'smooth' }), 50)
    setTimeout(() => getLenis()?.start(), 100)
  }, [])

  const openNav = useCallback(() => { setNavOpen(true); stopScroll() }, [stopScroll])
  const closeNav = useCallback(() => { setNavOpen(false); startScroll() }, [startScroll])
  const openModal = useCallback(() => { setModalOpen(true); stopScroll() }, [stopScroll])
  const closeModal = useCallback(() => { setModalOpen(false); startScroll() }, [startScroll])

  const handleReady = useCallback(() => {
    setReady(true)
    document.body.classList.add('ready')
    startScroll()
  }, [startScroll])

  useEffect(() => {
    const h = (e) => {
      if (e.key === 'Escape') { if (modalOpen) closeModal(); else if (navOpen) closeNav() }
    }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [navOpen, modalOpen, closeModal, closeNav])

  // A section id ("demo") scrolls on the landing page, a page id ("models")
  // opens that page; sections clicked from a sub-page go home first.
  const go = useCallback((target) => {
    if (target === 'contact') { openModal(); return }
    if (PAGES.has(target)) { navigate(`/${target}`); return }
    if (page) { navigate('/'); setTimeout(() => scrollToId(target), 150); return }
    scrollToId(target)
  }, [page, openModal, scrollToId])

  const handleNav = useCallback((target) => {
    closeNav()
    setTimeout(() => go(target), target === 'contact' ? 200 : 100)
  }, [closeNav, go])

  // New page: start at the top. Back on home via a footer anchor (#demo):
  // scroll to that section once the landing page has rendered.
  useEffect(() => {
    if (page) { getLenis()?.scrollTo(0, { immediate: true }); window.scrollTo(0, 0); return }
    const anchor = window.location.hash.slice(1)
    if (anchor && !anchor.startsWith('/')) setTimeout(() => scrollToId(anchor), 150)
  }, [page, id, scrollToId])

  return (
    <>
      <PageLoader stopScroll={stopScroll} onReady={handleReady} />
      <Header go={go} openNav={openNav} />
      <main id="main">
        {page === 'models' && <ModelsPage />}
        {page === 'chat' && <ChatPage id={id} />}
        {page === 'create' && <CreatePage key={id || 'new'} id={id} />}
        {page === 'clone-voice' && <CloneVoicePage />}
        {!PAGES.has(page) && page !== 'chat' && (
          <>
            <Hero scrollToId={scrollToId} />
            <Marquee />
            <LiveDemo />
            <ModelGallery />
            <WhySection />
            <Band />
            <TrainYourModel />
            <TrustSection />
            <UnderHood />
            <Roadmap />
            <FAQ />
          </>
        )}
      </main>
      <Footer />
      <NavMenu open={navOpen} onClose={closeNav} onNav={handleNav} onCta={() => { closeNav(); setTimeout(openModal, 200) }} />
      <RequestModal open={modalOpen} onClose={closeModal} />
      <LoginGate />
    </>
  )
}

export default App