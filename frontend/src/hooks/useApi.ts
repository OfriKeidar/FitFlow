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

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      setData(await fetcher())
      setError(null)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [fetcher])

  useEffect(() => {
    reload()
  }, [reload])

  return { data, error, loading, reload }
}
