import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import ChatPanel from '../components/ChatPanel'
import AboutModel from '../components/AboutModel'
import { useT } from '../i18n'
import { ELON, ELON_QUICK, ELON_VOICES } from '../components/LiveDemo'

// Questions stay in English, like most archives they search
const CUSTOM_QUICK = ['What was your favourite birthday?', 'What did you love about your work?', 'What are you most proud of?', 'What advice would you give me?']

function greeting(t, persona) {
  if (persona.id === ELON.id) return t('chat.greet.elon')
  if (persona.kind === 'pretrained') return t('chat.greet.pretrained', { name: persona.name, description: persona.description || '' })
  if (persona.memorial) return t('chat.greet.memorial', { name: persona.name })
  return t('chat.greet.custom', { name: persona.name })
}

function disclaimer(t, persona) {
  if (persona.id === ELON.id) return t('chat.disc.elon')
  if (persona.kind === 'pretrained') {
    return t('chat.disc.pretrained', { name: persona.name, titles: persona.sources.map(s => s.title).join(', ') })
  }
  if (persona.memorial) return t('chat.disc.memorial', { name: persona.name })
  return t('chat.disc.custom')
}

export default function ChatPage({ id }) {
  const t = useT()
  const [persona, setPersona] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setPersona(null)
    setError('')
    api.persona(id).then(setPersona).catch(e => setError(e.message))
  }, [id])

  const notReady = persona && persona.status !== 'ready'
  const quick = !persona ? [] : persona.id === ELON.id ? ELON_QUICK
    : persona.suggested_questions?.length ? persona.suggested_questions : CUSTOM_QUICK

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <button className="page-back" onClick={() => navigate('/models')}>{t('chat.allModels')}</button>
        <div className="eyebrow eyebrow--accent">{persona?.kind === 'custom' ? t('chat.yourModel') : t('chat.pretrainedModel')}</div>
        <h1 className="page-h1">{persona?.name || (error ? t('chat.notFound') : t('common.loading'))}</h1>
        {persona?.description && <p className="page-sub">{persona.description}</p>}
        {persona && (
          <div className="page-links">
            <button className="page-link" onClick={() => navigate(`/memories/${persona.id}`)}>{t('chat.browseMemories')}</button>
            <button className="page-link" onClick={() => navigate(`/insights/${persona.id}`)}>{t('chat.insights')}</button>
            <button className="page-link" onClick={() => navigate(`/roundtable/${persona.id}`)}>{t('chat.addRoundtable')}</button>
          </div>
        )}
      </section>

      <section className="shell page-section page-chat">
        {error && <div className="page-alert">{error}</div>}
        {notReady && (
          <div className="page-alert">
            {t('chat.notBuilt', { name: persona.name })}{' '}
            <button className="page-link" onClick={() => navigate(`/create/${persona.id}`)}>{t('chat.finish')}</button>
          </div>
        )}
        {persona && !notReady && (
          <ChatPanel
            key={persona.id}
            tall
            persist
            persona={{ id: persona.id, name: persona.name, kind: persona.kind, memorial: persona.memorial, memories: persona.memories, allowAiVoice: persona.allow_cloud_llm, hasVoice: !!persona.voice, standInVoice: !!persona.stand_in_voice }}
            greeting={greeting(t, persona)}
            quick={quick}
            voiceGroup={persona.id === ELON.id ? ELON_VOICES : undefined}
          />
        )}
        {persona && !notReady && <AboutModel personaId={persona.id} />}
        {persona && <p className="demo-disclaimer">{disclaimer(t, persona)}</p>}
      </section>
    </div>
  )
}
