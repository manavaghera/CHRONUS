// Illustrated emblems for the models: drawn SVG, so they always load and
// never use anyone's photo or likeness. Custom models get a monogram.

const S = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }

const DRAWINGS = {
  // Rocket
  elon_musk: (
    <g {...S}>
      <path d="M24 6c6 5 8 12 7 21l-3 5h-8l-3-5c-1-9 1-16 7-21z" />
      <circle cx="24" cy="18" r="3" />
      <path d="M17 27l-5 5 1 5 5-3M31 27l5 5-1 5-5-3" />
      <path d="M21 36c0 3 1 5 3 7 2-2 3-4 3-7" opacity=".6" />
    </g>
  ),
  // Curved space-time and an orbit
  albert_einstein: (
    <g {...S}>
      <path d="M6 30c6-2 12-8 18-8s12 6 18 8" opacity=".55" />
      <path d="M6 36c6-1.5 12-6 18-6s12 4.5 18 6" opacity=".35" />
      <circle cx="24" cy="17" r="5" />
      <ellipse cx="24" cy="17" rx="13" ry="5" transform="rotate(-18 24 17)" />
      <circle cx="35" cy="12" r="1.6" fill="currentColor" stroke="none" />
    </g>
  ),
  // Tesla coil with arcs
  nikola_tesla: (
    <g {...S}>
      <ellipse cx="24" cy="12" rx="8" ry="3.5" />
      <path d="M21 15.5v18M27 15.5v18M21 19h6M21 23h6M21 27h6M21 31h6" />
      <path d="M16 42h16M19 33.5h10l3 8.5H16z" />
      <path d="M32 10l4-3-2 5 5-2M16 10l-4-3 2 5-5-2" opacity=".7" />
    </g>
  ),
  // Flask with glowing radium
  marie_curie: (
    <g {...S}>
      <path d="M19 6h10M21 6v11L11 37a3 3 0 0 0 2.7 4.3h20.6A3 3 0 0 0 37 37L27 17V6" />
      <path d="M15 30h18" opacity=".55" />
      <circle cx="21" cy="35" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="27" cy="33" r="1.8" fill="currentColor" stroke="none" />
      <circle cx="24" cy="38" r="1" fill="currentColor" stroke="none" />
    </g>
  ),
  // Charkha (spinning wheel)
  mahatma_gandhi: (
    <g {...S}>
      <circle cx="20" cy="22" r="11" />
      <circle cx="20" cy="22" r="2" />
      <path d="M20 11v22M9 22h22M12.2 14.2l15.6 15.6M27.8 14.2L12.2 29.8" opacity=".6" />
      <path d="M8 40h32M20 33v7M34 30v10M31 30h6" />
      <path d="M20 11c6 1 11 6 14 19" opacity=".5" />
    </g>
  ),
  // Stovepipe hat
  abraham_lincoln: (
    <g {...S}>
      <path d="M15 34V10c0-1.5 1-2.5 2.5-2.5h13c1.5 0 2.5 1 2.5 2.5v24" />
      <path d="M8 35c3 3 29 3 32 0" />
      <path d="M15 28h18" strokeWidth="4" opacity=".55" />
    </g>
  ),
  // Laurel wreath
  marcus_aurelius: (
    <g {...S}>
      <path d="M14 38C7 32 6 20 12 12M34 38c7-6 8-18 2-26" />
      <path d="M12 16c-3 0-5-2-5-4 3 0 5 2 5 4zM10 23c-3 1-5 0-6-2 3-1 5 0 6 2zM11 30c-2 2-5 2-6 1 2-2 4-2 6-1zM14 35c-1 2-4 3-5 3 1-2 3-3 5-3z" />
      <path d="M36 16c3 0 5-2 5-4-3 0-5 2-5 4zM38 23c3 1 5 0 6-2-3-1-5 0-6 2zM37 30c2 2 5 2 6 1-2-2-4-2-6-1zM34 35c1 2 4 3 5 3-1-2-3-3-5-3z" />
      <path d="M20 41l4-3 4 3" />
    </g>
  ),
  // Quill
  william_shakespeare: (
    <g {...S}>
      <path d="M38 7C25 9 15 19 12 36l3-1c3-10 9-17 17-21-6 6-10 12-12 19 9-3 15-12 18-26z" />
      <path d="M12 36l-3 6" />
      <path d="M8 42h14" opacity=".55" />
    </g>
  ),
}

export function hasEmblem(id) {
  return id in DRAWINGS
}

export function Emblem({ id, name = '' }) {
  if (DRAWINGS[id]) {
    return <svg viewBox="0 0 48 48" width="100%" height="100%" aria-hidden="true">{DRAWINGS[id]}</svg>
  }
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('') || '?'
  return (
    <svg viewBox="0 0 48 48" width="100%" height="100%" aria-hidden="true">
      <circle cx="24" cy="24" r="17" fill="none" stroke="currentColor" strokeWidth="1.5" opacity=".45" />
      <text x="24" y="29.5" textAnchor="middle" fontSize="15" fontWeight="600" fill="currentColor" fontFamily="Onest, sans-serif">{initials}</text>
    </svg>
  )
}
