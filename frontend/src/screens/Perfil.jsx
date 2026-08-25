import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Pencil, User } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { cambiarIdioma } from "../i18n";
import { aplicarTema, aplicarColorAcento, obtenerTema, obtenerColorAcento } from "../lib/tema";

const PALETA_FAVORITOS = [
  { bg: "var(--color-text)", fg: "var(--color-surface)" },
  { bg: "var(--color-accent)", fg: "var(--color-surface)" },
  { bg: "var(--color-accent-2)", fg: "var(--color-surface)" },
  { bg: "var(--color-surface-2)", fg: "var(--color-text)" },
];

export function Perfil() {
  const { t } = useTranslation();
  const fics = useFetch(() => api.fics.list({ limit: 200, orden: "ultima_lectura" }));

  return (
    <div>
      <CabeceraPerfil />
      <Identidad />
      <Favoritos />
      <Graficos />
      <CitaFavorita />
      <Ajustes />

      <div className="arv-card">
        <h3>{t("perfil.historialDeLectura")}</h3>
        {fics.loading && <Cargando />}
        {fics.error && <ErrorCarga error={fics.error} onReintentar={fics.reload} />}
        {fics.data?.length === 0 && <Vacio>{t("perfil.sinFicsImportados")}</Vacio>}
        {fics.data?.map((f) => (
          <Link key={f.id} to={`/fics/${f.id}`} className="arv-fic-row">
            <div>
              <div className="fandom">{f.fandoms[0]?.nombre ?? t("common.sinFandom")}</div>
              <div className="titulo">{f.titulo}</div>
            </div>
            <div className="meta" style={{ textAlign: "right" }}>
              <div>{f.estado_actual ?? t("common.sinEstado")}</div>
              <div>
                {f.word_count.toLocaleString()} {t("common.palabras")}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function CabeceraPerfil() {
  const perfil = useFetch(() => api.perfil.get());
  const [version, setVersion] = useState(0);

  const conCache = (url) => `${url}${url.includes("?") ? "&" : "?"}v=${version}`;

  function onCambio() {
    setVersion((v) => v + 1);
    perfil.reload();
  }

  return (
    <div className="arv-perfil-header">
      <EditorFoto
        tipo="portada"
        tieneFoto={!!perfil.data?.tiene_portada}
        url={conCache(api.perfil.imagenUrl("portada"))}
        posicion={perfil.data?.portada_posicion ?? "50% 50%"}
        contenedorClassName="arv-perfil-portada"
        onCambio={onCambio}
      />
      <div className="arv-perfil-avatar-wrap">
        <EditorFoto
          tipo="avatar"
          tieneFoto={!!perfil.data?.tiene_avatar}
          url={conCache(api.perfil.imagenUrl("avatar"))}
          posicion={perfil.data?.avatar_posicion ?? "50% 50%"}
          contenedorClassName="arv-perfil-avatar"
          placeholder={<User size={32} />}
          onCambio={onCambio}
        />
      </div>
    </div>
  );
}

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n));
}

function parsePosicion(posicion) {
  const [x, y] = posicion.split(" ").map((v) => parseFloat(v));
  return [Number.isFinite(x) ? x : 50, Number.isFinite(y) ? y : 50];
}

function EditorFoto({ tipo, tieneFoto, url, posicion, contenedorClassName, placeholder, onCambio }) {
  const { t } = useTranslation();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [moviendo, setMoviendo] = useState(false);
  const [viendoGrande, setViendoGrande] = useState(false);
  const [posicionLocal, setPosicionLocal] = useState(posicion);
  const [guardandoPosicion, setGuardandoPosicion] = useState(false);
  const inputRef = useRef(null);
  const contenedorRef = useRef(null);
  const arrastre = useRef(null);

  useEffect(() => {
    if (!moviendo) setPosicionLocal(posicion);
  }, [posicion, moviendo]);

  function onPointerDown(e) {
    if (!moviendo) return;
    const rect = contenedorRef.current.getBoundingClientRect();
    const [x0, y0] = parsePosicion(posicionLocal);
    arrastre.current = { startX: e.clientX, startY: e.clientY, x0, y0, rect };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e) {
    if (!arrastre.current) return;
    const { startX, startY, x0, y0, rect } = arrastre.current;
    const nuevoX = clamp(x0 - ((e.clientX - startX) / rect.width) * 100, 0, 100);
    const nuevoY = clamp(y0 - ((e.clientY - startY) / rect.height) * 100, 0, 100);
    setPosicionLocal(`${nuevoX.toFixed(1)}% ${nuevoY.toFixed(1)}%`);
  }

  function onPointerUp() {
    arrastre.current = null;
  }

  async function guardarPosicion() {
    const [x, y] = parsePosicion(posicionLocal);
    setGuardandoPosicion(true);
    try {
      await api.perfil.actualizarPosicion(tipo, x, y);
      setMoviendo(false);
      onCambio();
    } catch (err) {
      alert(err.message);
    } finally {
      setGuardandoPosicion(false);
    }
  }

  function cancelarMovimiento() {
    setPosicionLocal(posicion);
    setMoviendo(false);
  }

  async function subir(archivo) {
    if (!archivo) return;
    try {
      await api.perfil.subirImagen(tipo, archivo);
      onCambio();
    } catch (err) {
      alert(err.message);
    }
  }

  return (
    <>
      <div
        ref={contenedorRef}
        className={contenedorClassName}
        style={{
          ...(tieneFoto ? { backgroundImage: `url(${url})`, backgroundPosition: posicionLocal } : {}),
          cursor: moviendo ? "grab" : "pointer",
          touchAction: moviendo ? "none" : "auto",
        }}
        onClick={() => !moviendo && setMenuAbierto(true)}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        {!tieneFoto && placeholder}
        {moviendo && <div className="arv-foto-mover-hint">{t("perfil.arrastraParaMover")}</div>}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(e) => subir(e.target.files[0])}
      />

      {menuAbierto && (
        <div className="arv-hoja-fondo" onClick={() => setMenuAbierto(false)}>
          <div className="arv-hoja" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => {
                inputRef.current.click();
                setMenuAbierto(false);
              }}
            >
              {t("perfil.cambiarFoto")}
            </button>
            {tieneFoto && (
              <button
                onClick={() => {
                  setMoviendo(true);
                  setMenuAbierto(false);
                }}
              >
                {t("perfil.moverFoto")}
              </button>
            )}
            {tieneFoto && (
              <button
                onClick={() => {
                  setViendoGrande(true);
                  setMenuAbierto(false);
                }}
              >
                {t("perfil.verEnGrande")}
              </button>
            )}
            <button className="cancelar" onClick={() => setMenuAbierto(false)}>
              {t("common.cancelar")}
            </button>
          </div>
        </div>
      )}

      {moviendo && (
        <div className="arv-foto-mover-acciones">
          <button className="arv-btn" disabled={guardandoPosicion} onClick={guardarPosicion}>
            {t("common.guardar")}
          </button>
          <button className="arv-btn arv-btn-secondary" onClick={cancelarMovimiento}>
            {t("common.cancelar")}
          </button>
        </div>
      )}

      {viendoGrande && (
        <div className="arv-foto-lightbox" onClick={() => setViendoGrande(false)}>
          <img src={url} alt="" />
        </div>
      )}
    </>
  );
}

