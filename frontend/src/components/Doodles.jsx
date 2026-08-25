// Adornitos sueltos (hoja, florecita, ramita) para darle un toque hecho a
// mano a un par de tarjetas clave — decoración, no información, por eso
// aria-hidden y sin interacción. Trazo simple a propósito, para que lean
// como un garabato y no como un ícono de sistema.

function Doodle({ className, style, children, viewBox = "0 0 44 44" }) {
  return (
    <svg
      className={`arv-doodle ${className ?? ""}`}
      style={style}
      viewBox={viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function DoodleHoja({ className, style }) {
  return (
    <Doodle className={className} style={style}>
      <path d="M22 38C22 38 9 31 10 18C11 8 20 5 22 5C24 5 33 8 34 18C35 31 22 38 22 38Z" />
      <path d="M22 7V33" />
      <path d="M22 15C22 15 16 17 14 21" />
      <path d="M22 22C22 22 28 24 30 28" />
    </Doodle>
  );
}

export function DoodleFlor({ className, style }) {
  return (
    <Doodle className={className} style={style}>
      <g>
        <ellipse cx="22" cy="12" rx="5" ry="7" />
        <ellipse cx="22" cy="12" rx="5" ry="7" transform="rotate(72 22 22)" />
        <ellipse cx="22" cy="12" rx="5" ry="7" transform="rotate(144 22 22)" />
        <ellipse cx="22" cy="12" rx="5" ry="7" transform="rotate(216 22 22)" />
        <ellipse cx="22" cy="12" rx="5" ry="7" transform="rotate(288 22 22)" />
      </g>
      <circle cx="22" cy="22" r="2.6" fill="currentColor" stroke="none" />
    </Doodle>
  );
}

export function DoodleRamita({ className, style }) {
  return (
    <Doodle className={className} style={style}>
      <path d="M5 40C12 29 9 16 22 5" />
      <path d="M11 27C15 24 19 25 21 29" />
      <path d="M16 14C20 12 23 14 23 18" />
    </Doodle>
  );
}
