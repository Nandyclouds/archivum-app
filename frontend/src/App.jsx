import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthGate } from "./components/AuthGate";
import { NavBar } from "./components/NavBar";
import { NovedadesProvider } from "./lib/NovedadesContext";
import { Panel } from "./screens/Panel";
import { TopCompleto } from "./screens/TopCompleto";
import { Buscar } from "./screens/Buscar";
import { FicDetalle } from "./screens/FicDetalle";
import { Colecciones } from "./screens/Colecciones";
import { ColeccionDetalle } from "./screens/ColeccionDetalle";
import { Perfil } from "./screens/Perfil";
import { Archivo } from "./screens/Archivo";
import { Ao3 } from "./screens/Ao3";
import { Novedades } from "./screens/Novedades";
import { Compartir } from "./screens/Compartir";
import { Recomendar } from "./screens/Recomendar";
import { Recomendacion } from "./screens/Recomendacion";

function AppShell() {
  const location = useLocation();
  // En Perfil (pantalla de inicio) la portada llega hasta arriba de todo,
  // sin el título ni la barra encima empujándola — la barra se muestra
  // fija abajo en su lugar, para no perder la forma de navegar.
  const esPerfil = location.pathname === "/";

  return (
    <div className="arv-app">
      {!esPerfil && (
        <header className="arv-topbar">
          <h1>Archivum</h1>
          <NavBar />
        </header>
      )}
      <main className={`arv-main${esPerfil ? " arv-main-full-bleed" : ""}`}>
        <Routes>
          <Route path="/" element={<Perfil />} />
          <Route path="/panel" element={<Panel />} />
          <Route path="/panel/top/:tipo" element={<TopCompleto />} />
          <Route path="/buscar" element={<Buscar />} />
          <Route path="/fics/:id" element={<FicDetalle />} />
          <Route path="/colecciones" element={<Colecciones />} />
          <Route path="/colecciones/:id" element={<ColeccionDetalle />} />
          <Route path="/archivo" element={<Archivo />} />
          <Route path="/ao3" element={<Ao3 />} />
          <Route path="/novedades" element={<Novedades />} />
          <Route path="/compartir" element={<Compartir />} />
          <Route path="/recomendar" element={<Recomendar />} />
        </Routes>
      </main>
      {esPerfil && <NavBar className="arv-navbar-abajo" minimal />}
    </div>
  );
}

function AppAutenticada() {
  return (
    <AuthGate>
      <NovedadesProvider>
        <AppShell />
      </NovedadesProvider>
    </AuthGate>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Pública a propósito: es el link que se comparte con gente que no
            tiene el código de acceso a la app (ver app/main.py). */}
        <Route path="/recomendar/:token" element={<Recomendacion />} />
        <Route path="/*" element={<AppAutenticada />} />
      </Routes>
    </BrowserRouter>
  );
}
