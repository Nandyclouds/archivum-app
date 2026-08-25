import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { InfoPopover } from "./InfoPopover";

export function ImportarPorUrl() {
  const { t } = useTranslation();
  const [url, setUrl] = useState("");
  const [estado, setEstado] = useState("idle"); // idle | cargando | disparado | error
  const [error, setError] = useState(null);

  async function importar() {
    if (!url.trim()) return;
    setEstado("cargando");
    setError(null);
    try {
      await api.sync.trigger("fic", { url: url.trim() });
      setUrl("");
      setEstado("disparado");
    } catch (err) {
      setEstado("error");
      setError(err.message);
    }
  }

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {t("importarPorUrl.titulo")}
        <InfoPopover>{t("importarPorUrl.info")}</InfoPopover>
      </h3>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="arv-input"
          placeholder={t("importarPorUrl.placeholder")}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={estado === "cargando"}
        />
        <button className="arv-btn" disabled={estado === "cargando"} onClick={importar}>
          {estado === "cargando" ? t("importarPorUrl.disparando") : t("importarPorUrl.importar")}
        </button>
      </div>
      {estado === "disparado" && <p className="arv-muted">{t("importarPorUrl.enCamino")}</p>}
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
    </div>
  );
}
