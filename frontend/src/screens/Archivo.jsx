import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { abrirEnNavegadorExterno, descargarArchivo } from "../lib/abrirExterno";
import { InfoPopover } from "../components/InfoPopover";

export function Archivo() {
  const { t, i18n } = useTranslation();
  const archivos = useFetch(() => api.archivos.list());

  if (archivos.loading) return <Cargando />;
  if (archivos.error) return <ErrorCarga error={archivos.error} onReintentar={archivos.reload} />;

  async function descargarHtml(a) {
    try {
      await descargarArchivo(api.archivos.contenidoUrl(a.id), `${a.fic_titulo}.html`);
    } catch (err) {
      alert(err.message);
    }
  }

  const FORMATO_LABEL = { html: t("archivo.verCopia"), epub: t("archivo.descargarEpub") };

  return (
    <div>
      <div className="arv-card">
        <h2 style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          {t("archivo.titulo")}
          <InfoPopover>
            {t("archivo.infoParte1")} <code>download --all-unarchived</code> {t("archivo.infoParte2")}
          </InfoPopover>
        </h2>
      </div>

      {archivos.data.length === 0 && <Vacio>{t("archivo.sinArchivos")}</Vacio>}

      <div className="arv-card">
        {archivos.data.map((a) => (
          <div className="arv-list-item" key={a.id}>
            <div>
              <div style={{ fontWeight: 600 }}>{a.fic_titulo}</div>
              <div className="arv-muted">
                {t("archivo.guardado", { fecha: new Date(a.fecha_descarga).toLocaleDateString(i18n.language) })}
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "stretch", gap: 6, width: 130 }}>
              <span
                className={`arv-tag ${a.fic_deleted_detected_at ? "arv-tag-accent" : "arv-tag-accent-2"}`}
                style={{ justifyContent: "center" }}
              >
                {a.fic_deleted_detected_at ? t("archivo.originalEliminado") : t("archivo.disponible")}
              </span>
              <button
                className="arv-btn arv-btn-secondary"
                onClick={() => abrirEnNavegadorExterno(api.archivos.contenidoUrl(a.id))}
              >
                {FORMATO_LABEL[a.formato] ?? a.formato}
              </button>
              {a.formato === "html" && (
                <button className="arv-btn arv-btn-secondary" onClick={() => descargarHtml(a)}>
                  {t("archivo.descargar")}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
