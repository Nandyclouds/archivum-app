import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Archivum',
        short_name: 'Archivum',
        description: 'Tracker local de fanfics de AO3',
        start_url: '/',
        display: 'standalone',
        background_color: '#f5ead8',
        theme_color: '#c05a3f',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
        // Web Share Target: al elegir "Archivum" desde el menú Compartir de
        // Android (ej. compartiendo un link de AO3 desde Chrome), el navegador
        // navega a esta URL con el link como query param "url". Solo Android;
        // iOS no soporta share_target en manifests de PWA.
        share_target: {
          action: '/compartir',
          method: 'GET',
          params: {
            title: 'title',
            text: 'text',
            url: 'url',
          },
        },
      },
      workbox: {
        // sin cache agresivo: es una app local contra datos que cambian
        // seguido, no queremos servir stats viejas desde el service worker
        runtimeCaching: [],
        // El navigateFallback (necesario para que rutas de React Router
        // como /fics/5 funcionen al entrar directo) por defecto intercepta
        // TODA navegación de página completa, incluida la API. Toda la API
        // vive bajo /api (ver app/main.py) justamente para que este patrón
        // sea simple y no se pueda desincronizar de la lista de routers.
        navigateFallbackDenylist: [/^\/api(\/|$|\?)/, /^\/(docs|redoc|openapi\.json)(\/|$|\?)/],
      },
    }),
  ],
})
