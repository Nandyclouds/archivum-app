import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { InfoPopover } from "../components/InfoPopover";

export function Ao3() {
  const { t, i18n } = useTranslation();
  const logs = useFetch(() => api.importLog.list(20));

  return (
    <div>
      <div className="arv-card">
        <h2 style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          {t("ao3.titulo")}
          <InfoPopover>{t("ao3.info")}</InfoPopover>
        </h2>
      </div>

      <BotonSync modo="bookmarks" tituloKey="ao3.actualizarBookmarks" infoKey="ao3.actualizarBookmarksInfo" />
      <BotonSync modo="marcados" tituloKey="ao3.actualizarMarcados" infoKey="ao3.actualizarMarcadosInfo" />

      {logs.loading && <Cargando />}
      {logs.error && <ErrorCarga error={logs.error} onReintentar={logs.reload} />}
      {logs.data?.length === 0 && <Vacio>{t("ao3.sinCorridas")}</Vacio>}

      <div className="arv-card">
        {logs.data?.map((log) => (
          <div className="arv-list-item" key={log.id} style={{ alignItems: "flex-start" }}>
            <div>
              <div style={{ fontWeight: 600 }}>{log.tipo}</div>
              <div className="arv-muted">{new Date(log.fecha).toLocaleString(i18n.language)}</div>
            </div>
            <div style={{ textAlign: "right" }} className="arv-muted">
              <div>{t("ao3.nuevosYActualizados", { nuevos: log.fics_nuevos, actualizados: log.fics_actualizados })}</div>
              {log.errores > 0 && <div>{t("ao3.errores", { count: log.errores })}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BotonSync({ modo, tituloKey, infoKey }) {
  const { t } = useTranslation();
  const [estado, setEstado] = useState("idle"); // idle | disparando | disparado | error
  const [error, setError] = useState(null);

  async function disparar() {
    setEstado("disparando");
    setError(null);
    try {
      await api.sync.trigger(modo);
      setEstado("disparado");
    } catch (err) {
      setEstado("error");
      setError(err.message);
    }
  }

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {t(tituloKey)}
        <InfoPopover>{t(infoKey)}</InfoPopover>
      </h3>
      <button className="arv-btn" disabled={estado === "disparando"} onClick={disparar}>
        {estado === "disparando" ? t("ao3.disparando") : t("ao3.actualizarAhora")}
      </button>
      {estado === "disparado" && <p className="arv-muted">{t("ao3.syncEnCamino")}</p>}
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
    </div>
  );
}
