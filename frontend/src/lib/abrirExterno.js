// Un link normal a /archivos/x/contenido, clickeado desde dentro de la PWA
// instalada (misma origin + dentro del scope del manifest), se queda
// abierto en la ventana propia de la PWA en vez de abrir Chrome de verdad
// (así es como Android maneja la navegación dentro de una PWA standalone).
// En Android forzamos el navegador real con un intent:// explícito; en
// cualquier otra plataforma, un window.open normal alcanza.
export function abrirEnNavegadorExterno(url) {
  // Absoluta siempre: la API devuelve rutas relativas ("/api/archivos/38/..."),
  // e intent:// necesita host de verdad — sin esto Android intentaba resolver
  // "api" como si fuera un dominio (DNS_PROBE_FINISHED_NXDOMAIN). Bug real.
  const absoluta = new URL(url, window.location.origin).href;
  const esAndroid = /Android/i.test(navigator.userAgent);
  if (esAndroid) {
    const sinEsquema = absoluta.replace(/^https?:\/\//, "");
    window.location.href = `intent://${sinEsquema}#Intent;scheme=https;package=com.android.chrome;end;`;
  } else {
    window.open(absoluta, "_blank", "noopener");
  }
}
