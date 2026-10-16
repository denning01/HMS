/**
 * Mother and child, for the sign-in panel.
 *
 * Drawn rather than photographed so it scales to any panel, needs nothing from
 * the network, and takes its colour from whatever it is laid over. It is three
 * layers — her, the child, her arms — each cut out of the one behind it, which
 * is what keeps the two figures reading apart at low opacity instead of merging
 * into one shape.
 */
export function MotherAndChild({ className }) {
  return (
    <svg
      viewBox="0 0 340 420"
      className={className}
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <circle id="mc-child" cx="178" cy="276" r="32" />
        <path id="mc-back" fill="none" d="M118 132 C 62 164, 36 252, 80 318 C 120 376, 220 382, 258 318" />
        <path id="mc-arms" fill="none" d="M112 286 C 150 336, 214 332, 240 282" />

        {/* The gaps. Each shape is drawn fattened in black, so whatever it is
            masking loses a sliver around it and an edge appears. */}
        <g id="mc-gap-child">
          <use href="#mc-child" fill="#000" stroke="#000" strokeWidth="9" />
        </g>
        <g id="mc-gap-arms">
          <use href="#mc-arms" stroke="#000" strokeWidth="34" strokeLinecap="round" />
        </g>

        <mask id="mc-mother">
          <rect width="340" height="420" fill="#fff" />
          <use href="#mc-gap-child" />
          <use href="#mc-gap-arms" />
        </mask>
        <mask id="mc-childCut">
          <rect width="340" height="420" fill="#fff" />
          <use href="#mc-gap-arms" />
        </mask>

        {/* The panel crops the foot of the drawing. Rather than let it end on a
            straight edge, the last stretch dissolves into the background. */}
        <linearGradient id="mc-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0.8" stopColor="#fff" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <mask id="mc-foot">
          <rect width="340" height="420" fill="url(#mc-fade)" />
        </mask>
      </defs>

      <g mask="url(#mc-foot)">
      {/* her: head and back, one tone so the join does not seam */}
      <g mask="url(#mc-mother)" opacity="0.2">
        <circle cx="124" cy="88" r="45" fill="currentColor" />
        <use href="#mc-back" stroke="currentColor" strokeWidth="43" strokeLinecap="round" />
      </g>

      {/* the child, held */}
      <g mask="url(#mc-childCut)">
        <use href="#mc-child" fill="currentColor" opacity="0.42" />
      </g>

      {/* her arms, closing round */}
      <use href="#mc-arms" stroke="currentColor" strokeWidth="27" strokeLinecap="round" opacity="0.3" />
      </g>
    </svg>
  )
}
