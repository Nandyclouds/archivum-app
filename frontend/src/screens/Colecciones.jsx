import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { GripVertical } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n));
}

export function Colecciones() {
  const { t } = useTranslation();
  const colecciones = useFetch(() => api.colecciones.list(), [], "colecciones-lista");
  const [nombreNueva, setNombreNueva] = useState("");
  const [creando, setCreando] = useState(false);
  const [reordenando, setReordenando] = useState(false);
  const [orden, setOrden] = useState([]);
  const [guardandoOrden, setGuardandoOrden] = useState(false);
  const arrastre = useRef(null);

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

  function empezarReorden() {
    setOrden(colecciones.data);
    setReordenando(true);
  }

  function cancelarReorden() {
    setReordenando(false);
  }

  async function guardarOrden() {
    setGuardandoOrden(true);
    try {
      await Promise.all(orden.map((c, i) => api.colecciones.update(c.id, { orden: i })));
      setReordenando(false);
      colecciones.reload();
    } catch (err) {
      alert(err.message);
    } finally {
      setGuardandoOrden(false);
    }
  }

  function onPointerDown(e, indice) {
    const fila = e.currentTarget.closest(".arv-list-item");
    const rect = fila.getBoundingClientRect();
    arrastre.current = { indiceInicial: indice, indiceActual: indice, startY: e.clientY, rowHeight: rect.height };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e) {
    if (!arrastre.current) return;
    const { indiceInicial, indiceActual, startY, rowHeight } = arrastre.current;
    const pasos = Math.round((e.clientY - startY) / rowHeight);
    const nuevoIndice = clamp(indiceInicial + pasos, 0, orden.length - 1);
    if (nuevoIndice !== indiceActual) {
      setOrden((prev) => {
        const copia = [...prev];
        const [item] = copia.splice(indiceActual, 1);
        copia.splice(nuevoIndice, 0, item);
        return copia;
      });
      arrastre.current.indiceActual = nuevoIndice;
    }
  }

  function onPointerUp() {
    arrastre.current = null;
  }

  if (colecciones.loading) return <Cargando />;
  if (colecciones.error) return <ErrorCarga error={colecciones.error} onReintentar={colecciones.reload} />;

  const lista = reordenando ? orden : colecciones.data;

  return (
    <div>
      {lista.length === 0 && <Vacio>{t("colecciones.sinColecciones")}</Vacio>}

      <div className="arv-card">
        {lista.length > 1 && (
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 10 }}>
            {reordenando ? (
              <>
                <button className="arv-btn" disabled={guardandoOrden} onClick={guardarOrden}>
                  {t("common.guardar")}
                </button>
                <button className="arv-btn arv-btn-secondary" onClick={cancelarReorden}>
                  {t("common.cancelar")}
                </button>
              </>
            ) : (
              <button
                className="arv-muted"
                onClick={empezarReorden}
                style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontSize: 12.5 }}
              >
                {t("colecciones.ordenar")}
              </button>
            )}
          </div>
        )}

        {lista.map((c, i) =>
          reordenando ? (
            <div className="arv-list-item" key={c.id}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                <span
                  onPointerDown={(e) => onPointerDown(e, i)}
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                  style={{ touchAction: "none", cursor: "grab", display: "flex", color: "var(--color-text-muted)" }}
                >
                  <GripVertical size={16} />
                </span>
                <span className="arv-tag arv-tag-accent-2">{t(`colecciones.tipoLabel.${c.tipo}`, c.tipo)}</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.nombre}</span>
              </div>
            </div>
          ) : (
            <Link to={`/colecciones/${c.id}`} className="arv-list-item arv-row-link" key={c.id}>
              <div>
                <span className="arv-tag arv-tag-accent-2" style={{ marginRight: 8 }}>
                  {t(`colecciones.tipoLabel.${c.tipo}`, c.tipo)}
                </span>
                {c.nombre}
              </div>
              <span className="arv-muted">{t("colecciones.fics", { count: c.cantidad_fics })}</span>
            </Link>
          )
        )}
      </div>

      <div className="arv-card">
        <h3>{t("colecciones.nuevaColeccion")}</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="arv-input"
            placeholder={t("colecciones.nombrePlaceholder")}
            value={nombreNueva}
            onChange={(e) => setNombreNueva(e.target.value)}
          />
          <button className="arv-btn" disabled={creando} onClick={crear}>
            {t("common.crear")}
          </button>
        </div>
      </div>
    </div>
  );
}
