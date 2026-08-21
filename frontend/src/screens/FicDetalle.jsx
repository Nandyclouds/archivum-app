import { useState } from "react";
import { useParams } from "react-router-dom";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga } from "../components/EstadoCarga";
import { Estrellas } from "../components/Estrellas";
import { InfoPopover } from "../components/InfoPopover";
import { abrirEnNavegadorExterno } from "../lib/abrirExterno";

const ESTADOS = [
  { value: "pendiente", label: "Pendiente" },
  { value: "leyendo", label: "Leyendo" },
  { value: "leido", label: "Leído" },
  { value: "abandonado", label: "Abandonado" },
];

const ESTADO_LABEL = Object.fromEntries(ESTADOS.map((e) => [e.value, e.label]));

function hoyISO() {
  return new Date().toISOString().slice(0, 10);
}

export function FicDetalle() {
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
          por {f.autor}
          {f.restricted && " 🔒"}
          {f.deleted_detected_at && " · borrado en AO3"}
        </p>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          {f.fandoms.map((fd) => (
            <span className="arv-tag arv-tag-accent" key={fd.id}>
              {fd.nombre}
            </span>
          ))}
          {f.ships.map((s) => (
            <span className="arv-tag arv-tag-accent-2" key={s.id}>
              {s.nombre}
            </span>
          ))}
        </div>

        <p className="arv-muted">
          {f.chapters_published}/{f.chapters_total ?? "?"} · {f.word_count.toLocaleString()} palabras
          {f.rating && ` · ${f.rating}`}
        </p>

        {f.summary && <p>{f.summary}</p>}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <a className="arv-btn arv-btn-secondary" href={f.url} target="_blank" rel="noreferrer">
            Ver en AO3
          </a>
          {snapshot && (
            <button
              className="arv-btn arv-btn-secondary"
              onClick={() => abrirEnNavegadorExterno(api.archivos.contenidoUrl(snapshot.id))}
            >
              Ver copia archivada
            </button>
          )}
          <DescargarEpub fic={f} epub={epub} onChange={fic.reload} />
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
  const colecciones = useFetch(() => api.colecciones.list());
  const [nombreNueva, setNombreNueva] = useState("");
  const [guardando, setGuardando] = useState(false);

  const idsDelFic = new Set(fic.colecciones.map((c) => c.id));

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
      <h3>Colecciones</h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
        {colecciones.data?.map((c) => {
          const yaEsta = idsDelFic.has(c.id);
          return (
            <button
              key={c.id}
              className={`arv-tag ${yaEsta ? "arv-tag-accent" : "arv-tag-accent-2"}`}
              disabled={guardando}
              onClick={() => alternar(c.id, yaEsta)}
              style={{ border: "none", cursor: "pointer" }}
            >
              {yaEsta ? "✓ " : "+ "}
              {c.nombre}
            </button>
          );
        })}
        {colecciones.data?.length === 0 && (
          <p className="arv-muted" style={{ margin: 0 }}>
            Todavía no tenés colecciones.
          </p>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="arv-input"
          placeholder="Nueva colección…"
          value={nombreNueva}
          onChange={(e) => setNombreNueva(e.target.value)}
        />
        <button className="arv-btn arv-btn-secondary" disabled={guardando} onClick={crearYAgregar}>
          Crear y agregar
        </button>
      </div>
    </div>
  );
}

function MisEtiquetas({ fic, onChange }) {
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
        Mis etiquetas
        <InfoPopover>
          Distinto de las colecciones: son etiquetas rápidas y libres, propias tuyas (no vienen de
          AO3). Sirven para filtrar en Buscar.
        </InfoPopover>
      </h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
        {fic.etiquetas_personales.map((et) => (
          <span key={et.id} className="arv-tag arv-tag-accent-2" style={{ display: "inline-flex", gap: 6 }}>
            {et.nombre}
            <button
              onClick={() => quitar(et.id)}
              disabled={guardando}
              aria-label={`Quitar etiqueta ${et.nombre}`}
              style={{ border: "none", background: "transparent", cursor: "pointer", color: "inherit" }}
            >
              ✕
            </button>
          </span>
        ))}
        {fic.etiquetas_personales.length === 0 && (
          <p className="arv-muted" style={{ margin: 0 }}>
            Sin etiquetas todavía.
          </p>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="arv-input"
          placeholder="Nueva etiqueta…"
          value={nombreNueva}
          onChange={(e) => setNombreNueva(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && agregar()}
        />
        <button className="arv-btn arv-btn-secondary" disabled={guardando} onClick={agregar}>
          Agregar
        </button>
      </div>
    </div>
  );
}

function DescargarEpub({ fic, epub, onChange }) {
  const [descargando, setDescargando] = useState(false);
  const [error, setError] = useState(null);

  async function descargar() {
    setDescargando(true);
    setError(null);
    try {
      await api.ao3.descargarEpub(fic.id);
      onChange();
    } catch (err) {
      setError(err.message);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <span>
      <button className="arv-btn arv-btn-secondary" disabled={descargando} onClick={descargar}>
        {descargando ? "Descargando…" : epub ? "Volver a descargar EPUB" : "Descargar EPUB"}
      </button>
      {epub && (
        <span className="arv-muted" style={{ marginLeft: 8 }}>
          guardado {new Date(epub.fecha_descarga).toLocaleDateString()}
        </span>
      )}
      {error && <p style={{ color: "var(--color-accent)" }}>{error}</p>}
    </span>
  );
}

function EstadoLectura({ fic, lecturas, onChange }) {
  const ultimaLectura = lecturas.at(-1);
  const [guardando, setGuardando] = useState(false);
  const [fechaRelectura, setFechaRelectura] = useState(hoyISO());

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
        Estado de lectura
        <InfoPopover>
          Cada lectura marcada "Leído" —incluidas las relecturas— suma las palabras del fic a
          "Palabras leídas" y "Fics leídos" en el Panel. Cambiar el estado acá arriba actualiza
          tu lectura más reciente. Para que una relectura cuente aparte (y no pise la anterior),
          usá "Registrar relectura" más abajo: agrega una lectura nueva sin borrar la vieja.
        </InfoPopover>
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
                {ESTADO_LABEL[l.estado] ?? l.estado}
                {l.es_relectura && <span className="arv-muted"> · relectura</span>}
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className="arv-muted">{l.fecha_fin ?? "sin fecha"}</span>
                <button
                  onClick={() => borrarLectura(l.id)}
                  disabled={guardando}
                  aria-label="Borrar esta lectura"
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
          + Registrar relectura
        </button>
      </div>
    </div>
  );
}

function MiResena({ fic, resena, onChange }) {
  const [editando, setEditando] = useState(false);
  const [rating, setRating] = useState(resena?.rating ?? 5);
  const [texto, setTexto] = useState(resena?.texto ?? "");
  const [guardando, setGuardando] = useState(false);

  async function guardar() {
    setGuardando(true);
    try {
      if (resena) {
        await api.resenas.update(fic.id, resena.id, { rating: Number(rating), texto });
      } else {
        await api.resenas.create(fic.id, { rating: Number(rating), texto });
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
        <h3>Mi reseña</h3>
        {resena ? (
          <>
            <Estrellas rating={resena.rating} />
            <p>{resena.texto}</p>
          </>
        ) : (
          <p className="arv-muted">Todavía no dejaste una reseña.</p>
        )}
        <button className="arv-btn arv-btn-secondary" onClick={() => setEditando(true)}>
          {resena ? "Editar" : "Agregar reseña"}
        </button>
      </div>
    );
  }

  return (
    <div className="arv-card">
      <h3>Mi reseña</h3>
      <label className="arv-muted">Rating (1 a 5, permite medios)</label>
      <input
        className="arv-input"
        type="number"
        min="1"
        max="5"
        step="0.5"
        value={rating}
        onChange={(e) => setRating(e.target.value)}
        style={{ marginBottom: 10 }}
      />
      <textarea
        className="arv-input"
        rows={4}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        placeholder="¿Qué te pareció?"
        style={{ marginBottom: 10, borderRadius: 12 }}
      />
      <div style={{ display: "flex", gap: 8 }}>
        <button className="arv-btn" disabled={guardando} onClick={guardar}>
          Guardar
        </button>
        <button className="arv-btn arv-btn-secondary" onClick={() => setEditando(false)}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
