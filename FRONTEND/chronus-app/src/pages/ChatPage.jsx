import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import ChatPanel from '../components/ChatPanel'
import { ELON, ELON_GREETING, ELON_QUICK, ELON_VOICES } from '../components/LiveDemo'

const CUSTOM_QUICK = ['What was your favourite birthday?', 'What did you love about your work?', 'What are you most proud of?', 'What advice would you give me?']

export default function ChatPage({ id }) {
  const [persona, setPersona] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setPersona(null)
    setError('')
    api.persona(id).then(setPersona).catch(e => setError(e.message))
  }, [id])

  const isElon = id === ELON.id
  const notReady = persona && persona.status !== 'ready'

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <button className="page-back" onClick={() => navigate('/models')}>&larr; All models</button>
        <div className="eyebrow eyebrow--accent">{persona?.kind === 'custom' ? 'Your model' : 'Pretrained model'}</div>
        <h1 className="page-h1">{persona?.name || (error ? 'Model not found' : 'Loading…')}</h1>
        {persona?.description && <p className="page-sub">{persona.description}</p>}
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
            persona={{ id: persona.id, name: persona.name, memories: persona.memories, allowAiVoice: persona.allow_cloud_llm }}
            greeting={isElon ? ELON_GREETING
              : `Hi, I'm a CHRONUS model of ${persona.name}. I only answer from the documents and interview answers added to this model, and you can check the source of every reply.`}
            quick={isElon ? ELON_QUICK : CUSTOM_QUICK}
            voiceLabels={isElon ? ELON_VOICES : undefined}
          />
        )}
        <p className="demo-disclaimer">
          {isElon
            ? "AI simulation built from Elon Musk's public interviews, tweets and biographies. It is not the real person and is not affiliated with him."
            : 'AI simulation built from memories shared with consent. It is not the real person, and it is not a substitute for grief support or professional help.'}
        </p>
      </section>
    </div>
  )
}
