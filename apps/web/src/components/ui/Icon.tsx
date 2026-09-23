/** A hand-picked handful of 24px stroke icons — a full icon package would cost more than the app. */
const PATHS = {
  home: 'M3 10.5 12 3l9 7.5M5.5 9.5V21h13V9.5',
  users: 'M16 20v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20M9.5 10.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7M21 20v-1.5a4 4 0 0 0-3-3.87M16 3.6a4 4 0 0 1 0 7.75',
  money: 'M12 2v20M17 6.5c0-1.9-2.2-3-5-3s-5 1-5 3 2 2.8 5 3.3 5 1.4 5 3.4-2.2 3.3-5 3.3-5-1.2-5-3.2',
  list: 'M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01',
  play: 'M6 4.5v15l13-7.5z',
  chart: 'M4 20V10M10 20V4M16 20v-6M22 20H2',
  user: 'M20 21v-2a5 5 0 0 0-5-5H9a5 5 0 0 0-5 5v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
  spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z',
  dumbbell: 'M6.5 6.5v11M3.5 9v6M17.5 6.5v11M20.5 9v6M6.5 12h11',
  check: 'M4 12.5l5 5 11-11',
  chevron: 'M9 5l7 7-7 7',
  calendar: 'M4 6.5A1.5 1.5 0 0 1 5.5 5h13A1.5 1.5 0 0 1 20 6.5V19H4zM4 10h16M8.5 3v4M15.5 3v4',
  camera: 'M3 8.5A1.5 1.5 0 0 1 4.5 7h2.2l1.1-2h8.4l1.1 2h2.2A1.5 1.5 0 0 1 21 8.5v9A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5zM12 16a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7',
  chat: 'M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5.1A8 8 0 1 1 21 12',
  lock: 'M7 10.5V7.8a5 5 0 0 1 10 0v2.7M5.5 10.5h13V20h-13zM12 14v2.5',
  whatsapp: 'M3 21l1.65-4.5A8 8 0 1 1 7.5 19.4zM8.5 9.5c0 3.5 3 6.5 6.5 6.5.6 0 1.2-.6 1.2-1.2l-1.7-.9-1 1c-1.3-.6-2.3-1.6-2.9-2.9l1-1-.9-1.7c-.6 0-1.2.6-1.2 1.2',
  bolt: 'M13 2 4 14h6l-1 8 9-12h-6z',
  add: 'M12 5v14M5 12h14',
  close: 'M6 6l12 12M18 6L6 18',
  help: 'M12 2a10 10 0 1 0 0.01 0ZM9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