function Identidad() {
  const { t } = useTranslation();
  const perfil = useFetch(() => api.perfil.get());
  const [editando, setEditando] = useState(false);
  const [nombreUsuario, setNombreUsuario] = useState("");
  const [bio, setBio] = useState("");
  const [guardando, setGuardando] = useState(false);

  function empezarEdicion() {
    setNombreUsuario(perfil.data?.nombre_usuario ?? "");
    setBio(perfil.data?.bio ?? "");
    setEditando(true);
  }

  async function guardar() {
    setGuardando(true);
    try {
      await api.perfil.actualizarIdentidad(nombreUsuario, bio);
      setEditando(false);
      perfil.reload();
    } catch (err) {
      alert(err.message);
    } finally {
      setGuardando(false);
    }
  }

  if (editando) {
    return (
      <div className="arv-card">
        <input
          className="arv-input"
          style={{ marginBottom: 8 }}
          placeholder={t("perfil.nombreUsuarioPlaceholder")}
          value={nombreUsuario}
          onChange={(e) => setNombreUsuario(e.target.value)}
          autoFocus
        />
        <textarea
          className="arv-input"
          style={{ resize: "vertical", minHeight: 60, marginBottom: 10 }}
          placeholder={t("perfil.bioPlaceholder")}
          value={bio}
          onChange={(e) => setBio(e.target.value)}
        />
        <div style={{ display: "flex", gap: 8 }}>
          <button className="arv-btn" disabled={guardando} onClick={guardar}>
            {t("common.guardar")}
          </button>
          <button className="arv-btn arv-btn-secondary" onClick={() => setEditando(false)}>
            {t("common.cancelar")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="arv-card" style={{ cursor: "pointer" }} onClick={empezarEdicion}>
      {perfil.data?.nombre_usuario ? (
        <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontStyle: "italic", fontSize: 26 }}>
          {perfil.data.nombre_usuario}
        </h2>
      ) : (
        <p className="arv-muted" style={{ margin: 0 }}>
          {t("perfil.agregarUsuario")}
        </p>
      )}
      {perfil.data?.bio && (
        <p
          className="arv-muted"
          style={{ marginBottom: 0, marginTop: 6, fontStyle: "italic", fontSize: 14.5, lineHeight: 1.5 }}
        >
          {perfil.data.bio}
        </p>
      )}
    </div>
  );
}

