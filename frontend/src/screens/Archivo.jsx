import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { abrirEnNavegadorExterno } from "../lib/abrirExterno";
import { InfoPopover } from "../components/InfoPopover";

const FORMATO_LABEL = { html: "Ver copia", epub: "Descargar EPUB" };

export function Archivo() {
  const archivos = useFetch(() => api.archivos.list());

  if (archivos.loading) return <Cargando />;
  if (archivos.error) return <ErrorCarga error={archivos.error} onReintentar={archivos.reload} />;

  return (
    <div>
      <div className="arv-card">
        <h2 style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          Archivo tipo Wayback Machine
          <InfoPopover>
            Copia HTML guardada automáticamente al importar cada fic, por si el original
            desaparece. El EPUB es aparte y hay que pedirlo (botón en cada fic, o{" "}
            <code>download --all-unarchived</code> desde la terminal).
          </InfoPopover>
        </h2>
      </div>

      {archivos.data.length === 0 && <Vacio>Todavía no hay nada archivado.</Vacio>}

      <div className="arv-card">
        {archivos.data.map((a) => (
          <div className="arv-list-item" key={a.id}>
            <div>
              <div style={{ fontWeight: 600 }}>{a.fic_titulo}</div>
              <div className="arv-muted">
                guardado {new Date(a.fecha_descarga).toLocaleDateString()}
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "stretch", gap: 6 }}>
              <span
                className={`arv-tag ${a.fic_deleted_detected_at ? "arv-tag-accent" : "arv-tag-accent-2"}`}
                style={{ justifyContent: "center" }}
              >
                {a.fic_deleted_detected_at ? "Original eliminado" : "Disponible"}
              </span>
              <button
                className="arv-btn arv-btn-secondary"
                onClick={() => abrirEnNavegadorExterno(api.archivos.contenidoUrl(a.id))}
              >
                {FORMATO_LABEL[a.formato] ?? a.formato}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
