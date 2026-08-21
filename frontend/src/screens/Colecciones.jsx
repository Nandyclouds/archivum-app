import { useState } from "react";
import { Link } from "react-router-dom";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

const TIPO_LABEL = {
  personalizada: "Personalizada",
  bookmark_tag: "Tag de AO3",
  fandom: "Fandom",
  ship: "Ship",
  estado: "Estado",
};

export function Colecciones() {
  const colecciones = useFetch(() => api.colecciones.list());
  const [nombreNueva, setNombreNueva] = useState("");
  const [creando, setCreando] = useState(false);

  async function crear() {
    if (!nombreNueva.trim()) return;
    setCreando(true);
    try {
      await api.colecciones.create({ nombre: nombreNueva.trim() });
      setNombreNueva("");
      colecciones.reload();
    } finally {
      setCreando(false);
    }
  }

  if (colecciones.loading) return <Cargando />;
  if (colecciones.error) return <ErrorCarga error={colecciones.error} onReintentar={colecciones.reload} />;

  return (
    <div>
      {colecciones.data.length === 0 && <Vacio>Todavía no tenés colecciones.</Vacio>}

      <div className="arv-card">
        {colecciones.data.map((c) => (
          <Link to={`/colecciones/${c.id}`} className="arv-list-item arv-row-link" key={c.id}>
            <div>
              <span className="arv-tag arv-tag-accent-2" style={{ marginRight: 8 }}>
                {TIPO_LABEL[c.tipo] ?? c.tipo}
              </span>
              {c.nombre}
            </div>
            <span className="arv-muted">{c.cantidad_fics} fics</span>
          </Link>
        ))}
      </div>

      <div className="arv-card">
        <h3>Nueva colección</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="arv-input"
            placeholder="Nombre"
            value={nombreNueva}
            onChange={(e) => setNombreNueva(e.target.value)}
          />
          <button className="arv-btn" disabled={creando} onClick={crear}>
            Crear
          </button>
        </div>
      </div>
    </div>
  );
}
