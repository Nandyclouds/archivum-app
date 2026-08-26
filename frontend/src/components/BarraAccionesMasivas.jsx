import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Library, Tag, CircleCheck, Share2, X } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";

const ESTADOS = ["pendiente", "leyendo", "leido", "abandonado"];

/** Barra fija abajo que aparece mientras hay fics seleccionados (modo
 * selección de FilaFicSeleccionable) — agregar a colección/etiqueta, cambiar
 * estado de lectura, o mandar a armar una recomendación, todo en lote. */
export function BarraAccionesMasivas({ seleccionIds, onLimpiar, onAplicado }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [panel, setPanel] = useState(null); // "coleccion" | "etiqueta" | "estado" | null
  const [nombreEtiqueta, setNombreEtiqueta] = useState("");
  const [aplicando, setAplicando] = useState(false);
  const colecciones = useFetch(() => api.colecciones.list());

  const ids = [...seleccionIds];

  function alternarPanel(nombre) {
    setPanel((p) => (p === nombre ? null : nombre));
  }

  async function aplicarColeccion(coleccionId) {
    setAplicando(true);
    try {
      await api.masivo.colecciones(ids, coleccionId);
      setPanel(null);
      onAplicado();
    } finally {
      setAplicando(false);
    }
  }

  async function aplicarEtiqueta() {
    if (!nombreEtiqueta.trim()) return;
    setAplicando(true);
    try {
      await api.masivo.etiquetas(ids, nombreEtiqueta.trim());
      setNombreEtiqueta("");
      setPanel(null);
      onAplicado();
    } finally {
      setAplicando(false);
    }
  }

  async function aplicarEstado(estado) {
    setAplicando(true);
    try {
      await api.masivo.lecturas(ids, estado);
      setPanel(null);
      onAplicado();
    } finally {
      setAplicando(false);
    }
  }

  function irARecomendar() {
    navigate(`/recomendar?ids=${ids.join(",")}`);
  }

  return (
    <div className="arv-masivo-wrap">
      {panel && (
        <div className="arv-masivo-panel">
          {panel === "coleccion" && (
            <div className="arv-coleccion-picker" style={{ marginBottom: 0 }}>
              {colecciones.data?.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="arv-coleccion-picker-item"
                  disabled={aplicando}
                  onClick={() => aplicarColeccion(c.id)}
                >
                  <span className="arv-coleccion-picker-nombre">{c.nombre}</span>
                </button>
              ))}
              {colecciones.data?.length === 0 && (
                <p className="arv-muted" style={{ margin: 8 }}>
                  {t("colecciones.sinColecciones")}
                </p>
              )}
            </div>
          )}
          {panel === "etiqueta" && (
            <div style={{ display: "flex", gap: 8 }}>
              <input
                className="arv-input"
                placeholder={t("ficDetalle.nuevaEtiquetaPlaceholder")}
                value={nombreEtiqueta}
                onChange={(e) => setNombreEtiqueta(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && aplicarEtiqueta()}
                autoFocus
              />
              <button className="arv-btn" disabled={aplicando} onClick={aplicarEtiqueta}>
                {t("ficDetalle.agregar")}
              </button>
            </div>
          )}
          {panel === "estado" && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {ESTADOS.map((e) => (
                <button
                  key={e}
                  className="arv-btn arv-btn-secondary"
                  disabled={aplicando}
                  onClick={() => aplicarEstado(e)}
                >
                  {t(`ficDetalle.estados.${e}`)}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="arv-masivo-barra">
        <span className="arv-masivo-cuenta">{t("buscar.seleccionados", { count: ids.length })}</span>
        <div style={{ display: "flex", gap: 4 }}>
          <button
            className={`arv-icon-btn${panel === "coleccion" ? " active" : ""}`}
            onClick={() => alternarPanel("coleccion")}
            aria-label={t("buscar.aColeccion")}
            title={t("buscar.aColeccion")}
          >
            <Library size={17} />
          </button>
          <button
            className={`arv-icon-btn${panel === "etiqueta" ? " active" : ""}`}
            onClick={() => alternarPanel("etiqueta")}
            aria-label={t("buscar.aEtiqueta")}
            title={t("buscar.aEtiqueta")}
          >
            <Tag size={17} />
          </button>
          <button
            className={`arv-icon-btn${panel === "estado" ? " active" : ""}`}
            onClick={() => alternarPanel("estado")}
            aria-label={t("buscar.aEstado")}
            title={t("buscar.aEstado")}
          >
            <CircleCheck size={17} />
          </button>
          <button className="arv-icon-btn" onClick={irARecomendar} aria-label={t("buscar.aRecomendar")} title={t("buscar.aRecomendar")}>
            <Share2 size={17} />
          </button>
          <button
            className="arv-icon-btn"
            onClick={onLimpiar}
            aria-label={t("buscar.cancelarSeleccion")}
            title={t("buscar.cancelarSeleccion")}
          >
            <X size={17} />
          </button>
        </div>
      </div>
    </div>
  );
}
