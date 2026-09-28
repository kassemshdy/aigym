/**
 * YouTube links as coaches actually paste them, and how each kind plays.
 *
 * A Short is stored as provider `youtube_short` rather than a new column:
 * the id is the same kind of id and plays through the same embed URL. The
 * provider only decides the shape — Shorts are filmed vertically, and in a
 * 16:9 box they play as a thin strip between two black bars.
 */

export const YOUTUBE = 'youtube'
export const YOUTUBE_SHORT = 'youtube_short'

export interface YoutubeLink {
  id: string
  short: boolean
}

/** A watch, share, embed or Shorts link, or a bare 11-character id. Null for
 * anything else, so a mistyped link is caught on the form rather than saved
 * as a video that never plays (decision 28: no live oEmbed check). */
export function parseYoutube(input: string): YoutubeLink | null {
  const trimmed = input.trim()
  const short = trimmed.match(/shorts\/([\w-]{11})/)
  if (short) return { id: short[1], short: true }
  const long = trimmed.match(/(?:v=|youtu\.be\/|embed\/|live\/)([\w-]{11})/)
  if (long) return { id: long[1], short: false }
  return /^[\w-]{11}$/.test(trimmed) ? { id: trimmed, short: false } : null
}

export const isShort = (v: { provider: string }) => v.provider === YOUTUBE_SHORT

export const isYoutube = (v: { provider: string }) =>
  v.provider === YOUTUBE || v.provider === YOUTUBE_SHORT

/** hqdefault is 4:3 with the vertical frame in the middle, so cropping it to
 * 9:16 with object-cover shows a Short's actual picture. */
export const youtubeThumb = (v: { provider: string; external_id: string }) =>
  isYoutube(v)
    ? `https://img.youtube.com/vi/${v.external_id}/${isShort(v) ? 'hqdefault' : 'mqdefault'}.jpg`
    : ''
