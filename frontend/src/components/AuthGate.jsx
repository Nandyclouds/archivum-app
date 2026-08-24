import { useState } from "react";
import { getToken, setToken } from "../lib/auth";
import { api } from "../lib/api";

export function AuthGate({ children }) {
  const [desbloqueado, setDesbloqueado] = useState(() => !!getToken());
  const [valor, setValor] = useState("");
  const [error, setError] = useState("");
  const [verificando, setVerificando] = useState(false);

  if (desbloqueado) return children;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!valor.trim()) {
      setError("Ingresá el código de acceso.");
      return;
    }
    setVerificando(true);
    setError("");
    setToken(valor.trim());
    try {
      await api.stats.resumen();
      setDesbloqueado(true);
    } catch (err) {
      setError("Código incorrecto.");
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
            Ingresá el código de acceso para entrar.
          </p>
          <form onSubmit={handleSubmit}>
            <input
              className="arv-input"
              type="password"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              placeholder="Código de acceso"
              autoFocus
              style={{ marginBottom: 12 }}
            />
            {error && (
              <p style={{ color: "var(--color-accent)", fontSize: 13, marginBottom: 12 }}>{error}</p>
            )}
            <button className="arv-btn" type="submit" disabled={verificando}>
              {verificando ? "Verificando..." : "Entrar"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
