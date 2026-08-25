import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Trash2, Copy, Check, X } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

export function Recomendar() {
  const { t } = useTranslation();
  const colecciones = useFetch(() => api.colecciones.list());
  const listas = useFetch(() => api.recomendaciones.list());

  const [seleccion, setSeleccion] = useState([]);
  const [titulo, setTitulo] = useState("");
  const [nota, setNota] = useState("");
  const [q, setQ] = useState("");
  const resultados = useFetch(
    () => (q ? api.fics.list({ q, limit: 8 }) : Promise.resolve([])),
    [q]
  );
  const [publicando, setPublicando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [copiado, setCopiado] = useState(false);

  const idsEnSeleccion = new Set(seleccion.map((f) => f.id));

  function agregarFic(fic) {
    if (idsEnSeleccion.has(fic.id)) return;
    setSeleccion((prev) => [...prev, fic]);
  }

  function quitarFic(ficId) {
    setSeleccion((prev) => prev.filter((f) => f.id !== ficId));
  }

  async function agregarDesdeColeccion(coleccionId) {
    const fics = await api.fics.list({ coleccion: coleccionId, limit: 1000 });
    setSeleccion((prev) => {
      const yaHay = new Set(prev.map((f) => f.id));
      const nuevos = fics.filter((f) => !yaHay.has(f.id));
      return [...prev, ...nuevos];
    });
  }

  async function publicar() {
    setPublicando(true);
    try {
      const creada = await api.recomendaciones.create({
        titulo: titulo.trim() || null,
        nota: nota.trim() || null,
        fic_ids: seleccion.map((f) => f.id),
      });
      setResultado(creada);
      setSeleccion([]);
      setTitulo("");
      setNota("");
      listas.reload();
    } catch (err) {
      alert(err.message);
    } finally {
      setPublicando(false);
    }
  }

  async function borrarLista(id) {
    await api.recomendaciones.remove(id);
    listas.reload();
  }

  function linkDe(token) {
    return `${window.location.origin}/recomendar/${token}`;
  }

  async function copiarLink(token) {
    await navigator.clipboard.writeText(linkDe(token));
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  }

  return (
    <div>
      <div className="arv-card">
        <h3>{t("recomendar.titulo")}</h3>
        <p className="arv-muted" style={{ marginBottom: 14 }}>
          {t("recomendar.info")}
        </p>

        <input
          className="arv-input"
          style={{ marginBottom: 8 }}
          placeholder={t("recomendar.tituloListaPlaceholder")}
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
        />
        <textarea
          className="arv-input"
          style={{ resize: "vertical", minHeight: 60, marginBottom: 16 }}
          placeholder={t("recomendar.notaPlaceholder")}
          value={nota}
          onChange={(e) => setNota(e.target.value)}
        />

        <h4 style={{ marginBottom: 8 }}>{t("recomendar.desdeColeccion")}</h4>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
          {colecciones.data?.map((c) => (
            <button
              key={c.id}
              className="arv-tag arv-tag-accent-2"
              style={{ border: "none", cursor: "pointer" }}
              onClick={() => agregarDesdeColeccion(c.id)}
            >
              + {c.nombre} ({c.cantidad_fics})
            </button>
          ))}
          {colecciones.data?.length === 0 && (
            <p className="arv-muted" style={{ margin: 0 }}>
              {t("colecciones.sinColecciones")}
            </p>
          )}
        </div>

        <h4 style={{ marginBottom: 8 }}>{t("recomendar.unoPorUno")}</h4>
        <input
          className="arv-input"
          placeholder={t("recomendar.buscarFicPlaceholder")}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ marginBottom: 8 }}
        />
        {q && (
          <div style={{ maxHeight: 180, overflowY: "auto", marginBottom: 16 }}>
            {resultados.data?.map((fic) => (
              <div
                key={fic.id}
                className="arv-list-item"
                style={{ cursor: idsEnSeleccion.has(fic.id) ? "default" : "pointer" }}
                onClick={() => agregarFic(fic)}
              >
                <span style={idsEnSeleccion.has(fic.id) ? { color: "var(--color-text-muted)" } : undefined}>
                  {fic.titulo}
                </span>
                {idsEnSeleccion.has(fic.id) && <Check size={14} />}
              </div>
            ))}
            {resultados.data?.length === 0 && <p className="arv-muted">{t("perfil.sinResultados")}</p>}
          </div>
        )}

        <h4 style={{ marginBottom: 8 }}>{t("recomendar.enLaLista", { count: seleccion.length })}</h4>
        {seleccion.length === 0 ? (
          <p className="arv-muted" style={{ marginBottom: 16 }}>
            {t("recomendar.listaVacia")}
          </p>
        ) : (
          <div style={{ marginBottom: 16 }}>
            {seleccion.map((f) => (
              <div className="arv-list-item" key={f.id}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {f.titulo}
                </span>
                <button
                  onClick={() => quitarFic(f.id)}
                  aria-label={t("recomendar.quitarDeLaLista")}
                  style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--color-text-muted)" }}
                >
                  <X size={15} />
                </button>
              </div>
            ))}
          </div>
        )}

        <button className="arv-btn" disabled={seleccion.length === 0 || publicando} onClick={publicar}>
          {publicando ? t("recomendar.publicando") : t("recomendar.publicar")}
        </button>
      </div>

      {resultado && (
        <div className="arv-card">
          <p style={{ marginBottom: 10 }}>{t("recomendar.listoInfo")}</p>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input className="arv-input" readOnly value={linkDe(resultado.token)} onFocus={(e) => e.target.select()} />
            <button className="arv-btn arv-btn-secondary" onClick={() => copiarLink(resultado.token)}>
              {copiado ? <Check size={16} /> : <Copy size={16} />}
            </button>
          </div>
        </div>
      )}

      <div className="arv-card">
        <h3>{t("recomendar.tusListas")}</h3>
        {listas.loading && <Cargando />}
        {listas.error && <ErrorCarga error={listas.error} onReintentar={listas.reload} />}
        {listas.data?.length === 0 && <Vacio>{t("recomendar.sinListas")}</Vacio>}
        {listas.data?.map((l) => (
          <div className="arv-list-item" key={l.id}>
            <div style={{ minWidth: 0 }}>
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {l.titulo || t("recomendar.sinTitulo")}
              </div>
              <span className="arv-muted" style={{ fontSize: 12 }}>
                {t("recomendar.fics", { count: l.cantidad_fics })}
              </span>
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", flex: "none" }}>
              <button className="arv-icon-btn" onClick={() => copiarLink(l.token)} aria-label={t("recomendar.copiarLink")}>
                <Copy size={15} />
              </button>
              <button className="arv-icon-btn" onClick={() => borrarLista(l.id)} aria-label={t("recomendar.borrarLista")}>
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
