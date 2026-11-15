import type { ReactNode } from 'react'

// Small line icons (24 grid, rounded 1.8 stroke, currentColor). Decorative: always paired with a text label.
const PATHS = {
  order: <><path d="M5 9.5h14l-1.2 8.6a2 2 0 0 1-2 1.7H8.2a2 2 0 0 1-2-1.7L5 9.5Z" /><path d="m9 9.5 3-5 3 5" /></>,
  history: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  kitchen: <><path d="M7 14.5a4 4 0 1 1 1.6-7.7 4 4 0 0 1 6.8 0A4 4 0 1 1 17 14.5V19a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1v-4.5Z" /><path d="M7 16.5h10" /></>,
  rules: <><path d="m12 3.5 7 2.5v5.5c0 4.2-2.9 7.4-7 9-4.1-1.6-7-4.8-7-9V6l7-2.5Z" /><path d="m9 12 2.2 2.2L15.5 10" /></>,
  valio: <><path d="M5 20V6.5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1V20" /><path d="M14 10h4a1 1 0 0 1 1 1v9M3.5 20h17M8 9h3M8 12.5h3M8 16h3" /></>,
  globe: <><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.6 2.6 2.6 14.4 0 17M12 3.5c-2.6 2.6-2.6 14.4 0 17" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" /></>,
  key: <><circle cx="8" cy="15.5" r="3.5" /><path d="M10.6 12.9 19 4.5M15.5 8l2.5 2.5M13 10.5l2 2" /></>,
  sparkle: <><path d="m11 4 1.7 4.6L17.5 10l-4.8 1.4L11 16l-1.7-4.6L4.5 10l4.8-1.4L11 4Z" /><path d="m18 15 .8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2Z" /></>,
  bulb: <><path d="M12 3.5a6 6 0 0 0-3.6 10.8c.6.5.9 1.1.9 1.8v.9h5.4v-.9c0-.7.3-1.3.9-1.8A6 6 0 0 0 12 3.5Z" /><path d="M10 20.5h4" /></>,
  chart: <path d="M4.5 19.5h15M7.5 16v-4M12 16V7.5M16.5 16v-6" />,
  pencil: <><path d="m4.5 19.5 1-4L16 5a1.8 1.8 0 0 1 2.5 0l.5.5a1.8 1.8 0 0 1 0 2.5L8.5 18.5l-4 1Z" /><path d="m14 7 3 3" /></>,
  calendar: <><rect x="4" y="5.5" width="16" height="14" rx="2" /><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" /></>,
  chevron: <path d="m9 6 6 6-6 6" />,
} satisfies Record<string, ReactNode>

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg className="ico" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  )
}
