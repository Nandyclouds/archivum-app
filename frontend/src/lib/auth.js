const STORAGE_KEY = "archivum_token";

export function getToken() {
  return localStorage.getItem(STORAGE_KEY) || "";
}

export function setToken(token) {
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(STORAGE_KEY);
  // Si el próximo login es de otra cuenta en este mismo dispositivo, no
  // debería poder ver sin internet lo que quedó cacheado de esta sesión.
  if ("caches" in window) {
    caches.delete("archivum-api-cache").catch(() => {});
  }
}
