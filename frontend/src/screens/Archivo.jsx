import { useTranslation } from "react-i18next";
import { Eye, Download, Trash2 } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { abrirEnNavegadorExterno, descargarArchivo } from "../lib/abrirExterno";
import { InfoPopover } from "../components/InfoPopover";

function agruparPorFic(archivos) {
  const porFic = new Map();
  for (const a of archivos) {
    if (!porFic.has(a.fic_id)) {
      porFic.set(a.fic_id, {
        fic_id: a.fic_id,
        fic_titulo: a.fic_titulo,
        fic_deleted_detected_at: a.fic_deleted_detected_at,
        fecha_descarga: a.fecha_descarga,
        html: null,
        epub: null,
      });
    }
    const grupo = porFic.get(a.fic_id);
    grupo[a.formato] = a;
    if (a.fecha_descarga > grupo.fecha_descarga) grupo.fecha_descarga = a.fecha_descarga;
  }
  return [...porFic.values()].sort((a, b) => (a.fecha_descarga < b.fecha_descarga ? 1 : -1));
}

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

  async function borrar(a) {
    if (!confirm(t("archivo.confirmarBorrar", { titulo: a.fic_titulo }))) return;
    try {
      await api.archivos.remove(a.id);
      archivos.reload();
    } catch (err) {
      alert(err.message);
    }
  }

  const grupos = agruparPorFic(archivos.data);

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

      {grupos.length === 0 && <Vacio>{t("archivo.sinArchivos")}</Vacio>}

      <div className="arv-card">
        {grupos.map((g) => (
          <div className="arv-list-item" key={g.fic_id} style={{ alignItems: "flex-start" }}>
            <div>
              <div style={{ fontWeight: 600 }}>{g.fic_titulo}</div>
              <div className="arv-muted">
                {t("archivo.guardado", { fecha: new Date(g.fecha_descarga).toLocaleDateString(i18n.language) })}
              </div>
              <span
                className={`arv-tag ${g.fic_deleted_detected_at ? "arv-tag-accent" : "arv-tag-accent-2"}`}
                style={{ marginTop: 6, display: "inline-flex" }}
              >
                {g.fic_deleted_detected_at ? t("archivo.originalEliminado") : t("archivo.disponible")}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
              {g.html && (
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    className="arv-icon-btn"
                    onClick={() => abrirEnNavegadorExterno(api.archivos.contenidoUrl(g.html.id))}
                    aria-label={t("archivo.verCopia")}
                    title={t("archivo.verCopia")}
                  >
                    <Eye size={16} />
                  </button>
                  <button
                    className="arv-icon-btn"
                    onClick={() => descargarHtml(g.html)}
                    aria-label={t("archivo.descargar")}
                    title={t("archivo.descargar")}
                  >
                    <Download size={16} />
                  </button>
                  <button
                    className="arv-icon-btn"
                    onClick={() => borrar(g.html)}
                    aria-label={t("archivo.borrarCopia")}
                    title={t("archivo.borrarCopia")}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              )}
              {g.epub && (
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    className="arv-icon-btn"
                    onClick={() => abrirEnNavegadorExterno(api.archivos.contenidoUrl(g.epub.id))}
                    aria-label={t("archivo.descargarEpub")}
                    title={t("archivo.descargarEpub")}
                  >
                    <Download size={16} />
                  </button>
                  <button
                    className="arv-icon-btn"
                    onClick={() => borrar(g.epub)}
                    aria-label={t("archivo.borrarCopia")}
                    title={t("archivo.borrarCopia")}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
