// The FitFlow logo: a ring (like the daily calorie ring) around a dumbbell.
// When `animated`, the ring fills and the dumbbell is "lifted" - used as the loading indicator.

interface Props {
  size?: number
  animated?: boolean
}

export function Logo({ size = 40, animated = false }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 90 90" role="img" aria-label="FitFlow">
      <circle cx="45" cy="45" r="36" fill="none" stroke="var(--surface-2)" strokeWidth="7" />
      <circle
        cx="45" cy="45" r="36" fill="none" stroke="var(--accent)" strokeWidth="7" strokeLinecap="round"
        transform="rotate(-90 45 45)"
        strokeDasharray="226"
        style={animated ? { animation: 'ring-fill 2.2s ease-in-out infinite' } : undefined}
      />
      <g fill="var(--accent)" style={animated ? { animation: 'lift 1.1s ease-in-out infinite' } : undefined}>
        <rect x="26" y="36" width="6" height="18" rx="2" />
        <rect x="58" y="36" width="6" height="18" rx="2" />
        <rect x="21" y="40" width="4" height="10" rx="1.5" />
        <rect x="65" y="40" width="4" height="10" rx="1.5" />
        <rect x="32" y="43" width="26" height="4" rx="2" />
      </g>
    </svg>
  )
}

/** Full-screen loading state: the animated logo with a short message. */
export function Loader({ message }: { message?: string }) {
  return (
    <div style={{ minHeight: '60dvh', display: 'grid', placeItems: 'center' }}>
      <div className="stack fade-in" style={{ alignItems: 'center' }}>
        <Logo size={96} animated />
        <h1>FitFlow</h1>
        {message && <p className="muted">{message}</p>}
      </div>
    </div>
  )
}