function Favoritos() {
  const { t } = useTranslation();
  const favoritos = useFetch(() => api.perfil.favoritos.list());
  const [buscando, setBuscando] = useState(false);
  const [q, setQ] = useState("");
  const resultados = useFetch(() => (q ? api.fics.list({ q, limit: 8 }) : Promise.resolve([])), [q]);
  const [eligiendo, setEligiendo] = useState(false);
  const [elegidos, setElegidos] = useState([]);
  const [guardandoDestacados, setGuardandoDestacados] = useState(false);

  function empezarAElegir() {
    setElegidos(favoritos.data?.destacados_ids ?? []);
    setEligiendo(true);
  }

  function alternarElegido(ficId) {
    setElegidos((prev) => {
      if (prev.includes(ficId)) return prev.filter((id) => id !== ficId);
      if (prev.length >= 4) return prev;
      return [...prev, ficId];
    });
  }

  async function guardarDestacados() {
    setGuardandoDestacados(true);
    try {
      await api.perfil.favoritos.setDestacados(elegidos);
      setEligiendo(false);
      favoritos.reload();
    } catch (err) {
      alert(err.message);
    } finally {
      setGuardandoDestacados(false);
    }
  }

  async function agregar(ficId) {
    try {
      await api.perfil.favoritos.add(ficId);
      setBuscando(false);
      setQ("");
      favoritos.reload();
    } catch (err) {
      alert(err.message);
    }
  }

  async function quitar(e, ficId) {
    e.preventDefault();
    await api.perfil.favoritos.remove(ficId);
    favoritos.reload();
  }

  const lista = favoritos.data?.fics ?? [];
  const total = favoritos.data?.total ?? 0;
  const coleccionId = favoritos.data?.coleccion_id;

  return (
    <div className="arv-card">
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 10 }}>
        <h3 style={{ marginBottom: 0 }}>{t("perfil.favoritos")}</h3>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {total > 4 && !eligiendo && (
            <button
              onClick={empezarAElegir}
              className="arv-muted"
              aria-label={t("perfil.elegirDestacados")}
              style={{
                border: "none",
                background: "transparent",
                cursor: "pointer",
                padding: 0,
                display: "flex",
                alignItems: "center",
              }}
            >
              <Pencil size={13} />
            </button>
          )}
          {coleccionId && total > 4 && (
            <Link to={`/colecciones/${coleccionId}`} className="arv-muted" style={{ fontSize: 12.5 }}>
              {t("perfil.verLos", { count: total })}
            </Link>
          )}
        </div>
      </div>

      {favoritos.error && (
        <div style={{ marginBottom: 12 }}>
          <p className="arv-muted" style={{ marginBottom: 8 }}>
            {t("common.errorApi", { msg: favoritos.error.message })}
          </p>
          <button className="arv-btn arv-btn-secondary" onClick={favoritos.reload}>
            {t("common.reintentar")}
          </button>
        </div>
      )}

      {!favoritos.error && eligiendo ? (
        <div>
          <div style={{ maxHeight: 260, overflowY: "auto", marginBottom: 10 }}>
            {(favoritos.data?.todos ?? []).map((f) => {
              const elegido = elegidos.includes(f.fic_id);
              return (
                <div
                  key={f.fic_id}
                  className="arv-list-item arv-destacado-opcion"
                  onClick={() => alternarElegido(f.fic_id)}
                  style={elegido ? { background: "var(--color-accent-soft)" } : undefined}
                >
                  <span style={elegido ? { color: "var(--color-accent)", fontWeight: 700 } : undefined}>
                    {f.titulo}
                  </span>
                  {elegido && <span style={{ color: "var(--color-accent)" }}>✓</span>}
                </div>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="arv-btn" disabled={guardandoDestacados} onClick={guardarDestacados}>
              {t("common.guardar")}
            </button>
            <button className="arv-btn arv-btn-secondary" onClick={() => setEligiendo(false)}>
              {t("common.cancelar")}
            </button>
          </div>
        </div>
      ) : (
      <>
      <div className="arv-favoritos-grid">
        {lista.map((f, i) => (
          <Link
            key={f.fic_id}
            to={`/fics/${f.fic_id}`}
            className="arv-favorito-card"
            style={{ background: PALETA_FAVORITOS[i % 4].bg, color: PALETA_FAVORITOS[i % 4].fg }}
          >
            <span>{f.titulo}</span>
            <button
              className="arv-favorito-quitar"
              onClick={(e) => quitar(e, f.fic_id)}
              aria-label={t("perfil.quitarDeFavoritos")}
            >
              ×
            </button>
          </Link>
        ))}
        {lista.length < 4 && (
          <div className="arv-favorito-add" onClick={() => setBuscando(true)}>
            +
          </div>
        )}
      </div>
      {buscando && (
        <div style={{ marginTop: 12 }}>
          <input
            className="arv-input"
            placeholder={t("perfil.buscarFicPlaceholder")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            autoFocus
          />
          {resultados.data?.map((fic) => (
            <div
              key={fic.id}
              className="arv-list-item"
              style={{ cursor: "pointer" }}
              onClick={() => agregar(fic.id)}
            >
              <span>{fic.titulo}</span>
            </div>
          ))}
          {q && resultados.data?.length === 0 && <p className="arv-muted">{t("perfil.sinResultados")}</p>}
        </div>
      )}
      </>
      )}
    </div>
  );
}

function GraficoAnios({ datos }) {
  if (!datos || datos.length === 0) return null;
  const W = 320;
  const H = 96;
  const max = Math.max(...datos.map((d) => d.palabras), 1);
  const n = datos.length;
  const puntos = datos.map((d, i) => ({
    x: n === 1 ? W / 2 : (i / (n - 1)) * (W - 8) + 4,
    y: H - 4 - (d.palabras / max) * (H - 10),
  }));
  const linea = puntos.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  const area = `${linea} L ${puntos[n - 1].x.toFixed(1)} ${H} L ${puntos[0].x.toFixed(1)} ${H} Z`;
  const ultimo = puntos[n - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: 96, display: "block", overflow: "visible" }}>
      <defs>
        <linearGradient id="arv-graf-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--color-accent)" stopOpacity="0.25" />
          <stop offset="1" stopColor="var(--color-accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#arv-graf-fill)" />
      <path d={linea} fill="none" stroke="var(--color-accent)" strokeWidth="2.5" strokeLinecap="round" />
      {puntos.slice(0, -1).map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="3" fill="var(--color-accent-soft)" />
      ))}
      <circle cx={ultimo.x} cy={ultimo.y} r="5" fill="var(--color-accent)" stroke="var(--color-surface)" strokeWidth="2.5" />
    </svg>
  );
}

