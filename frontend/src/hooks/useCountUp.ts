import { useEffect, useRef, useState } from 'react'

const reduceMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/**
 * Animate a number from its previous value to `target` (e.g. 0 -> 1787 on first load).
 * Small touch, but it makes the dashboard feel alive. Users who prefer reduced motion get the
 * final number right away.
 */
export function useCountUp(target: number, durationMs = 700): number {
  const [value, setValue] = useState(0)
  const from = useRef(0)

  useEffect(() => {
    if (reduceMotion) return
    const start = performance.now()
    const startValue = from.current
    let frame = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3) // ease-out: fast start, gentle stop
      setValue(startValue + (target - startValue) * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
      else from.current = target
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs])

  return reduceMotion ? target : value
}
