import { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { api } from "../lib/api";

// Pantalla que recibe el "Compartir" de Android (ver share_target en
// vite.config.js). Chrome manda la URL compartida en ?url=..., pero a veces
// (compartir texto seleccionado en vez del link de la barra) viene en
// ?text=... — probamos los dos.
export function Compartir() {
  const [params] = useSearchParams();
  const [estado, setEstado] = useState("cargando");
  const [error, setError] = useState(null);
  const [urlManual, setUrlManual] = useState("");
  const navigate = useNavigate();

  const urlCompartida = params.get("url") || extraerUrl(params.get("text")) || "";

  useEffect(() => {
    if (!urlCompartida) {
      setEstado("sin-url");
      return;
    }
    api.ao3
      .importarPorUrl(urlCompartida)
      .then((fic) => navigate(`/fics/${fic.id}`, { replace: true }))
      .catch((err) => {
        setEstado("error");
        setError(err.message);
      });
  }, [urlCompartida, navigate]);

  async function importarManual() {
    if (!urlManual.trim()) return;
    setEstado("cargando");
    setError(null);
    try {
      const fic = await api.ao3.importarPorUrl(urlManual.trim());
      navigate(`/fics/${fic.id}`, { replace: true });
    } catch (err) {
      setEstado("error");
      setError(err.message);
    }
  }

  if (estado === "cargando") {
    return (
      <div className="arv-card">
        <h3>Importando…</h3>
        <p className="arv-muted">Puede tardar ~10 segundos por el límite de velocidad de AO3.</p>
      </div>
    );
  }

  return (
    <div className="arv-card">
      <h3>{estado === "sin-url" ? "No encontré un link" : "Algo falló"}</h3>
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
      <p className="arv-muted">Pegalo acá:</p>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="arv-input"
          placeholder="https://archiveofourown.org/works/..."
          value={urlManual}
          onChange={(e) => setUrlManual(e.target.value)}
        />
        <button className="arv-btn" onClick={importarManual}>
          Importar
        </button>
      </div>
      <Link to="/" className="arv-muted" style={{ display: "block", marginTop: 12 }}>
        Volver al panel
      </Link>
    </div>
  );
}

function extraerUrl(texto) {
  if (!texto) return null;
  const match = texto.match(/https?:\/\/archiveofourown\.org\/works\/\d+[^\s]*/);
  return match ? match[0] : null;
}
