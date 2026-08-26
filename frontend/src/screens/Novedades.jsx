import { useTranslation } from "react-i18next";
import { Check } from "lucide-react";
import { api } from "../lib/api";
import { useNovedades } from "../lib/NovedadesContext";
import { Cargando, Vacio } from "../components/EstadoCarga";
import { FilaFicSeleccionable } from "../components/FilaFicSeleccionable";
import { BarraAccionesMasivas } from "../components/BarraAccionesMasivas";
import { useSeleccionMultiple } from "../lib/useSeleccionMultiple";

export function Novedades() {
  const { t, i18n } = useTranslation();
  const { lista, cargando, recargar } = useNovedades();
  const { seleccion, activa: seleccionActiva, activar, alternar, limpiar } = useSeleccionMultiple();

  if (cargando) return <Cargando />;

  async function marcarLeida(id) {
    try {
      await api.novedades.marcarLeida(id);
      recargar();
    } catch (err) {
      alert(err.message);
    }
  }

  async function marcarTodas() {
    try {
      await api.novedades.marcarTodasLeidas();
      recargar();
    } catch (err) {
      alert(err.message);
    }
  }

  return (
    <div>
      <div className="arv-card">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>{t("novedades.titulo")}</h2>
          {lista.length > 0 && (
            <button className="arv-btn arv-btn-secondary" onClick={marcarTodas}>
              {t("novedades.marcarTodas")}
            </button>
          )}
        </div>
      </div>

      {lista.length === 0 && <Vacio>{t("novedades.sinNovedades")}</Vacio>}

      <div className="arv-card" style={seleccionActiva ? { marginBottom: 90 } : undefined}>
        {lista.map((n) => (
          <FilaFicSeleccionable
            key={n.id}
            ficId={n.fic_id}
            to={`/fics/${n.fic_id}`}
            className="arv-list-item"
            seleccionActiva={seleccionActiva}
            seleccionado={seleccion.has(n.fic_id)}
            onLongPress={activar}
            onToggle={alternar}
          >
            <div>
              <div style={{ fontWeight: 600 }}>{n.fic_titulo}</div>
              <div className="arv-muted">
                {n.tipo === "completado"
                  ? t("novedades.completado")
                  : t("novedades.capituloNuevo", { count: n.capitulos_publicados })}
              </div>
              <div className="arv-muted" style={{ fontSize: 11.5 }}>
                {new Date(n.detectado_en).toLocaleString(i18n.language)}
              </div>
            </div>
            {!seleccionActiva && (
              <button
                className="arv-icon-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  marcarLeida(n.id);
                }}
                aria-label={t("novedades.marcarLeida")}
                title={t("novedades.marcarLeida")}
              >
                <Check size={16} />
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
            recargar();
          }}
        />
      )}
    </div>
  );
}
