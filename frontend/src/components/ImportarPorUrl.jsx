import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { InfoPopover } from "./InfoPopover";

export function ImportarPorUrl({ onImportado }) {
  const [url, setUrl] = useState("");
  const [estado, setEstado] = useState("idle"); // idle | cargando | error
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function importar() {
    if (!url.trim()) return;
    setEstado("cargando");
    setError(null);
    try {
      const fic = await api.ao3.importarPorUrl(url.trim());
      setUrl("");
      setEstado("idle");
      onImportado?.();
      navigate(`/fics/${fic.id}`);
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
          candado porque usa tu sesión conectada. Puede tardar ~10 segundos por el límite de
          velocidad de AO3.
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
          {estado === "cargando" ? "Importando…" : "Importar"}
        </button>
      </div>
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
    </div>
  );
}
