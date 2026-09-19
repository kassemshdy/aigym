import { useEffect, useState } from 'react'
import { API_URL, fetchMedia, type AuthAs } from './client'

/**
 * Turns an opaque photo_key into a displayable <img src>. Mock mode's key
 * IS already a data URL (mockAdapter's progress-photo/food-entry
 * convention, since there's no real object store to round-trip through)
 * — real API mode fetches the blob through the authenticated
 * GET /media/{key} route and hands back a revocable object URL. The
 * fetch is the only case that needs effect state; a data URL or missing
 * key is returned straight from render, no effect involved.
 */
export function useMediaUrl(key: string | null, authAs: AuthAs): string | null {
  const passthrough = !key || !API_URL || key.startsWith('data:')
  const [fetchedUrl, setFetchedUrl] = useState<string | null>(null)

  useEffect(() => {
    if (passthrough || !key) return

    let cancelled = false
    let objectUrl: string | null = null
    void fetchMedia(key, authAs)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setFetchedUrl(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setFetchedUrl(null)
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [passthrough, key, authAs])

  if (!key) return null
  return passthrough ? key : fetchedUrl
}
