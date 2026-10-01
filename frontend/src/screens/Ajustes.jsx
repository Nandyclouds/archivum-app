import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Copy, Trash2 } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { InfoPopover } from "../components/InfoPopover";
import { useEmojisPersonalizados } from "../lib/EmojiPersonalizadoContext";
import { cambiarIdioma } from "../i18n";
import { clearToken } from "../lib/auth";
import { aplicarTema, aplicarColorAcento, obtenerTema, obtenerColorAcento } from "../lib/tema";

export function Ajustes() {
  return (
    <div>
      <Preferencias />
      <EmojisPersonalizados />
      <GifsPersonalizados />
      <CredencialesAo3 />
      <InvitacionesAdmin />
      <CuentaActual />
    </div>
  );
}

function Preferencias() {
  const { t, i18n } = useTranslation();
  const [tema, setTema] = useState(obtenerTema());
  const [color, setColor] = useState(obtenerColorAcento());
  const [textoColor, setTextoColor] = useState(obtenerColorAcento());

  function cambiarTema(valor) {
    aplicarTema(valor);
    setTema(valor);
    setColor(obtenerColorAcento());
    setTextoColor(obtenerColorAcento());
  }

  function cambiarColor(hex) {
    aplicarColorAcento(hex);
    setColor(hex);
    setTextoColor(hex);
  }

  function cambiarTextoColor(valor) {
    setTextoColor(valor);
    const hex = valor.startsWith("#") ? valor : `#${valor}`;
    if (/^#[0-9a-fA-F]{6}$/.test(hex)) cambiarColor(hex);
  }

  return (
    <div className="arv-card">
      <h3>{t("perfil.ajustes")}</h3>

      <div className="arv-ajustes-fila">
        <span className="arv-ajustes-label">{t("perfil.idioma")}</span>
        <div className="arv-segmentado">
          <button className={i18n.language === "es" ? "active" : ""} onClick={() => cambiarIdioma("es")}>
            {t("perfil.espanol")}
          </button>
          <button className={i18n.language === "en" ? "active" : ""} onClick={() => cambiarIdioma("en")}>
            {t("perfil.ingles")}
          </button>
        </div>
      </div>

      <div className="arv-ajustes-fila">
        <span className="arv-ajustes-label">{t("perfil.tema")}</span>
        <div className="arv-segmentado">
          <button className={tema === "light" ? "active" : ""} onClick={() => cambiarTema("light")}>
            {t("perfil.temaClaro")}
          </button>
          <button className={tema === "dark" ? "active" : ""} onClick={() => cambiarTema("dark")}>
            {t("perfil.temaOscuro")}
          </button>
        </div>
      </div>

      <div className="arv-ajustes-fila">
        <span className="arv-ajustes-label">{t("perfil.colorDeAcento")}</span>
        <div className="arv-color-picker">
          <input
            type="text"
            className="arv-color-hex"
            value={textoColor}
            onChange={(e) => cambiarTextoColor(e.target.value)}
            onBlur={() => setTextoColor(color)}
            maxLength={7}
            spellCheck={false}
            aria-label={t("perfil.colorDeAcento")}
          />
          <input
            type="color"
            className="arv-color-swatch"
            value={color}
            onChange={(e) => cambiarColor(e.target.value)}
            aria-label={t("perfil.colorDeAcento")}
          />
        </div>
      </div>
    </div>
  );
}

function EmojisPersonalizados() {
  const { t } = useTranslation();
  const { lista, recargar } = useEmojisPersonalizados();
  const [nombre, setNombre] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState("");
  const inputArchivoRef = useRef(null);

  async function subir() {
    if (!nombre.trim() || !archivo) return;
    setSubiendo(true);
    setError("");
    try {
      await api.emojis.create(nombre.trim().toLowerCase(), archivo);
      setNombre("");
      setArchivo(null);
      if (inputArchivoRef.current) inputArchivoRef.current.value = "";
      recargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubiendo(false);
    }
  }

  async function borrar(id) {
    await api.emojis.remove(id);
    recargar();
  }

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14 }}>
        {t("perfil.emojisPersonalizados")}
        <InfoPopover>{t("perfil.emojisPersonalizadosInfo")}</InfoPopover>
      </h3>

      {lista.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
          {lista.map((e) => (
            <div
              key={e.id}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, width: 60 }}
            >
              <img
                src={api.emojis.imagenUrl(e.id)}
                alt={e.nombre}
                style={{ width: 36, height: 36, objectFit: "contain" }}
              />
              <span className="arv-muted" style={{ fontSize: 10, textAlign: "center", wordBreak: "break-all" }}>
                :{e.nombre}:
              </span>
              <button
                onClick={() => borrar(e.id)}
                aria-label={t("perfil.borrarEmoji", { nombre: e.nombre })}
                style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--color-text-muted)", padding: 0 }}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          ref={inputArchivoRef}
          type="file"
          accept="image/png,image/webp,image/gif,image/jpeg,image/svg+xml"
          onChange={(e) => setArchivo(e.target.files[0] ?? null)}
          style={{ flex: "1 1 160px", minWidth: 0 }}
        />
        <input
          className="arv-input"
          style={{ flex: "1 1 140px", minWidth: 0 }}
          placeholder={t("perfil.nombreEmojiPlaceholder")}
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
        />
        <button className="arv-btn arv-btn-secondary" disabled={subiendo || !nombre.trim() || !archivo} onClick={subir}>
          {subiendo ? t("perfil.subiendoEmoji") : t("perfil.subirEmoji")}
        </button>
      </div>
      {error && <p style={{ color: "var(--color-accent)", fontSize: 13, marginTop: 8 }}>{error}</p>}
    </div>
  );
}

