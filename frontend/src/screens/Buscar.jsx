import { Link, useSearchParams } from "react-router-dom";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { ImportarPorUrl } from "../components/ImportarPorUrl";

const ESTADO_LABEL = {
  leido: "Leídos",
  leyendo: "Leyendo",
  abandonado: "Abandonados",
  pendiente: "Pendientes",
};

export function Buscar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get("q") || "";
  const fandom = searchParams.get("fandom") || "";
  const ship = searchParams.get("ship") || "";
  const etiqueta = searchParams.get("etiqueta") || "";
  const estado = searchParams.get("estado") || "";
  const completo = searchParams.get("completo"); // "true" | "false" | null

  function setFiltro(clave, valor) {
    const next = new URLSearchParams(searchParams);
    if (valor) next.set(clave, valor);
    else next.delete(clave);
    setSearchParams(next, { replace: true });
  }

  const fandoms = useFetch(() => api.stats.topFandoms(30));
  const etiquetas = useFetch(() => api.etiquetas.list());
  const fics = useFetch(
    () =>
      api.fics.list({
        q,
        fandom,
        ship,
        etiqueta,
        estado,
        ...(completo !== null ? { completo } : {}),
        limit: 100,
      }),
    [q, fandom, ship, etiqueta, estado, completo]
  );

  const hayFiltrosExtra = ship || etiqueta || estado || completo !== null;

  return (
    <div>
      <ImportarPorUrl />
      <input
        className="arv-input"
        placeholder="Buscar en tu biblioteca…"
        value={q}
        onChange={(e) => setFiltro("q", e.target.value)}
        style={{ marginBottom: 10 }}
      />

      {hayFiltrosExtra && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10, alignItems: "center" }}>
          {ship && <span className="arv-tag arv-tag-accent-2">{ship}</span>}
          {etiqueta && <span className="arv-tag arv-tag-accent-2">{etiqueta}</span>}
          {estado && <span className="arv-tag arv-tag-accent-2">{ESTADO_LABEL[estado] ?? estado}</span>}
          {completo !== null && (
            <span className="arv-tag arv-tag-accent-2">{completo === "true" ? "Completos" : "WIP"}</span>
          )}
          <button
            className="arv-tab"
            onClick={() => {
              setSearchParams({ ...(q ? { q } : {}), ...(fandom ? { fandom } : {}) }, { replace: true });
            }}
          >
            Limpiar
          </button>
        </div>
      )}

      <div className="arv-scrollnav" style={{ marginBottom: 14 }}>
        <button className={`arv-tab${fandom === "" ? " active" : ""}`} onClick={() => setFiltro("fandom", "")}>
          Todos
        </button>
        {fandoms.data?.map((f) => (
          <button
            key={f.nombre}
            className={`arv-tab${fandom === f.nombre ? " active" : ""}`}
            onClick={() => setFiltro("fandom", f.nombre === fandom ? "" : f.nombre)}
          >
            {f.nombre}
          </button>
        ))}
      </div>

      {etiquetas.data?.length > 0 && (
        <div className="arv-scrollnav" style={{ marginBottom: 14 }}>
          {etiquetas.data.map((et) => (
            <button
              key={et.id}
              className={`arv-tab${etiqueta === et.nombre ? " active" : ""}`}
              onClick={() => setFiltro("etiqueta", et.nombre === etiqueta ? "" : et.nombre)}
            >
              #{et.nombre}
            </button>
          ))}
        </div>
      )}

      {fics.loading && <Cargando />}
      {fics.error && <ErrorCarga error={fics.error} onReintentar={fics.reload} />}
      {fics.data?.length === 0 && <Vacio>No encontré fics con esos filtros.</Vacio>}

      <div className="arv-card">
        {fics.data?.map((fic) => (
          <Link key={fic.id} to={`/fics/${fic.id}`} className="arv-fic-row">
            <div>
              <div className="fandom">{fic.fandoms[0]?.nombre ?? "Sin fandom"}</div>
              <div className="titulo">{fic.titulo}</div>
            </div>
            <div className="meta" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
              {formatoCompacto(fic.word_count)}
              <br />
              {fic.estado_actual ?? "sin estado"}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function formatoCompacto(numero) {
  if (numero >= 1_000) return `${(numero / 1_000).toFixed(1)}k`;
  return String(numero);
}
