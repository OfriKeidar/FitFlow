interface Props {
  label: string
  eaten: number
  target: number
  color: string
  unit?: string
}

/** One macro's progress: "Protein 121 / 176 g" with a bar that turns red when over target. */
export function MacroBar({ label, eaten, target, color, unit = "גר'" }: Props) {
  const percent = target > 0 ? Math.min(100, (eaten / target) * 100) : 0
  const over = eaten > target * 1.05 // small tolerance: 101% isn't "over"
  return (
    <div>
      <div className="row" style={{ fontSize: 13 }}>
        <span>{label}</span>
        <span className="muted">
          {Math.round(eaten)} / {Math.round(target)} {unit}
        </span>
      </div>
      <div className={`bar ${over ? 'over' : ''}`}>
        <i style={{ width: `${percent}%`, background: color }} />
      </div>
    </div>
  )
}
