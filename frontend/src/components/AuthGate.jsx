import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Cargando } from "./EstadoCarga";
import { getToken, setToken } from "../lib/auth";
import { api } from "../lib/api";

function mensajeError(err) {
  return err.message.replace(/^\d+:\s*/, "");
}

export function AuthGate({ children }) {
  const { t } = useTranslation();
  // Sin token guardado todavía no sabemos si hace falta login real: si el
  // servidor corre sin ARCHIVUM_AUTH_TOKEN (uso local de una sola persona),
  // cualquier pedido pasa igual — /auth/yo lo confirma sin que haga falta
  // mostrar el formulario.
  const [estado, setEstado] = useState(() => (getToken() ? "desbloqueado" : "comprobando"));
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [codigoInvitacion, setCodigoInvitacion] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (estado !== "comprobando") return;
    api.auth
      .yo()
      .then(() => setEstado("desbloqueado"))
      .catch(() => setEstado("bloqueado"));
  }, [estado]);

  if (estado === "desbloqueado") return children;
  if (estado === "comprobando") return <Cargando />;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email.trim() || !password.trim() || (tab === "registro" && !codigoInvitacion.trim())) {
      setError(t("authGate.faltanDatos"));
      return;
    }
    setEnviando(true);
    setError("");
    try {
      const respuesta =
        tab === "login"
          ? await api.auth.login(email.trim(), password)
          : await api.auth.registro(email.trim(), password, codigoInvitacion.trim());
      setToken(respuesta.token);
      setEstado("desbloqueado");
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setEnviando(false);
    }
  }

  function cambiarTab(nuevoTab) {
    setTab(nuevoTab);
    setError("");
  }

  return (
    <div className="arv-app">
      <main className="arv-main" style={{ display: "flex", alignItems: "center", minHeight: "100vh" }}>
        <div className="arv-card" style={{ width: "100%" }}>
          <h2>Archivum</h2>

          <div className="arv-segmentado" style={{ margin: "16px 0" }}>
            <button className={tab === "login" ? "active" : ""} onClick={() => cambiarTab("login")} type="button">
              {t("authGate.tabLogin")}
            </button>
            <button className={tab === "registro" ? "active" : ""} onClick={() => cambiarTab("registro")} type="button">
              {t("authGate.tabRegistro")}
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <input
              className="arv-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("authGate.email")}
              autoFocus
              style={{ marginBottom: 12 }}
            />
            <input
              className="arv-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("authGate.password")}
              style={{ marginBottom: 12 }}
            />
            {tab === "registro" && (
              <input
                className="arv-input"
                type="text"
                value={codigoInvitacion}
                onChange={(e) => setCodigoInvitacion(e.target.value)}
                placeholder={t("authGate.codigoInvitacion")}
                style={{ marginBottom: 12 }}
              />
            )}
            {error && (
              <p style={{ color: "var(--color-accent)", fontSize: 13, marginBottom: 12 }}>{error}</p>
            )}
            <button className="arv-btn" type="submit" disabled={enviando}>
              {enviando
                ? t("authGate.verificando")
                : tab === "login"
                ? t("authGate.entrar")
                : t("authGate.crearCuenta")}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
