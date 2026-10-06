import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import ChatPanel from '../components/ChatPanel'
import { ELON, ELON_GREETING, ELON_QUICK, ELON_VOICES } from '../components/LiveDemo'

const CUSTOM_QUICK = ['What was your favourite birthday?', 'What did you love about your work?', 'What are you most proud of?', 'What advice would you give me?']

function greeting(persona) {
  if (persona.id === ELON.id) return ELON_GREETING
  if (persona.kind === 'pretrained') {
    return `I'm a CHRONUS model of ${persona.name}. ${persona.description} I answer only from these texts, and you can check the source of every reply.`
  }
  if (persona.memorial) {
    return `These are ${persona.name}'s words, kept by the people who loved them. I can only share what they wrote or said, or what family remembered, and I'll show you where each answer comes from.`
  }
  return `Hi, I'm a CHRONUS model of ${persona.name}. I only answer from the documents and interview answers added to this model, and you can check the source of every reply.`
}

function disclaimer(persona) {
  if (persona.id === ELON.id) {
    return "AI simulation built from Elon Musk's public interviews, tweets and biographies. It is not the real person and is not affiliated with him."
  }
  if (persona.kind === 'pretrained') {
    const titles = persona.sources.map(s => s.title).join(', ')
    return `AI simulation built from ${persona.name}'s public-domain writings (${titles}; Project Gutenberg). It is not the real person.`
  }
  if (persona.memorial) {
    return `A memorial archive of ${persona.name}'s words, built with consent. It is not ${persona.name}, and it is not a substitute for grief support or the people around you.`
  }
  return 'AI simulation built from memories shared with consent. It is not the real person, and it is not a substitute for grief support or professional help.'
}

export default function ChatPage({ id }) {
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
        <button className="page-back" onClick={() => navigate('/models')}>&larr; All models</button>
        <div className="eyebrow eyebrow--accent">{persona?.kind === 'custom' ? 'Your model' : 'Pretrained model'}</div>
        <h1 className="page-h1">{persona?.name || (error ? 'Model not found' : 'Loading…')}</h1>
        {persona?.description && <p className="page-sub">{persona.description}</p>}
        {persona && (
          <div className="page-links">
            <button className="page-link" onClick={() => navigate(`/memories/${persona.id}`)}>Browse its memories</button>
            <button className="page-link" onClick={() => navigate(`/insights/${persona.id}`)}>Insights</button>
            <button className="page-link" onClick={() => navigate(`/roundtable/${persona.id}`)}>Add to a roundtable</button>
          </div>
        )}
      </section>

      <section className="shell page-section page-chat">
        {error && <div className="page-alert">{error}</div>}
        {notReady && (
          <div className="page-alert">
            {persona.name} isn't built yet.{' '}
            <button className="page-link" onClick={() => navigate(`/create/${persona.id}`)}>Finish building it</button>
          </div>
        )}
        {persona && !notReady && (
          <ChatPanel
            key={persona.id}
            tall
            persist
            persona={{ id: persona.id, name: persona.name, kind: persona.kind, memorial: persona.memorial, memories: persona.memories, allowAiVoice: persona.allow_cloud_llm, hasVoice: !!persona.voice, standInVoice: !!persona.stand_in_voice }}
            greeting={greeting(persona)}
            quick={quick}
            voiceLabels={persona.id === ELON.id ? ELON_VOICES : undefined}
          />
        )}
        {persona && <p className="demo-disclaimer">{disclaimer(persona)}</p>}
      </section>
    </div>
  )
}
