import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { InfoPopover } from "../components/InfoPopover";

export function Ao3() {
  const logs = useFetch(() => api.importLog.list(20));

  return (
    <div>
      <div className="arv-card">
        <h2 style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          Importar / conectar AO3
          <InfoPopover>
            Las importaciones se corren desde la terminal (<code>import bookmarks</code>,{" "}
            <code>import history</code>, <code>check-deleted</code>) porque pueden tardar horas
            por el límite de peticiones de AO3. Acá abajo se ve el historial de corridas.
          </InfoPopover>
        </h2>
      </div>

      {logs.loading && <Cargando />}
      {logs.error && <ErrorCarga error={logs.error} onReintentar={logs.reload} />}
      {logs.data?.length === 0 && <Vacio>Todavía no corriste ninguna importación.</Vacio>}

      <div className="arv-card">
        {logs.data?.map((log) => (
          <div className="arv-list-item" key={log.id} style={{ alignItems: "flex-start" }}>
            <div>
              <div style={{ fontWeight: 600 }}>{log.tipo}</div>
              <div className="arv-muted">{new Date(log.fecha).toLocaleString()}</div>
            </div>
            <div style={{ textAlign: "right" }} className="arv-muted">
              <div>+{log.fics_nuevos} nuevos · {log.fics_actualizados} actualizados</div>
              {log.errores > 0 && <div>{log.errores} errores</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
