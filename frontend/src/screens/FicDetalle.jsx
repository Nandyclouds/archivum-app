import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Droplet, Check } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga } from "../components/EstadoCarga";
import { Estrellas } from "../components/Estrellas";
import { EstrellasInput } from "../components/EstrellasInput";
import { InfoPopover } from "../components/InfoPopover";
import { abrirEnNavegadorExterno } from "../lib/abrirExterno";

function hoyISO() {
  return new Date().toISOString().slice(0, 10);
}

export function FicDetalle() {
  const { t } = useTranslation();
  const { id } = useParams();
  const fic = useFetch(() => api.fics.get(id), [id]);

  if (fic.loading) return <Cargando />;
  if (fic.error) return <ErrorCarga error={fic.error} onReintentar={fic.reload} />;

  const f = fic.data;
  const lecturas = [...f.lecturas].sort((a, b) => a.id - b.id);
  const ultimaResena = f.resenas.at(-1);
  const epub = f.archivos.find((a) => a.formato === "epub");
  const snapshot = f.archivos.find((a) => a.formato === "html");

  return (
    <div>
      <div className="arv-card">
        <h2 style={{ marginBottom: 4 }}>{f.titulo}</h2>
        <p className="arv-muted" style={{ marginTop: 0 }}>
          {t("ficDetalle.por", { autor: f.autor })}
          {f.restricted && " 🔒"}
          {f.deleted_detected_at && ` · ${t("ficDetalle.borradoEnAo3")}`}
        </p>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          {f.fandoms.map((fd) => (
            <Link
              to={`/buscar?fandom=${encodeURIComponent(fd.nombre)}`}
              className="arv-tag arv-tag-accent"
              key={fd.id}
            >
              {fd.nombre}
            </Link>
          ))}
          {f.ships.map((s) => (
            <Link
              to={`/buscar?ship=${encodeURIComponent(s.nombre)}`}
              className="arv-tag arv-tag-accent-2"
              key={s.id}
            >
              {s.nombre}
            </Link>
          ))}
        </div>

        <p className="arv-muted">
          {f.chapters_published}/{f.chapters_total ?? "?"} · {f.word_count.toLocaleString()} {t("common.palabras")}
          {f.rating && ` · ${f.rating}`}
        </p>

        {f.summary && <p>{f.summary}</p>}

        {f.nota_bookmark && (
          <div
            style={{
              background: "var(--color-surface-2)",
              borderRadius: 12,
              padding: "10px 14px",
              marginBottom: 14,
            }}
          >
            <div className="arv-muted" style={{ fontSize: 10.5, letterSpacing: "0.05em", marginBottom: 4 }}>
              {t("ficDetalle.notaBookmark")}
            </div>
            <p style={{ margin: 0, fontStyle: "italic", whiteSpace: "pre-wrap" }}>{f.nota_bookmark}</p>
          </div>
        )}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <a className="arv-btn arv-btn-secondary" href={f.url} target="_blank" rel="noreferrer">
            {t("ficDetalle.verEnAo3")}
          </a>
          {snapshot && (
            <button
              className="arv-btn arv-btn-secondary"
              onClick={() => abrirEnNavegadorExterno(api.archivos.contenidoUrl(snapshot.id))}
            >
              {t("ficDetalle.verCopiaArchivada")}
            </button>
          )}
          <DescargarEpub fic={f} epub={epub} />
        </div>
      </div>

      <EstadoLectura fic={f} lecturas={lecturas} onChange={fic.reload} />
      <MiResena fic={f} resena={ultimaResena} onChange={fic.reload} />
      <MisColecciones fic={f} onChange={fic.reload} />
      <MisEtiquetas fic={f} onChange={fic.reload} />
    </div>
  );
}

