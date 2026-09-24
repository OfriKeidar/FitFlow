// A small set of outline icons (24x24, stroke-based), drawn inline so we need no icon library.

const PATHS = {
  home: 'M5 12H3l9-9 9 9h-2M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7M9 21v-6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v6',
  chat: 'M3 20l1.3-3.9A9 8 0 1 1 7.7 19L3 20',
  kitchen: 'M19 3v12h-5c-.02-3.68.3-7.72 5-12M19 15v6h-1v-3M8 4v17M5 4v3a3 3 0 1 0 6 0V4',
  barbell: 'M2 12h1M6 8H4a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2M6 7v10a1 1 0 0 0 1 1h1a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1M9 12h6M15 7v10a1 1 0 0 0 1 1h1a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-1a1 1 0 0 0-1 1M18 8h2a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2M22 12h-1',
  chart: 'M4 19h16M4 15l4-6 4 2 4-5 4 4',
  trash: 'M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3',
  send: 'M10 14L21 3M21 3l-6.5 18a.55.55 0 0 1-1 0L10 14l-7-3.5a.55.55 0 0 1 0-1L21 3',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  bulb: 'M3 12h1m8-9v1m8 8h1M5.6 5.6l.7.7m12.1-.7l-.7.7M9 16a5 5 0 1 1 6 0a3.5 3.5 0 0 0-1 3a2 2 0 0 1-4 0a3.5 3.5 0 0 0-1-3M9.7 17h4.6',
  check: 'M5 12l5 5L20 7',
  x: 'M18 6L6 18M6 6l12 12',
  sparkles: 'M16 18a2 2 0 0 1 2 2a2 2 0 0 1 2-2a2 2 0 0 1-2-2a2 2 0 0 1-2 2m0-12a2 2 0 0 1 2 2a2 2 0 0 1 2-2a2 2 0 0 1-2-2a2 2 0 0 1-2 2M9 18a6 6 0 0 1 6-6a6 6 0 0 1-6-6a6 6 0 0 1-6 6a6 6 0 0 1 6 6',
  scale: 'M7 20h10M6 6l6-1l6 1M12 3v17M9 12L6 6l-3 6a3 3 0 0 0 6 0M21 12l-3-6l-3 6a3 3 0 0 0 6 0',
  flame: 'M12 12c2-2.96 0-7-1-8c0 3.04-1.77 4.74-3 6c-1.22 1.27-2 3.27-2 5a6 6 0 1 0 12 0c0-1.5-1.06-3.86-2-5c-1.79 3-2.8 3-4 2',
  run: 'M13 4a1 1 0 1 0 2 0a1 1 0 1 0-2 0M4 17l5 1l.75-1.5M15 21v-4l-4-3l1-6M7 12V9l5-1l3 3l3 1',
  ball: 'M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 7l4.76 3.45l-1.76 5.55h-6l-1.76-5.55zM12 7V3m4.76 7.45l3.9-1.9M15 16l2.5 3.5M9 16l-2.5 3.5M7.24 10.45L3.34 8.55',
  trendDown: 'M3 7l6 6l4-4l8 8M21 10v7h-7',
  trendUp: 'M3 17l6-6l4 4l8-8M14 7h7v7',
  arrows: 'M21 17H3M6 10L3 7l3-3M3 7h18M18 20l3-3l-3-3',
  equal: 'M5 10h14M5 14h14',
  logout: 'M14 8V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2M9 12h12l-3-3m0 6l3-3',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
