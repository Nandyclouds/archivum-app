import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { FilaFicSeleccionable } from "../components/FilaFicSeleccionable";
import { BarraAccionesMasivas } from "../components/BarraAccionesMasivas";
import { useSeleccionMultiple } from "../lib/useSeleccionMultiple";

export function ColeccionDetalle() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const coleccion = useFetch(() => api.colecciones.get(id), [id]);
  const fics = useFetch(() => api.fics.list({ coleccion: id, limit: 200 }), [id]);
  const { seleccion, activa: seleccionActiva, activar, alternar, limpiar } = useSeleccionMultiple();

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
              {t("common.editar")}
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
              {t("common.guardar")}
            </button>
            <button className="arv-btn arv-btn-secondary" onClick={() => setEditando(false)}>
              {t("common.cancelar")}
            </button>
          </div>
        )}
        <p className="arv-muted" style={{ marginBottom: 0 }}>
          {t("coleccionDetalle.fics", { count: c.cantidad_fics })}
        </p>
      </div>

      {fics.loading && <Cargando />}
      {fics.error && <ErrorCarga error={fics.error} onReintentar={fics.reload} />}
      {fics.data?.length === 0 && <Vacio>{t("coleccionDetalle.sinFics")}</Vacio>}

      <div className="arv-card" style={seleccionActiva ? { marginBottom: 90 } : undefined}>
        {fics.data?.map((fic) => (
          <FilaFicSeleccionable
            key={fic.id}
            ficId={fic.id}
            to={`/fics/${fic.id}`}
            className="arv-list-item"
            seleccionActiva={seleccionActiva}
            seleccionado={seleccion.has(fic.id)}
            onLongPress={activar}
            onToggle={alternar}
          >
            <div style={{ minWidth: 0 }}>
              <div className="fandom">{fic.fandoms[0]?.nombre ?? t("common.sinFandom")}</div>
              <div className="titulo">{fic.titulo}</div>
            </div>
            {!seleccionActiva && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  quitarFic(fic.id);
                }}
                aria-label={t("coleccionDetalle.quitarDeColeccion")}
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
            )}
          </FilaFicSeleccionable>
        ))}
      </div>

      {seleccionActiva && (
        <BarraAccionesMasivas
          seleccionIds={seleccion}
          onLimpiar={limpiar}
          onAplicado={() => {
            limpiar();
            fics.reload();
            coleccion.reload();
          }}
        />
      )}

      <div className="arv-card">
        <button className="arv-btn arv-btn-secondary" onClick={borrarColeccion}>
          {t("coleccionDetalle.borrarColeccion")}
        </button>
      </div>
    </div>
  );
}