function MisColecciones({ fic, onChange }) {
  const { t } = useTranslation();
  const colecciones = useFetch(() => api.colecciones.list());
  const [nombreNueva, setNombreNueva] = useState("");
  const [guardando, setGuardando] = useState(false);

  const idsDelFic = new Set(fic.colecciones.map((c) => c.id));
  // Las colecciones donde ya está este fic van primero (para verlas de un
  // vistazo sin tener que buscarlas entre el resto), después alfabético.
  const ordenadas = [...(colecciones.data ?? [])].sort((a, b) => {
    const yaEstaA = idsDelFic.has(a.id);
    const yaEstaB = idsDelFic.has(b.id);
    if (yaEstaA !== yaEstaB) return yaEstaA ? -1 : 1;
    return a.nombre.localeCompare(b.nombre, "es", { sensitivity: "base" });
  });

  async function alternar(coleccionId, yaEsta) {
    setGuardando(true);
    try {
      if (yaEsta) {
        await api.colecciones.removeFic(coleccionId, fic.id);
      } else {
        await api.colecciones.addFic(coleccionId, fic.id);
      }
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  async function crearYAgregar() {
    if (!nombreNueva.trim()) return;
    setGuardando(true);
    try {
      const nueva = await api.colecciones.create({ nombre: nombreNueva.trim() });
      await api.colecciones.addFic(nueva.id, fic.id);
      setNombreNueva("");
      colecciones.reload();
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="arv-card">
      <h3>{t("ficDetalle.colecciones")}</h3>
      {ordenadas.length > 0 ? (
        <div className="arv-coleccion-picker">
          {ordenadas.map((c) => {
            const yaEsta = idsDelFic.has(c.id);
            return (
              <button
                key={c.id}
                type="button"
                className={`arv-coleccion-picker-item ${yaEsta ? "arv-coleccion-picker-item-activa" : ""}`}
                disabled={guardando}
                onClick={() => alternar(c.id, yaEsta)}
              >
                <span className="arv-coleccion-picker-nombre">{c.nombre}</span>
                <span className="arv-coleccion-picker-check">
                  {yaEsta && <Check size={13} strokeWidth={3} />}
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <p className="arv-muted" style={{ margin: "0 0 12px" }}>
          {t("ficDetalle.sinColecciones")}
        </p>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="arv-input"
          placeholder={t("ficDetalle.nuevaColeccionPlaceholder")}
          value={nombreNueva}
          onChange={(e) => setNombreNueva(e.target.value)}
        />
        <button
          className="arv-btn arv-btn-secondary arv-btn-compacto"
          disabled={guardando}
          onClick={crearYAgregar}
        >
          {t("ficDetalle.crearYAgregar")}
        </button>
      </div>
    </div>
  );
}

function MisEtiquetas({ fic, onChange }) {
  const { t } = useTranslation();
  const [nombreNueva, setNombreNueva] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function agregar() {
    if (!nombreNueva.trim()) return;
    setGuardando(true);
    try {
      await api.etiquetas.addToFic(fic.id, nombreNueva.trim());
      setNombreNueva("");
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  async function quitar(etiquetaId) {
    setGuardando(true);
    try {
      await api.etiquetas.removeFromFic(fic.id, etiquetaId);
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {t("ficDetalle.misEtiquetas")}
        <InfoPopover>{t("ficDetalle.misEtiquetasInfo")}</InfoPopover>
      </h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
        {fic.etiquetas_personales.map((et) => (
          <span key={et.id} className="arv-tag arv-tag-accent-2" style={{ display: "inline-flex", gap: 6 }}>
            {et.nombre}
            <button
              onClick={() => quitar(et.id)}
              disabled={guardando}
              aria-label={t("ficDetalle.quitarEtiqueta", { nombre: et.nombre })}
              style={{ border: "none", background: "transparent", cursor: "pointer", color: "inherit" }}
            >
              ✕
            </button>
          </span>
        ))}
        {fic.etiquetas_personales.length === 0 && (
          <p className="arv-muted" style={{ margin: 0 }}>
            {t("ficDetalle.sinEtiquetas")}
          </p>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="arv-input"
          placeholder={t("ficDetalle.nuevaEtiquetaPlaceholder")}
          value={nombreNueva}
          onChange={(e) => setNombreNueva(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && agregar()}
        />
        <button className="arv-btn arv-btn-secondary" disabled={guardando} onClick={agregar}>
          {t("ficDetalle.agregar")}
        </button>
      </div>
    </div>
  );
}

function DescargarEpub({ fic, epub }) {
  const { t, i18n } = useTranslation();
  const [descargando, setDescargando] = useState(false);
  const [disparado, setDisparado] = useState(false);
  const [error, setError] = useState(null);

  async function descargar() {
    setDescargando(true);
    setError(null);
    try {
      await api.sync.trigger("epub", { ao3Id: fic.ao3_id });
      setDisparado(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <span>
      <button className="arv-btn arv-btn-secondary" disabled={descargando} onClick={descargar}>
        {descargando
          ? t("importarPorUrl.disparando")
          : epub
          ? t("ficDetalle.volverADescargarEpub")
          : t("ficDetalle.descargarEpub")}
      </button>
      {epub && (
        <span className="arv-muted" style={{ marginLeft: 8 }}>
          {t("ficDetalle.guardado", { fecha: new Date(epub.fecha_descarga).toLocaleDateString(i18n.language) })}
        </span>
      )}
      {disparado && <p className="arv-muted">{t("ficDetalle.descargaEnCamino")}</p>}
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
    </span>
  );
}

function EstadoLectura({ fic, lecturas, onChange }) {
  const { t, i18n } = useTranslation();
  const ESTADOS = [
    { value: "pendiente", label: t("ficDetalle.estados.pendiente") },
    { value: "leyendo", label: t("ficDetalle.estados.leyendo") },
    { value: "leido", label: t("ficDetalle.estados.leido") },
    { value: "abandonado", label: t("ficDetalle.estados.abandonado") },
  ];
  const ultimaLectura = lecturas.at(-1);
  const [guardando, setGuardando] = useState(false);
  const [fechaRelectura, setFechaRelectura] = useState(hoyISO());
  const [editandoFechaId, setEditandoFechaId] = useState(null);

  async function cambiarFecha(lecturaId, fecha) {
    setGuardando(true);
    try {
      await api.lecturas.update(fic.id, lecturaId, { fecha_fin: fecha || null });
      setEditandoFechaId(null);
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  async function cambiarEstado(estado) {
    setGuardando(true);
    try {
      if (ultimaLectura) {
        await api.lecturas.update(fic.id, ultimaLectura.id, { estado });
      } else {
        await api.lecturas.create(fic.id, { estado });
      }
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  async function registrarRelectura() {
    setGuardando(true);
    try {
      await api.lecturas.create(fic.id, {
        estado: "leido",
        fecha_fin: fechaRelectura,
        es_relectura: true,
      });
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  async function borrarLectura(lecturaId) {
    setGuardando(true);
    try {
      await api.lecturas.remove(fic.id, lecturaId);
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="arv-card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {t("ficDetalle.estadoDeLectura")}
        <InfoPopover>{t("ficDetalle.estadoDeLecturaInfo")}</InfoPopover>
      </h3>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        {ESTADOS.map((e) => (
          <button
            key={e.value}
            className={`arv-btn${ultimaLectura?.estado === e.value ? "" : " arv-btn-secondary"}`}
            disabled={guardando}
            onClick={() => cambiarEstado(e.value)}
          >
            {e.label}
          </button>
        ))}
      </div>

      {lecturas.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          {lecturas.map((l) => (
            <div className="arv-list-item" key={l.id}>
              <span>
                {t(`ficDetalle.estados.${l.estado}`, l.estado)}
                {l.es_relectura && <span className="arv-muted"> · {t("ficDetalle.relectura")}</span>}
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                {editandoFechaId === l.id ? (
                  <input
                    className="arv-input"
                    type="date"
                    autoFocus
                    defaultValue={l.fecha_fin ?? ""}
                    disabled={guardando}
                    onBlur={(e) => cambiarFecha(l.id, e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && cambiarFecha(l.id, e.target.value)}
                    style={{ maxWidth: 150, padding: "4px 10px" }}
                  />
                ) : (
                  <button
                    onClick={() => setEditandoFechaId(l.id)}
                    className="arv-muted"
                    style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, font: "inherit" }}
                  >
                    {l.fecha_fin ?? t("ficDetalle.sinFecha")}
                  </button>
                )}
                <button
                  onClick={() => borrarLectura(l.id)}
                  disabled={guardando}
                  aria-label={t("ficDetalle.borrarLectura")}
                  style={{
                    border: "none",
                    background: "transparent",
                    color: "var(--color-text-muted)",
                    cursor: "pointer",
                    fontSize: 14,
                    padding: 2,
                  }}
                >
                  ✕
                </button>
              </span>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          className="arv-input"
          type="date"
          value={fechaRelectura}
          onChange={(e) => setFechaRelectura(e.target.value)}
          style={{ maxWidth: 160 }}
        />
        <button className="arv-btn arv-btn-secondary" disabled={guardando} onClick={registrarRelectura}>
          {t("ficDetalle.registrarRelectura")}
        </button>
      </div>
    </div>
  );
}

function MiResena({ fic, resena, onChange }) {
  const { t } = useTranslation();
  const [editando, setEditando] = useState(false);
  const [rating, setRating] = useState(resena?.rating ?? 5);
  const [texto, setTexto] = useState(resena?.texto ?? "");
  const [hizoLlorar, setHizoLlorar] = useState(resena?.hizo_llorar ?? false);
  const [guardando, setGuardando] = useState(false);

  async function guardar() {
    setGuardando(true);
    try {
      if (resena) {
        await api.resenas.update(fic.id, resena.id, { rating: Number(rating), texto, hizo_llorar: hizoLlorar });
      } else {
        await api.resenas.create(fic.id, { rating: Number(rating), texto, hizo_llorar: hizoLlorar });
      }
      setEditando(false);
      onChange();
    } finally {
      setGuardando(false);
    }
  }

  if (!editando) {
    return (
      <div className="arv-card">
        <h3>{t("ficDetalle.miResena")}</h3>
        {resena ? (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
              <Estrellas rating={resena.rating} />
              {resena.hizo_llorar && (
                <span className="arv-llore-badge">
                  <Droplet size={12} fill="currentColor" />
                  {t("ficDetalle.hizoLlorarBadge")}
                </span>
              )}
            </div>
            <p>{resena.texto}</p>
          </>
        ) : (
          <p className="arv-muted">{t("ficDetalle.sinResena")}</p>
        )}
        <button className="arv-btn arv-btn-secondary" onClick={() => setEditando(true)}>
          {resena ? t("common.editar") : t("ficDetalle.agregarResena")}
        </button>
      </div>
    );
  }

  return (
    <div className="arv-card">
      <h3>{t("ficDetalle.miResena")}</h3>
      <label className="arv-muted">{t("ficDetalle.ratingLabel")}</label>
      <div style={{ margin: "6px 0 14px" }}>
        <EstrellasInput value={Number(rating)} onChange={setRating} />
      </div>
      <button
        type="button"
        className={`arv-llore-toggle ${hizoLlorar ? "arv-llore-toggle-activo" : ""}`}
        disabled={guardando}
        onClick={() => setHizoLlorar((v) => !v)}
      >
        <Droplet size={15} fill={hizoLlorar ? "currentColor" : "none"} />
        {t("ficDetalle.hizoLlorarLabel")}
      </button>
      <textarea
        className="arv-input"
        rows={4}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        placeholder={t("ficDetalle.resenaPlaceholder")}
        style={{ margin: "14px 0 10px", borderRadius: 12 }}
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
