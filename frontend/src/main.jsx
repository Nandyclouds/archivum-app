import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './i18n'
import { cargarTema, cargarColorAcento } from './lib/tema'
import App from './App.jsx'

cargarTema()
cargarColorAcento()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
