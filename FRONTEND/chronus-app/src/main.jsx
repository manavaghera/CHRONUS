import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { LanguageProvider, loadDictionaries, storedLanguage } from './i18n'
import { applyTheme, storedTheme } from './theme'
import './styles/base.css'
import './styles/home.css'
import './styles/pages.css'
import './styles/chat.css'
import './styles/extra.css'

// Before the first render, so a dark-mode reader never sees a white flash
applyTheme(storedTheme())
// Motion is opt-out: people who ask for reduced motion get a still page
if (!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) document.documentElement.classList.add('motion')

const start = () => ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <LanguageProvider>
      <App />
    </LanguageProvider>
  </React.StrictMode>
)
// A Hindi or Gujarati reader gets their language on the very first paint
if (storedLanguage() === 'en') start()
else loadDictionaries().then(start, start)
