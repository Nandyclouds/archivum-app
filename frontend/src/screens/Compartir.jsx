import { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";

// Pantalla que recibe el "Compartir" de Android (ver share_target en
// vite.config.js). Chrome manda la URL compartida en ?url=..., pero a veces
// (compartir texto seleccionado en vez del link de la barra) viene en
// ?text=... — probamos los dos.
export function Compartir() {
  const { t } = useTranslation();
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
        <h3>{t("compartir.importando")}</h3>
        <p className="arv-muted">{t("compartir.esperaLimite")}</p>
      </div>
    );
  }

  return (
    <div className="arv-card">
      <h3>{estado === "sin-url" ? t("compartir.sinLink") : t("compartir.algoFallo")}</h3>
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
      <p className="arv-muted">{t("compartir.pegaloAca")}</p>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="arv-input"
          placeholder={t("importarPorUrl.placeholder")}
          value={urlManual}
          onChange={(e) => setUrlManual(e.target.value)}
        />
        <button className="arv-btn" onClick={importarManual}>
          {t("compartir.importar")}
        </button>
      </div>
      <Link to="/" className="arv-muted" style={{ display: "block", marginTop: 12 }}>
        {t("compartir.volverAlPanel")}
      </Link>
    </div>
  );
}

function extraerUrl(texto) {
  if (!texto) return null;
  const match = texto.match(/https?:\/\/archiveofourown\.org\/works\/\d+[^\s]*/);
  return match ? match[0] : null;
}