function BubbleLongitud({ datos }) {
  const { t } = useTranslation();
  if (!datos) return null;
  const MAX_D = 108;
  const MIN_D = 20;
  const max = Math.max(...datos.map((d) => d.total), 1);
  return (
    <>
      <div className="arv-bubble-row">
        {datos.map(({ bucket, total }) => {
          const d = Math.max(MIN_D, Math.sqrt(total / max) * MAX_D);
          return (
            <div key={bucket} className="arv-bubble" style={{ width: d, height: d }}>
              <span className="numero" style={{ fontSize: Math.max(11, d * 0.26) }}>
                {total}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "center", gap: 14, flexWrap: "wrap" }}>
        {datos.map(({ bucket }) => (
          <span key={bucket} className="arv-muted" style={{ fontSize: 10.5 }}>
            {t(`perfil.bucketLabelCorto.${bucket}`, { defaultValue: bucket })}
          </span>
        ))}
      </div>
    </>
  );
}

function Graficos() {
  const { t } = useTranslation();
  const porAnio = useFetch(() => api.stats.palabrasPorAnio());
  const longitud = useFetch(() => api.stats.distribucionLongitud());
  const wipCompletos = useFetch(() => api.stats.ratioWipCompletos());
  const resumen = useFetch(() => api.stats.resumen());

  const ultimoAnio = porAnio.data?.[porAnio.data.length - 1];
  const completos = wipCompletos.data?.completos ?? 0;
  const wip = wipCompletos.data?.wip ?? 0;
  const totalCompletosWip = completos + wip;
  const pctCompletos = totalCompletosWip > 0 ? Math.round((completos / totalCompletosWip) * 100) : 0;

  return (
    <div className="arv-card">
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <h3 style={{ marginBottom: 2 }}>{t("perfil.graficos")}</h3>
      </div>

      {porAnio.loading && <Cargando />}
      {ultimoAnio && (
        <>
          <div className="arv-graf-hero">
            <span className="numero">{formatoCompacto(ultimoAnio.palabras)}</span>
            <span className="etiqueta">{t("perfil.palabrasEnAnio", { anio: ultimoAnio.periodo })}</span>
          </div>
          <GraficoAnios datos={porAnio.data} />
          <div className="arv-graf-anio-labels">
            {porAnio.data.map((p) => (
              <Link key={p.periodo} to={`/panel/top/palabras?anio=${p.periodo}`}>
                {p.periodo}
              </Link>
            ))}
          </div>
        </>
      )}
      {porAnio.data?.length === 0 && <p className="arv-muted">{t("perfil.sinDatosTodavia")}</p>}

      <div className="arv-graf-divider">
        <span>{t("perfil.distribucionPorLongitud")}</span>
        <span className="line" />
      </div>
      {longitud.loading && <Cargando />}
      <BubbleLongitud datos={longitud.data} />

      <div className="arv-graf-divider">
        <span>{t("perfil.completosVsWip")}</span>
        <span className="line" />
      </div>
      {wipCompletos.data && totalCompletosWip > 0 && (
        <div className="arv-donut-fila">
          <div className="arv-donut-wrap">
            <div
              className="arv-donut"
              style={{
                background: `conic-gradient(var(--color-accent) 0 ${pctCompletos}%, var(--color-accent-2-soft) ${pctCompletos}% 100%)`,
              }}
            >
              <div className="arv-donut-inner">
                <span className="numero">{pctCompletos}%</span>
                <span className="etiqueta">{t("perfil.completos")}</span>
              </div>
            </div>
            <div className="arv-donut-legend">
              <span>
                <i style={{ background: "var(--color-accent)" }} />
                {completos}
              </span>
              <span>
                <i style={{ background: "var(--color-accent-2-soft)" }} />
                {wip} {t("perfil.wip")}
              </span>
            </div>
          </div>
          {resumen.data && (
            <div className="arv-racha-card">
              <span className="etiqueta">
                {t("perfil.rachaDeLectura")}
                <br />
                {t("perfil.lectura")}
              </span>
              <div>
                <div className="numero">{resumen.data.racha_dias}</div>
                <div className="sub">
                  {resumen.data.racha_dias === 1 ? t("perfil.diaSeguido") : t("perfil.diasSeguidos")}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CitaFavorita() {
  const { t } = useTranslation();
  const perfil = useFetch(() => api.perfil.get());
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState("");
  const [fuente, setFuente] = useState("");

  function empezarEdicion() {
    setTexto(perfil.data?.cita_texto ?? "");
    setFuente(perfil.data?.cita_fuente ?? "");
    setEditando(true);
  }

  async function guardar() {
    try {
      await api.perfil.actualizarCita(texto, fuente);
      setEditando(false);
      perfil.reload();
    } catch (err) {
      alert(err.message);
    }
  }

  if (editando) {
    return (
      <div className="arv-card">
        <h3>{t("perfil.citaFavorita")}</h3>
        <textarea
          className="arv-input"
          style={{ resize: "vertical", minHeight: 70, marginBottom: 8 }}
          placeholder={t("perfil.citaPlaceholder")}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
        <input
          className="arv-input"
          style={{ marginBottom: 10 }}
          placeholder={t("perfil.fuentePlaceholder")}
          value={fuente}
          onChange={(e) => setFuente(e.target.value)}
        />
        <div style={{ display: "flex", gap: 8 }}>
          <button className="arv-btn" onClick={guardar}>
            {t("common.guardar")}
          </button>
          <button className="arv-btn arv-btn-secondary" onClick={() => setEditando(false)}>
            {t("common.cancelar")}
          </button>
        </div>
      </div>
    );
  }

  if (!perfil.data?.cita_texto) {
    return (
      <div className="arv-card">
        <h3>{t("perfil.citaFavorita")}</h3>
        <p className="arv-muted" style={{ marginBottom: 10 }}>
          {t("perfil.sinCita")}
        </p>
        <button className="arv-btn arv-btn-secondary" onClick={empezarEdicion}>
          {t("perfil.agregarCita")}
        </button>
      </div>
    );
  }

  return (
    <div className="arv-cita-card" style={{ marginBottom: 14, cursor: "pointer" }} onClick={empezarEdicion}>
      <span className="etiqueta">{t("perfil.citaFavoritaEtiqueta")}</span>
      <p>“{perfil.data.cita_texto}”</p>
      {perfil.data.cita_fuente && <span className="fuente">{t("perfil.de", { fuente: perfil.data.cita_fuente })}</span>}
    </div>
  );
}

function Ajustes() {
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
          <button
            className={i18n.language === "es" ? "active" : ""}
            onClick={() => cambiarIdioma("es")}
          >
            {t("perfil.espanol")}
          </button>
          <button
            className={i18n.language === "en" ? "active" : ""}
            onClick={() => cambiarIdioma("en")}
          >
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

function formatoCompacto(numero) {
  if (numero >= 1_000_000) return `${(numero / 1_000_000).toFixed(1)}M`;
  if (numero >= 1_000) return `${(numero / 1_000).toFixed(0)}k`;
  return String(numero);
}
