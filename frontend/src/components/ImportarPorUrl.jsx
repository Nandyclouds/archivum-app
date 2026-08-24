import { useState } from "react";
import { api } from "../lib/api";
import { InfoPopover } from "./InfoPopover";

export function ImportarPorUrl() {
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
        Importar por link
        <InfoPopover>
          Pegá la URL de un fic de AO3 y se agrega a tu biblioteca. Funciona con fics con
          candado porque usa tu sesión conectada. El import corre en GitHub Actions (no en este
          server), así que tarda entre uno y varios minutos — no aparece al toque.
        </InfoPopover>
      </h3>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="arv-input"
          placeholder="https://archiveofourown.org/works/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={estado === "cargando"}
        />
        <button className="arv-btn" disabled={estado === "cargando"} onClick={importar}>
          {estado === "cargando" ? "Disparando…" : "Importar"}
        </button>
      </div>
      {estado === "disparado" && (
        <p className="arv-muted">Import en camino — puede tardar unos minutos en aparecer.</p>
      )}
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
    </div>
  );
}
