import { useState } from "react";
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
            Traer bookmarks nuevos corre en GitHub Actions (no en este server), porque puede
            tardar y este host no tiene salida directa a AO3. Abajo se ve el historial de
            corridas hechas desde la terminal de tu PC, si alguna vez usás esa vía.
          </InfoPopover>
        </h2>
      </div>

      <ActualizarBookmarks />

      {logs.loading && <Cargando />}
      {logs.error && <ErrorCarga error={logs.error} onReintentar={logs.reload} />}
      {logs.data?.length === 0 && <Vacio>Todavía no corriste ninguna importación desde la terminal.</Vacio>}

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

function ActualizarBookmarks() {
  const [estado, setEstado] = useState("idle"); // idle | disparando | disparado | error
  const [error, setError] = useState(null);

  async function disparar() {
    setEstado("disparando");
    setError(null);
    try {
      await api.sync.trigger("bookmarks");
      setEstado("disparado");
    } catch (err) {
      setEstado("error");
      setError(err.message);
    }
  }

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6 }}>
        Actualizar bookmarks
        <InfoPopover>
          Trae los bookmarks nuevos que agregaste en AO3 desde la última vez. Corre en GitHub
          Actions, así que no hace falta que tu PC esté prendida — puede tardar varios minutos
          (o más, si AO3 está limitando peticiones).
        </InfoPopover>
      </h3>
      <button className="arv-btn" disabled={estado === "disparando"} onClick={disparar}>
        {estado === "disparando" ? "Disparando…" : "Actualizar ahora"}
      </button>
      {estado === "disparado" && (
        <p className="arv-muted">
          Sync en camino — volvé a revisar tu biblioteca en un rato.
        </p>
      )}
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
    </div>
  );
}
