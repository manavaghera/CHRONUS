import { download } from '../api'
import { plain } from './AnswerText'

// Draws an answer as a 1200×630 card (their words, who said them, the
// source) and downloads it as a PNG. Everything happens in the browser.
function wrap(ctx, text, width) {
  const words = text.split(/\s+/)
  const lines = []
  let line = ''
  for (const w of words) {
    const next = line ? `${line} ${w}` : w
    if (ctx.measureText(next).width > width && line) { lines.push(line); line = w } else line = next
  }
  if (line) lines.push(line)
  return lines
}

export async function downloadQuoteCard({ text, name, source, dark }) {
  await document.fonts?.ready
  const W = 1200, H = 630, pad = 84
  const c = document.createElement('canvas')
  c.width = W; c.height = H
  const ctx = c.getContext('2d')
  const bg = dark ? '#0A0B0D' : '#F3F3F0', ink = dark ? '#ECECE8' : '#0F1012', mute = dark ? '#8B8E96' : '#62666E', acc = dark ? '#FF6436' : '#CF3D10'
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H)
  // faint voice lines
  ctx.strokeStyle = ink; ctx.globalAlpha = 0.06
  for (let i = 0; i < 14; i++) {
    ctx.beginPath()
    for (let x = 0; x <= W; x += 10) { const y = 40 + i * 42 + Math.sin(x / 90 + i) * 8; x ? ctx.lineTo(x, y) : ctx.moveTo(x, y) }
    ctx.stroke()
  }
  ctx.globalAlpha = 1
  ctx.fillStyle = acc; ctx.fillRect(pad, pad, 56, 3)
  let quote = plain(text).replace(/\s+/g, ' ').trim()
  if (quote.length > 300) quote = `${quote.slice(0, 297).replace(/\s+\S*$/, '')}…`
  let size = 56, lines
  do {
    ctx.font = `italic ${size}px "Instrument Serif", Georgia, serif`
    lines = wrap(ctx, `“${quote.replace(/^[“"]|[”"]$/g, '')}”`, W - pad * 2)
    size -= 4
  } while (lines.length * size * 1.25 > H - 280 && size > 28)
  ctx.fillStyle = ink
  const lh = (size + 4) * 1.22
  lines.forEach((l, i) => ctx.fillText(l, pad, pad + 70 + i * lh))
  ctx.font = '600 26px Geist, system-ui, sans-serif'
  ctx.fillText(name, pad, H - pad - 34)
  ctx.font = '400 18px "Geist Mono", ui-monospace, monospace'
  ctx.fillStyle = mute
  ctx.fillText((source || 'From their own words').toUpperCase().slice(0, 70), pad, H - pad)
  ctx.textAlign = 'right'
  ctx.fillStyle = ink
  ctx.font = '600 20px Geist, system-ui, sans-serif'
  ctx.fillText('C H R O N U S', W - pad, H - pad)
  const blob = await new Promise(r => c.toBlob(r, 'image/png'))
  if (blob) download(blob, `chronus-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-quote.png`)
}
