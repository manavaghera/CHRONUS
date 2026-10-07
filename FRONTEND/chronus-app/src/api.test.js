import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, LOGIN_EVENT, OFFLINE_MSG } from './api'

const enc = new TextEncoder()
// A response whose body arrives in the given pieces (split anywhere, like a network)
const streamed = (pieces, status = 200) => new Response(new ReadableStream({
  start(c) { pieces.forEach(p => c.enqueue(enc.encode(p))); c.close() },
}), { status, headers: { 'Content-Type': 'text/event-stream' } })
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const mockFetch = (impl) => vi.stubGlobal('fetch', vi.fn(impl))

afterEach(() => vi.unstubAllGlobals())

describe('chatStream', () => {
  const sse = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

  it('passes on draft tokens and resolves with the final answer, however the bytes are split', async () => {
    const body = sse('token', { text: 'Mars ' }) + sse('token', { text: 'matters [1]' }) + sse('final', { response: 'Mars matters [1].', sources: [{}] })
    const pieces = [body.slice(0, 7), body.slice(7, 30), body.slice(30, 61), body.slice(61)]
    mockFetch(async () => streamed(pieces))
    const tokens = []
    const final = await api.chatStream({ query: 'Why Mars?' }, t => tokens.push(t))
    expect(tokens).toEqual(['Mars ', 'matters [1]'])
    expect(final.response).toBe('Mars matters [1].')
    const [url, init] = fetch.mock.calls[0]
    expect(url).toMatch(/\/chat\/stream$/)
    expect(JSON.parse(init.body)).toEqual({ query: 'Why Mars?' })
  })

  it('turns an error event into an ApiError with its status', async () => {
    mockFetch(async () => streamed([sse('error', { detail: 'Too many requests', status: 429 })]))
    await expect(api.chatStream({ query: 'x' })).rejects.toMatchObject({ message: 'Too many requests', status: 429 })
  })

  it('fails clearly when the stream ends without an answer', async () => {
    mockFetch(async () => streamed([sse('token', { text: 'half' })]))
    await expect(api.chatStream({ query: 'x' })).rejects.toThrow('ended early')
  })
})

describe('errors', () => {
  it('joins validation messages', async () => {
    mockFetch(async () => json({ detail: [{ msg: 'query too long' }, { msg: 'unknown mode' }] }, 422))
    await expect(api.chat({ query: 'x' })).rejects.toMatchObject({ message: 'query too long; unknown mode', status: 422 })
  })

  it('asks for the access code when the server wants it', async () => {
    const heard = vi.fn()
    window.addEventListener(LOGIN_EVENT, heard)
    mockFetch(async () => json({ detail: 'Access code required', login: true }, 401))
    await expect(api.personas()).rejects.toBeInstanceOf(ApiError)
    expect(heard).toHaveBeenCalledOnce()
    window.removeEventListener(LOGIN_EVENT, heard)
  })

  it('says the server is offline when it can\'t be reached or answers with a proxy page', async () => {
    mockFetch(async () => { throw new TypeError('Failed to fetch') })
    await expect(api.health()).rejects.toMatchObject({ message: OFFLINE_MSG, offline: true })
    mockFetch(async () => new Response('<html>Bad gateway</html>', { status: 502 }))
    await expect(api.health()).rejects.toMatchObject({ offline: true, status: 502 })
  })
})

describe('requests', () => {
  it('escapes ids and sends the right method', async () => {
    mockFetch(async () => json({ questions_deleted: 0, feedback_deleted: 0 }))
    await api.deleteHistory('elon_musk')
    await api.deleteHistory()
    await api.persona('../../etc')
    const calls = fetch.mock.calls.map(([url, init]) => [url.replace(/^.*?(\/(history|personas))/, '$1'), init.method])
    expect(calls).toEqual([['/history?persona=elon_musk', 'DELETE'], ['/history', 'DELETE'], ['/personas/..%2F..%2Fetc', 'GET']])
  })
})
