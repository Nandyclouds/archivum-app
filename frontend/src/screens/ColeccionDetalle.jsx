import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

export function ColeccionDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const coleccion = useFetch(() => api.colecciones.get(id), [id]);
  const fics = useFetch(() => api.fics.list({ coleccion: id, limit: 200 }), [id]);

  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState("");
  const [guardando, setGuardando] = useState(false);

  if (coleccion.loading) return <Cargando />;
  if (coleccion.error) return <ErrorCarga error={coleccion.error} onReintentar={coleccion.reload} />;

  const c = coleccion.data;

  async function guardarNombre() {
    if (!nombre.trim()) return;
    setGuardando(true);
    try {
      await api.colecciones.update(id, { nombre: nombre.trim() });
      setEditando(false);
      coleccion.reload();
    } finally {
      setGuardando(false);
    }
  }

  async function borrarColeccion() {
    await api.colecciones.remove(id);
    navigate("/colecciones");
  }

  async function quitarFic(ficId) {
    await api.colecciones.removeFic(id, ficId);
    fics.reload();
    coleccion.reload();
  }

  return (
    <div>
      <div className="arv-card">
        {!editando ? (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>{c.nombre}</h2>
            <button
              className="arv-btn arv-btn-secondary"
              onClick={() => {
                setNombre(c.nombre);
                setEditando(true);
              }}
            >
              Editar
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 8 }}>
            <input
              className="arv-input"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              autoFocus
            />
            <button className="arv-btn" disabled={guardando} onClick={guardarNombre}>
              Guardar
            </button>
            <button className="arv-btn arv-btn-secondary" onClick={() => setEditando(false)}>
              Cancelar
            </button>
          </div>
        )}
        <p className="arv-muted" style={{ marginBottom: 0 }}>
          {c.cantidad_fics} fics
        </p>
      </div>

      {fics.loading && <Cargando />}
      {fics.error && <ErrorCarga error={fics.error} onReintentar={fics.reload} />}
      {fics.data?.length === 0 && <Vacio>Todavía no agregaste ningún fic acá.</Vacio>}

      <div className="arv-card">
        {fics.data?.map((fic) => (
          <div className="arv-list-item" key={fic.id}>
            <Link to={`/fics/${fic.id}`} style={{ textDecoration: "none", color: "inherit" }}>
              <div className="fandom">{fic.fandoms[0]?.nombre ?? "Sin fandom"}</div>
              <div className="titulo">{fic.titulo}</div>
            </Link>
            <button
              onClick={() => quitarFic(fic.id)}
              aria-label="Quitar de la colección"
              style={{
                border: "none",
                background: "transparent",
                color: "var(--color-text-muted)",
                cursor: "pointer",
                fontSize: 14,
                padding: 2,
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="arv-card">
        <button className="arv-btn arv-btn-secondary" onClick={borrarColeccion}>
          Borrar colección
        </button>
      </div>
    </div>
  );
}
