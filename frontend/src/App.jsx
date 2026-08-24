import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthGate } from "./components/AuthGate";
import { NavBar } from "./components/NavBar";
import { Panel } from "./screens/Panel";
import { TopCompleto } from "./screens/TopCompleto";
import { Buscar } from "./screens/Buscar";
import { FicDetalle } from "./screens/FicDetalle";
import { Colecciones } from "./screens/Colecciones";
import { ColeccionDetalle } from "./screens/ColeccionDetalle";
import { Perfil } from "./screens/Perfil";
import { Archivo } from "./screens/Archivo";
import { Ao3 } from "./screens/Ao3";
import { Compartir } from "./screens/Compartir";

export default function App() {
  return (
    <AuthGate>
      <BrowserRouter>
        <div className="arv-app">
          <header className="arv-topbar">
            <h1>Archivum</h1>
            <NavBar />
          </header>
          <main className="arv-main">
            <Routes>
              <Route path="/" element={<Panel />} />
              <Route path="/panel/top/:tipo" element={<TopCompleto />} />
              <Route path="/perfil" element={<Perfil />} />
              <Route path="/buscar" element={<Buscar />} />
              <Route path="/fics/:id" element={<FicDetalle />} />
              <Route path="/colecciones" element={<Colecciones />} />
              <Route path="/colecciones/:id" element={<ColeccionDetalle />} />
              <Route path="/archivo" element={<Archivo />} />
              <Route path="/ao3" element={<Ao3 />} />
              <Route path="/compartir" element={<Compartir />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </AuthGate>
  );
}
