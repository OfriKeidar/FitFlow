import { useCallback, useEffect, useState } from 'react'
import { errorMessage } from '../api/client'

/**
 * Load data from the API when a component mounts.
 *
 *   const { data, error, loading, reload } = useApi(api.today)
 *
 * `reload()` fetches again (e.g. after the user logs something).
 * The previous data stays on screen while reloading, so the page doesn't flicker.
 */
export function useApi<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(
    async (isStale: () => boolean = () => false) => {
      try {
        const result = await fetcher()
        if (isStale()) return
        setData(result)
        setError(null)
      } catch (e) {
        if (!isStale()) setError(errorMessage(e))
      } finally {
        if (!isStale()) setLoading(false)
      }
    },
    [fetcher],
  )

  // Initial load. If the component unmounts before the response arrives, ignore the response
  // (otherwise we'd update a page the user already left).
  useEffect(() => {
    let stale = false
    // False positive: load() only calls setState after awaiting the request, never synchronously.
    // oxlint-disable-next-line react/set-state-in-effect
    load(() => stale)
    return () => {
      stale = true
    }
  }, [load])

  const reload = useCallback(() => {
    setLoading(true)
    return load()
  }, [load])

  return { data, error, loading, reload }
}
