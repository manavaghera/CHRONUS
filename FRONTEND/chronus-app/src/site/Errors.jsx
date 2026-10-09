import { Component } from 'react'
import Icon from '../lib/Icon'

// Something broke (500), and planned maintenance. Same layout as the 404 page.

function ErrorScreen({ code, title, text, children }) {
  return (
    <section className="nf" aria-labelledby="err-h">
      <div className="wrap col gap16" style={{ alignItems: 'center', textAlign: 'center' }}>
        <span className="nf-code" aria-hidden="true">{code}</span>
        <h1 id="err-h" className="h2">{title}</h1>
        <p className="lede">{text}</p>
        <div className="row wrap-row gap12" style={{ justifyContent: 'center' }}>{children}</div>
      </div>
    </section>
  )
}

export function ServerError() {
  return (
    <ErrorScreen code="500" title="Something went wrong on our side." text="Nothing you did caused this, and nothing you made has been lost. Please try again in a moment.">
      <button type="button" className="btn btn-a" onClick={() => window.location.reload()}>Try again<Icon name="arrow" /></button>
      <a className="btn btn-s" href="#/contact/support">Tell us what happened</a>
    </ErrorScreen>
  )
}

export function Maintenance() {
  return (
    <ErrorScreen code="···" title="CHRONUS is resting for a moment." text="We’re making improvements. Every model and memory is safe; please come back shortly.">
      <a className="btn btn-s" href="#/wellbeing">Need someone to talk to?</a>
    </ErrorScreen>
  )
}

/** Shows the 500 screen instead of a blank page when a page crashes */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error) {
    console.error('Page crashed:', error)
  }

  render() {
    return this.state.failed ? <ServerError /> : this.props.children
  }
}
