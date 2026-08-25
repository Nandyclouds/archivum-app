import { useState } from "react";
import { useTranslation } from "react-i18next";
import { getToken, setToken } from "../lib/auth";
import { api } from "../lib/api";

export function AuthGate({ children }) {
  const { t } = useTranslation();
  const [desbloqueado, setDesbloqueado] = useState(() => !!getToken());
  const [valor, setValor] = useState("");
  const [error, setError] = useState("");
  const [verificando, setVerificando] = useState(false);

  if (desbloqueado) return children;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!valor.trim()) {
      setError(t("authGate.faltaCodigo"));
      return;
    }
    setVerificando(true);
    setError("");
    setToken(valor.trim());
    try {
      await api.stats.resumen();
      setDesbloqueado(true);
    } catch (err) {
      setError(t("authGate.codigoIncorrecto"));
      setToken("");
    } finally {
      setVerificando(false);
    }
  }

  return (
    <div className="arv-app">
      <main className="arv-main" style={{ display: "flex", alignItems: "center", minHeight: "100vh" }}>
        <div className="arv-card" style={{ width: "100%" }}>
          <h2>Archivum</h2>
          <p className="arv-muted" style={{ marginBottom: 16 }}>
            {t("authGate.subtitulo")}
          </p>
          <form onSubmit={handleSubmit}>
            <input
              className="arv-input"
              type="password"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              placeholder={t("authGate.placeholder")}
              autoFocus
              style={{ marginBottom: 12 }}
            />
            {error && (
              <p style={{ color: "var(--color-accent)", fontSize: 13, marginBottom: 12 }}>{error}</p>
            )}
            <button className="arv-btn" type="submit" disabled={verificando}>
              {verificando ? t("authGate.verificando") : t("authGate.entrar")}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