function GifsPersonalizados() {
  const { t } = useTranslation();
  const perfil = useFetch(() => api.perfil.get(), [], "perfil-datos");
  const [subiendoIndice, setSubiendoIndice] = useState(null);
  const [error, setError] = useState("");

  async function subir(indice, archivo) {
    if (!archivo) return;
    setSubiendoIndice(indice);
    setError("");
    try {
      await api.perfil.subirGif(indice, archivo);
      perfil.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubiendoIndice(null);
    }
  }

  async function borrar(indice) {
    await api.perfil.borrarGif(indice);
    perfil.reload();
  }

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14 }}>
        {t("perfil.gifsPersonalizados")}
        <InfoPopover>{t("perfil.gifsPersonalizadosInfo")}</InfoPopover>
      </h3>

      <div style={{ display: "flex", gap: 14 }}>
        {[1, 2, 3].map((i) => {
          const tiene = !!perfil.data?.[`tiene_gif${i}`];
          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <div className="arv-gif-slot">
                {tiene ? (
                  <img src={api.perfil.imagenUrl(`gif${i}`)} alt="" />
                ) : (
                  <span className="arv-muted">{i}</span>
                )}
              </div>
              <label className="arv-btn arv-btn-secondary arv-btn-compacto" style={{ cursor: "pointer" }}>
                {subiendoIndice === i ? t("perfil.subiendoEmoji") : t(tiene ? "perfil.cambiarGif" : "perfil.subirGifBtn")}
                <input
                  type="file"
                  accept="image/gif,image/webp"
                  hidden
                  onChange={(e) => subir(i, e.target.files[0])}
                />
              </label>
              {tiene && (
                <button
                  onClick={() => borrar(i)}
                  aria-label={t("perfil.borrarGif", { n: i })}
                  style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--color-text-muted)", padding: 0 }}
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          );
        })}
      </div>
      {error && <p style={{ color: "var(--color-accent)", fontSize: 13, marginTop: 8 }}>{error}</p>}
    </div>
  );
}

