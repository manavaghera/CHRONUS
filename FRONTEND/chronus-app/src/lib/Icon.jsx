// Stroke icons drawn for CHRONUS (currentColor, 24px grid)
const PATHS = {
  arrow: <><path d="M5 12h14" /><path d="M13 6l6 6-6 6" /></>,
  back: <><path d="M19 12H5" /><path d="M11 6l-6 6 6 6" /></>,
  out: <><path d="M7 17L17 7" /><path d="M8 7h9v9" /></>,
  up: <><path d="M12 19V5" /><path d="M6 11l6-6 6 6" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="M20 20l-4.2-4.2" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4" /></>,
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />,
  menu: <path d="M4 9h16M4 15h16" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  lock: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></>,
  stop: <rect x="7" y="7" width="10" height="10" rx="2" />,
  play: <path d="M8 5v14l11-7z" />,
  speaker: <><path d="M4 9v6h4l5 4V5L8 9z" /><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /></>,
  upload: <><path d="M12 16V4" /><path d="M6 10l6-6 6 6" /><path d="M4 20h16" /></>,
  file: <><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5" /></>,
  trash: <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />,
  copy: <><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h8" /></>,
  shield: <><path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6l8-3z" /><path d="M9 12l2 2 4-4" /></>,
  heart: <path d="M12 21s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.6-7 10-7 10z" />,
  buoy: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><path d="M5.6 5.6l3.6 3.6M14.8 14.8l3.6 3.6M18.4 5.6l-3.6 3.6M9.2 14.8l-3.6 3.6" /></>,
  chart: <path d="M5 20V11M11 20V5M17 20v-6M3 20h18" />,
  doc: <><path d="M7 4h10v16H7z" /><path d="M10 9h4M10 13h4" /></>,
  wave: <path d="M3 12h2M7 8v8M11 5v14M15 9v6M19 7v10M21 12h0" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
  slash: <><circle cx="12" cy="12" r="9" /><path d="M5.6 18.4L18.4 5.6" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  dots: <path d="M5 12h.01M12 12h.01M19 12h.01" />,
  swap: <><path d="M9 7l-5 5 5 5" /><path d="M15 7l5 5-5 5" /></>,
  key: <><circle cx="8" cy="15" r="4" /><path d="M11 12l9-9M16 7l3 3" /></>,
  sparkle: <path d="M12 3c.8 5 3.2 7.6 8 8.5-4.8.9-7.2 3.5-8 8.5-.8-5-3.2-7.6-8-8.5 4.8-.9 7.2-3.5 8-8.5z" />,
  thumbUp: <><path d="M7 11v9H4v-9z" /><path d="M7 11l4-7a2 2 0 0 1 3 2l-1 4h5a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 16.8 20H7" /></>,
  thumbDown: <><path d="M7 13V4H4v9z" /><path d="M7 13l4 7a2 2 0 0 0 3-2l-1-4h5a2 2 0 0 0 2-2.3l-1.2-6A2 2 0 0 0 16.8 4H7" /></>,
  table: <><circle cx="12" cy="12" r="4" /><circle cx="12" cy="3.5" r="1.5" /><circle cx="12" cy="20.5" r="1.5" /><circle cx="3.5" cy="12" r="1.5" /><circle cx="20.5" cy="12" r="1.5" /></>,
  brain: <><path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V6a2 2 0 0 0-3-2z" /><path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1" /></>,
  share: <><circle cx="18" cy="5" r="2.5" /><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="19" r="2.5" /><path d="M8.2 10.8l7.6-4.4M8.2 13.2l7.6 4.4" /></>,
  download: <><path d="M12 4v12" /><path d="M6 10l6 6 6-6" /><path d="M4 20h16" /></>,
  keyboard: <><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10" /></>,
  logo: <><circle cx="12" cy="12" r="9.25" /><path className="acc" d="M12 12V5.2" /><path d="M12 12l4.2 2.6" /></>,
}

export default function Icon({ name, size = 18, className = '', label }) {
  return (
    <svg className={`ic ${className}`.trim()} viewBox="0 0 24 24" width={size} height={size}
      aria-hidden={label ? undefined : 'true'} aria-label={label} role={label ? 'img' : undefined}>
      {PATHS[name]}
    </svg>
  )
}
