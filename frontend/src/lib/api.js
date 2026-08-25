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

function buildQuery(params) {
  const query = new URLSearchParams();
  for (const [clave, valor] of Object.entries(params)) {
    if (valor === null || valor === undefined || valor === "") continue;
    if (Array.isArray(valor)) {
      for (const v of valor) query.append(clave, v);
    } else {
      query.append(clave, valor);
    }
  }
  return query;
}

export const api = {
  fics: {
    list: (params = {}) => request(`/fics?${buildQuery(params)}`),
    get: (id) => request(`/fics/${id}`),
    opcionesFiltro: () => request("/fics/opciones-filtro"),
  },
  ao3: {
    // Tarda ~10s reales (login + fetch, con el rate limit de 4s entre
    // peticiones a AO3 de por medio) — es intencional, no un timeout a
    // arreglar. Solo funciona si ESTE server tiene salida a AO3 (uso local);
    // en PythonAnywhere y similares usar api.sync.trigger en su lugar.
    importarPorUrl: (url, force = false) =>
      request("/ao3/import-fic", { method: "POST", body: JSON.stringify({ url, force }) }),
    descargarEpub: (ficId) => request(`/fics/${ficId}/download-epub`, { method: "POST" }),
  },
  sync: {
    // Dispara el workflow de GitHub Actions (ver .github/workflows/ao3-sync.yml)
    // para hosts sin salida directa a AO3. Es asíncrono: esto solo confirma
    // que arrancó, no que ya terminó — tarda entre segundos y minutos.
    trigger: (modo, { url, ao3Id } = {}) =>
      request("/sync/trigger", {
        method: "POST",
        body: JSON.stringify({ modo, url, ao3_id: ao3Id }),
      }),
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
  novedades: {
    list: (soloNoLeidas = true) => request(`/novedades?${buildQuery({ solo_no_leidas: soloNoLeidas })}`),
    marcarLeida: (id) => request(`/novedades/${id}/marcar-leida`, { method: "POST" }),
    marcarTodasLeidas: () => request("/novedades/marcar-todas-leidas", { method: "POST" }),
  },
  archivos: {
    list: () => request("/archivos"),
    remove: (archivoId) => request(`/archivos/${archivoId}`, { method: "DELETE" }),
    contenidoUrl: (archivoId) => {
      const token = getToken();
      const query = token ? `?token=${encodeURIComponent(token)}` : "";
      return `${API_BASE}/archivos/${archivoId}/contenido${query}`;
    },
  },
  importLog: {
    list: (limit = 20) => request(`/import-log?limit=${limit}`),
  },
  perfil: {
    get: () => request("/perfil"),
    imagenUrl: (tipo) => {
      const token = getToken();
      const query = token ? `?token=${encodeURIComponent(token)}` : "";
      return `${API_BASE}/perfil/imagen/${tipo}${query}`;
    },
    subirImagen: async (tipo, archivo) => {
      const formData = new FormData();
      formData.append("archivo", archivo);
      const token = getToken();
      const response = await fetch(`${API_BASE}/perfil/${tipo}`, {
        method: "POST",
        headers: token ? { "X-Archivum-Token": token } : {},
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(`${response.status}: ${body.detail ?? response.statusText}`);
      }
      return response.json();
    },
    actualizarCita: (cita_texto, cita_fuente) =>
      request("/perfil", { method: "PATCH", body: JSON.stringify({ cita_texto, cita_fuente }) }),
    actualizarIdentidad: (nombre_usuario, handle, pronombres, insignia, bio) =>
      request("/perfil", {
        method: "PATCH",
        body: JSON.stringify({ nombre_usuario, handle, pronombres, insignia, bio }),
      }),
    actualizarPosicion: (tipo, x, y) =>
      request(`/perfil/posicion/${tipo}`, { method: "PUT", body: JSON.stringify({ x, y }) }),
    favoritos: {
      list: () => request("/perfil/favoritos"),
      add: (ficId) =>
        request("/perfil/favoritos", { method: "POST", body: JSON.stringify({ fic_id: ficId }) }),
      remove: (ficId) => request(`/perfil/favoritos/${ficId}`, { method: "DELETE" }),
      setDestacados: (ficIds) =>
        request("/perfil/favoritos/destacados", {
          method: "PUT",
          body: JSON.stringify({ fic_ids: ficIds }),
        }),
    },
  },
  recomendaciones: {
    list: () => request("/recomendaciones"),
    create: (payload) => request("/recomendaciones", { method: "POST", body: JSON.stringify(payload) }),
    remove: (id) => request(`/recomendaciones/${id}`, { method: "DELETE" }),
    // Pública (ver app/main.py) — no manda el token, o lo manda y no importa:
    // este endpoint no lo exige.
    get: (token) => request(`/recomendaciones/${token}`),
  },
  stats: {
    resumen: (anio) => request(`/stats/resumen${anio ? `?anio=${anio}` : ""}`),
    topFandoms: (limite = 10, anio) =>
      request(`/stats/top-fandoms?${new URLSearchParams({ limite, ...(anio ? { anio } : {}) })}`),
    topShips: (limite = 10, tipo, anio) =>
      request(
        `/stats/top-ships?${new URLSearchParams({
          limite,
          ...(tipo ? { tipo } : {}),
          ...(anio ? { anio } : {}),
        })}`
      ),
    palabrasPorMes: (anio) =>
      request(`/stats/palabras-por-mes${anio ? `?anio=${anio}` : ""}`),
    palabrasPorAnio: () => request("/stats/palabras-por-anio"),
    distribucionLongitud: () => request("/stats/distribucion-longitud"),
    ratioWipCompletos: () => request("/stats/ratio-wip-completos"),
    estadoLectura: () => request("/stats/estado-lectura"),
    relecturas: (limite = 10) => request(`/stats/relecturas?limite=${limite}`),
    ratingPorFandom: () => request("/stats/rating-por-fandom"),
  },
  emojis: {
    list: () => request("/emojis"),
    create: async (nombre, archivo) => {
      const formData = new FormData();
      formData.append("nombre", nombre);
      formData.append("archivo", archivo);
      const token = getToken();
      const response = await fetch(`${API_BASE}/emojis`, {
        method: "POST",
        headers: token ? { "X-Archivum-Token": token } : {},
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(`${response.status}: ${body.detail ?? response.statusText}`);
      }
      return response.json();
    },
    remove: (id) => request(`/emojis/${id}`, { method: "DELETE" }),
    imagenUrl: (id) => {
      const token = getToken();
      const query = token ? `?token=${encodeURIComponent(token)}` : "";
      return `${API_BASE}/emojis/${id}/imagen${query}`;
    },
  },
};
