import { Link, useParams, useSearchParams } from "react-router-dom";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

const TITULOS = {
  fandoms: "Todos los fandoms",
  romantico: "Todas las parejas",
  platonico: "Todas las relaciones",
  palabras: "Fics leídos por palabras",
};

export function TopCompleto() {
  const { tipo } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const anio = searchParams.get("anio") || "";

  const anios = useFetch(() => api.stats.palabrasPorAnio());
  const aniosDisponibles = (anios.data ?? []).map((p) => p.periodo).sort().reverse();

  const datos = useFetch(() => {
    if (tipo === "palabras") return api.fics.list({ orden: "palabras", limit: 500, ...(anio ? { anio } : {}) });
    if (tipo === "fandoms") return api.stats.topFandoms(500, anio || undefined);
    return api.stats.topShips(500, tipo, anio || undefined);
  }, [tipo, anio]);

  const linkPara = (nombre) =>
    tipo === "fandoms"
      ? `/buscar?fandom=${encodeURIComponent(nombre)}`
      : `/buscar?ship=${encodeURIComponent(nombre)}`;

  return (
    <div>
      <div className="arv-card">
        <h2 style={{ marginBottom: 2 }}>{TITULOS[tipo] ?? "Todos"}{anio ? ` en ${anio}` : ""}</h2>
      </div>

      {aniosDisponibles.length > 0 && (
        <div className="arv-scrollnav" style={{ marginBottom: 14 }}>
          <button
            className={`arv-tab${anio === "" ? " active" : ""}`}
            onClick={() => setSearchParams({}, { replace: true })}
          >
            Todos los años
          </button>
          {aniosDisponibles.map((a) => (
            <button
              key={a}
              className={`arv-tab${anio === a ? " active" : ""}`}
              onClick={() => setSearchParams(a === anio ? {} : { anio: a }, { replace: true })}
            >
              {a}
            </button>
          ))}
        </div>
      )}

      {datos.loading && <Cargando />}
      {datos.error && <ErrorCarga error={datos.error} onReintentar={datos.reload} />}
      {datos.data?.length === 0 && <Vacio>Nada para mostrar acá todavía.</Vacio>}

      <div className="arv-card">
        {tipo === "palabras"
          ? datos.data?.map((fic) => (
              <Link to={`/fics/${fic.id}`} className="arv-fic-row" key={fic.id}>
                <div>
                  <div className="fandom">{fic.fandoms[0]?.nombre ?? "Sin fandom"}</div>
                  <div className="titulo">{fic.titulo}</div>
                </div>
                <div className="meta" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {fic.word_count.toLocaleString()} palabras
                </div>
              </Link>
            ))
          : datos.data?.map((d) => (
              <Link to={linkPara(d.nombre)} className="arv-list-item arv-row-link" key={d.nombre}>
                <span>{d.nombre}</span>
                <span className="arv-muted">×{d.total}</span>
              </Link>
            ))}
      </div>
    </div>
  );
}
