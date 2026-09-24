import type { ReactNode } from 'react'

interface Props {
  value: number
  max: number
  size: number
  stroke: number
  color: string
  children?: ReactNode // shown in the middle of the ring
  label?: string       // accessible description
}

/**
 * A circular progress ring. It fills clockwise as value approaches max, and turns red past max.
 * How it works: a circle's outline is drawn as a dash; strokeDashoffset hides the unfilled part.
 */
export function Ring({ value, max, size, stroke, color, children, label }: Props) {
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const fraction = max > 0 ? Math.min(1, value / max) : 0
  const over = value > max * 1.05

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }} role="img" aria-label={label}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} strokeLinecap="round"
          stroke={over ? 'var(--danger)' : color}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - fraction)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 0.9s ease-out' }}
        />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center' }}>
        {children}
      </div>
    </div>
  )
}
