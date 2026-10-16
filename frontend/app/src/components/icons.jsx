// The few glyphs the chrome needs. Inline rather than a dependency: five icons
// do not earn a package, and these inherit colour and size from their text.

const stroke = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
}

export function ChevronDown({ className = 'size-4' }) {
  return (
    <svg {...stroke} className={className}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}

export function Bars({ className = 'size-5' }) {
  return (
    <svg {...stroke} className={className}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  )
}

export function Cross({ className = 'size-5' }) {
  return (
    <svg {...stroke} className={className}>
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  )
}

export function Eye({ className = 'size-4.5' }) {
  return (
    <svg {...stroke} className={className}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

export function EyeOff({ className = 'size-4.5' }) {
  return (
    <svg {...stroke} className={className}>
      <path d="M10.6 6.7A8.9 8.9 0 0 1 12 6.5c6 0 9.5 6.5 9.5 6.5a16.6 16.6 0 0 1-3.2 3.9M6.3 8.1A16.4 16.4 0 0 0 2.5 13S6 19.5 12 19.5a9.3 9.3 0 0 0 3.7-.76" />
      <path d="M9.9 10.9a3 3 0 0 0 4.2 4.2M3 3l18 18" />
    </svg>
  )
}

/**
 * The clinic mark. A cross on the brand colour, used in the header and on the
 * sign-in screen so the two read as the same product.
 */
export function Mark({ className = 'size-9 rounded-xl' }) {
  return (
    <span
      className={`inline-grid shrink-0 place-items-center bg-brand-600 text-white ${className}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" fill="currentColor" className="size-[55%]">
        <path d="M10 3h4v7h7v4h-7v7h-4v-7H3v-4h7z" />
      </svg>
    </span>
  )
}
