import { getToken, clearToken } from "./auth";

// Vacío = mismo origen desde el que se sirvió la página. Funciona tanto en
// localhost:8000 como en la URL de Tailscale, porque FastAPI sirve la API y
// el frontend juntos (ver app/main.py). En dev con `npm run dev` (puerto
// 5173, distinto origen que la API) se pisa con VITE_API_URL en
// frontend/.env.development.
const BASE_URL = import.meta.env.VITE_API_URL || "";
// Todo bajo /api (ver app/main.py): así /fics/14 nunca es ambiguo entre "la
// pantalla del fic" (React Router) y "el JSON del fic" (backend).
const API_BASE = `${BASE_URL}/api`;

async function request(path, options = {}) {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Archivum-Token": token } : {}),
    },
    ...options,
  });
  if (response.status === 401) {
    // Token inválido/vencido: lo tiramos así AuthGate vuelve a pedirlo.
    clearToken();
    window.location.reload();
    throw new Error("401: No autorizado");
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // sin body legible, nos quedamos con statusText
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  fics: {
    list: (params = {}) => request(`/fics?${new URLSearchParams(params)}`),
    get: (id) => request(`/fics/${id}`),
  },
  ao3: {
    // Tarda ~10s reales (login + fetch, con el rate limit de 4s entre
    // peticiones a AO3 de por medio) — es intencional, no un timeout a
    // arreglar.
    importarPorUrl: (url, force = false) =>
      request("/ao3/import-fic", { method: "POST", body: JSON.stringify({ url, force }) }),
    descargarEpub: (ficId) => request(`/fics/${ficId}/download-epub`, { method: "POST" }),
  },
  lecturas: {
    create: (ficId, payload) =>
      request(`/fics/${ficId}/lecturas`, { method: "POST", body: JSON.stringify(payload) }),
    update: (ficId, lecturaId, payload) =>
      request(`/fics/${ficId}/lecturas/${lecturaId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    remove: (ficId, lecturaId) =>
      request(`/fics/${ficId}/lecturas/${lecturaId}`, { method: "DELETE" }),
  },
  resenas: {
    create: (ficId, payload) =>
      request(`/fics/${ficId}/resenas`, { method: "POST", body: JSON.stringify(payload) }),
    update: (ficId, resenaId, payload) =>
      request(`/fics/${ficId}/resenas/${resenaId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
  },
  colecciones: {
    list: () => request("/colecciones"),
    get: (id) => request(`/colecciones/${id}`),
    create: (payload) => request("/colecciones", { method: "POST", body: JSON.stringify(payload) }),
    update: (id, payload) =>
      request(`/colecciones/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    remove: (id) => request(`/colecciones/${id}`, { method: "DELETE" }),
    addFic: (id, ficId) => request(`/colecciones/${id}/fics/${ficId}`, { method: "PUT" }),
    removeFic: (id, ficId) => request(`/colecciones/${id}/fics/${ficId}`, { method: "DELETE" }),
  },
  etiquetas: {
    list: () => request("/etiquetas"),
    remove: (id) => request(`/etiquetas/${id}`, { method: "DELETE" }),
    addToFic: (ficId, nombre) =>
      request(`/fics/${ficId}/etiquetas`, { method: "POST", body: JSON.stringify({ nombre }) }),
    removeFromFic: (ficId, etiquetaId) =>
      request(`/fics/${ficId}/etiquetas/${etiquetaId}`, { method: "DELETE" }),
  },
  archivos: {
    list: () => request("/archivos"),
    contenidoUrl: (archivoId) => {
      const token = getToken();
      const query = token ? `?token=${encodeURIComponent(token)}` : "";
      return `${API_BASE}/archivos/${archivoId}/contenido${query}`;
    },
  },
  importLog: {
    list: (limit = 20) => request(`/import-log?limit=${limit}`),
  },
  stats: {
    resumen: () => request("/stats/resumen"),
    topFandoms: (limite = 10) => request(`/stats/top-fandoms?limite=${limite}`),
    topShips: (limite = 10, tipo) =>
      request(`/stats/top-ships?${new URLSearchParams({ limite, ...(tipo ? { tipo } : {}) })}`),
    palabrasPorMes: (anio) =>
      request(`/stats/palabras-por-mes${anio ? `?anio=${anio}` : ""}`),
    distribucionLongitud: () => request("/stats/distribucion-longitud"),
    ratioWipCompletos: () => request("/stats/ratio-wip-completos"),
    estadoLectura: () => request("/stats/estado-lectura"),
    relecturas: (limite = 10) => request(`/stats/relecturas?limite=${limite}`),
    ratingPorFandom: () => request("/stats/rating-por-fandom"),
  },
};
