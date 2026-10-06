import { describe, expect, it } from 'vitest'
import { encodeWav, wavSeconds } from './audio'

const text = (view, offset, n) => String.fromCharCode(...Array.from({ length: n }, (_, i) => view.getUint8(offset + i)))

describe('encodeWav', () => {
  it('writes a mono 16-bit PCM WAV the server accepts', () => {
    const view = new DataView(encodeWav(new Float32Array([0, 0.5, -0.5, 2, -2]), 24000))
    expect(text(view, 0, 4)).toBe('RIFF')
    expect(text(view, 8, 4)).toBe('WAVE')
    expect(view.getUint16(20, true)).toBe(1)  // PCM
    expect(view.getUint16(22, true)).toBe(1)  // mono
    expect(view.getUint32(24, true)).toBe(24000)
    expect(view.getUint16(34, true)).toBe(16)
    expect(view.getUint32(40, true)).toBe(10)  // 5 samples x 2 bytes
    expect(view.byteLength).toBe(54)
    // out-of-range samples are clipped, not wrapped
    expect(view.getInt16(50, true)).toBe(32767)
    expect(view.getInt16(52, true)).toBe(-32768)
  })

  it('knows how long its own recordings are', () => {
    expect(wavSeconds(new Blob([new Uint8Array(44 + 48000)]))).toBe(1)
    expect(wavSeconds(new Blob([]))).toBe(0)
  })
})