function InvitacionesAdmin() {
  const { t } = useTranslation();
  const yo = useFetch(() => api.auth.yo(), [], "auth-yo");
  const invitaciones = useFetch(() => api.auth.invitaciones.list(), [], "auth-invitaciones");
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState("");
  const [copiado, setCopiado] = useState(null);

  if (!yo.data?.es_admin) return null;

  async function generar() {
    setGenerando(true);
    setError("");
    try {
      await api.auth.invitaciones.create();
      invitaciones.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerando(false);
    }
  }

  async function copiar(codigo) {
    await navigator.clipboard.writeText(codigo);
    setCopiado(codigo);
    setTimeout(() => setCopiado(null), 1500);
  }

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14 }}>
        {t("perfil.invitaciones")}
        <InfoPopover>{t("perfil.invitacionesInfo")}</InfoPopover>
      </h3>

      <button className="arv-btn arv-btn-secondary" disabled={generando} onClick={generar} style={{ marginBottom: 14 }}>
        {generando ? t("perfil.generando") : t("perfil.generarInvitacion")}
      </button>
      {error && <p style={{ color: "var(--color-accent)", fontSize: 13, marginBottom: 12 }}>{error}</p>}

      {(invitaciones.data ?? []).length === 0 ? (
        <p className="arv-muted">{t("perfil.sinInvitaciones")}</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {invitaciones.data.map((inv) => (
            <div
              key={inv.codigo}
              style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}
            >
              <code style={{ background: "var(--color-surface-alt)", padding: "2px 6px", borderRadius: 4 }}>
                {inv.codigo}
              </code>
              <span className="arv-muted">
                {inv.usada ? t("perfil.invitacionUsadaPor", { email: inv.usada_por_email }) : t("perfil.invitacionSinUsar")}
              </span>
              {!inv.usada && (
                <button
                  onClick={() => copiar(inv.codigo)}
                  aria-label={t("perfil.copiarCodigo")}
                  style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--color-text-muted)", padding: 0, display: "flex", alignItems: "center", gap: 4 }}
                >
                  <Copy size={13} />
                  {copiado === inv.codigo && t("perfil.codigoCopiado")}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CredencialesAo3() {
  const { t } = useTranslation();
  const yo = useFetch(() => api.auth.yo(), [], "auth-yo");
  const [usuario, setUsuario] = useState("");
  const [password, setPassword] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  async function guardar() {
    if (!usuario.trim() || !password) return;
    setGuardando(true);
    setError("");
    try {
      await api.auth.ao3Credenciales.actualizar(usuario.trim(), password);
      setUsuario("");
      setPassword("");
      yo.reload();
    } catch (err) {
      setError(err.message.replace(/^\d+:\s*/, ""));
    } finally {
      setGuardando(false);
    }
  }

  async function desconectar() {
    await api.auth.ao3Credenciales.borrar();
    yo.reload();
  }

  if (!yo.data) return null;

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14 }}>
        {t("perfil.credencialesAo3")}
        <InfoPopover>{t("perfil.credencialesAo3Info")}</InfoPopover>
      </h3>

      <p className="arv-muted" style={{ marginBottom: 14 }}>
        {yo.data.ao3_username
          ? t("perfil.ao3ConectadoComo", { usuario: yo.data.ao3_username })
          : t("perfil.ao3SinConectar")}
      </p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <input
          className="arv-input"
          style={{ flex: "1 1 160px", minWidth: 0 }}
          placeholder={t("perfil.ao3UsuarioPlaceholder")}
          value={usuario}
          onChange={(e) => setUsuario(e.target.value)}
        />
        <input
          className="arv-input"
          type="password"
          style={{ flex: "1 1 160px", minWidth: 0 }}
          placeholder={t("perfil.ao3PasswordPlaceholder")}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="arv-btn arv-btn-secondary"
          disabled={guardando || !usuario.trim() || !password}
          onClick={guardar}
        >
          {guardando ? t("common.guardando") : t("common.guardar")}
        </button>
        {yo.data.ao3_username && (
          <button className="arv-btn arv-btn-secondary" onClick={desconectar}>
            {t("perfil.desconectarAo3")}
          </button>
        )}
      </div>
      {error && <p style={{ color: "var(--color-accent)", fontSize: 13, marginTop: 8 }}>{error}</p>}
    </div>
  );
}

function CuentaActual() {
  const { t } = useTranslation();
  const yo = useFetch(() => api.auth.yo(), [], "auth-yo");

  async function salir() {
    try {
      await api.auth.logout();
    } catch {
      // si el token ya no servía esto también falla, pero igual queremos limpiar y recargar
    }
    clearToken();
    window.location.reload();
  }

  if (!yo.data) return null;

  return (
    <div className="arv-card">
      <h3 style={{ marginBottom: 14 }}>{t("perfil.cuenta")}</h3>
      <p className="arv-muted" style={{ marginBottom: 14 }}>
        {yo.data.email}
      </p>
      <button className="arv-btn arv-btn-secondary" onClick={salir}>
        {t("perfil.cerrarSesion")}
      </button>
    </div>
  );
}
