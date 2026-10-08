// Answer text with clickable [n] citation markers. Rendered as React text
// nodes (never innerHTML): answers quote real documents.
export default function AnswerText({ text, sources = [], onCite }) {
  const parts = text.split(/(\[\d{1,2}\])/g)
  return parts.map((part, i) => {
    const m = /^\[(\d{1,2})\]$/.exec(part)
    const source = m && sources[Number(m[1]) - 1]
    if (!source) return part
    return (
      <button key={i} className="cite" onClick={() => onCite?.(Number(m[1]) - 1)}
        title={`Source ${m[1]}: ${source.citation || source.source_file}`} aria-label={`Source ${m[1]}`}>
        {m[1]}
      </button>
    )
  })
}

// Text without the markers (reading aloud, copying)
export const plain = (text) => text.replace(/\s*\[\d{1,2}\]/g, '')
