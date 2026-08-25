const CLAVE_TEMA = "archivum_tema"; // "light" | "dark" — ausente = sigue al sistema
const CLAVE_ACENTO = "archivum_color_acento";
export const ACENTO_POR_DEFECTO = "#c05a3f";

function mezclar(hex, hacia, porcentaje) {
  const num = parseInt(hex.replace("#", ""), 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  const canal = (c) => Math.round(c + (hacia - c) * porcentaje);
  return `#${[canal(r), canal(g), canal(b)].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

export function cargarTema() {
  const guardado = localStorage.getItem(CLAVE_TEMA);
  if (guardado) document.documentElement.setAttribute("data-theme", guardado);
}

export function aplicarTema(valor) {
  document.documentElement.setAttribute("data-theme", valor);
  localStorage.setItem(CLAVE_TEMA, valor);
  const acentoGuardado = localStorage.getItem(CLAVE_ACENTO);
  if (acentoGuardado) aplicarColorAcento(acentoGuardado);
}

export function obtenerTema() {
  return (
    localStorage.getItem(CLAVE_TEMA) ||
    (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light")
  );
}

export function cargarColorAcento() {
  const guardado = localStorage.getItem(CLAVE_ACENTO);
  if (guardado) aplicarColorAcento(guardado);
}

export function aplicarColorAcento(hex) {
  const oscuro = obtenerTema() === "dark";
  document.documentElement.style.setProperty("--color-accent", hex);
  document.documentElement.style.setProperty(
    "--color-accent-soft",
    oscuro ? mezclar(hex, 0, 0.72) : mezclar(hex, 255, 0.82)
  );
  localStorage.setItem(CLAVE_ACENTO, hex);
}

export function obtenerColorAcento() {
  return localStorage.getItem(CLAVE_ACENTO) || ACENTO_POR_DEFECTO;
}
