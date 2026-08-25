import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

export function Colecciones() {
  const { t } = useTranslation();
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
      {colecciones.data.length === 0 && <Vacio>{t("colecciones.sinColecciones")}</Vacio>}

      <div className="arv-card">
        {colecciones.data.map((c) => (
          <Link to={`/colecciones/${c.id}`} className="arv-list-item arv-row-link" key={c.id}>
            <div>
              <span className="arv-tag arv-tag-accent-2" style={{ marginRight: 8 }}>
                {t(`colecciones.tipoLabel.${c.tipo}`, c.tipo)}
              </span>
              {c.nombre}
            </div>
            <span className="arv-muted">{t("colecciones.fics", { count: c.cantidad_fics })}</span>
          </Link>
        ))}
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
