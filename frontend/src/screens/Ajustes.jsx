import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Trash2 } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { InfoPopover } from "../components/InfoPopover";
import { useEmojisPersonalizados } from "../lib/EmojiPersonalizadoContext";
import { cambiarIdioma } from "../i18n";
import { aplicarTema, aplicarColorAcento, obtenerTema, obtenerColorAcento } from "../lib/tema";

export function Ajustes() {
  return (
    <div>
      <Preferencias />
      <EmojisPersonalizados />
      <GifsPersonalizados />
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
