import { Link, useParams, useSearchParams } from "react-router-dom";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

const TITULOS = {
  fandoms: "Todos los fandoms",
  romantico: "Todas las parejas",
  platonico: "Todas las relaciones",
};

export function TopCompleto() {
  const { tipo } = useParams();
  const [searchParams] = useSearchParams();
  const anio = searchParams.get("anio") || undefined;

  const datos = useFetch(() => {
    if (tipo === "fandoms") return api.stats.topFandoms(500, anio);
    return api.stats.topShips(500, tipo, anio);
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

      {datos.loading && <Cargando />}
      {datos.error && <ErrorCarga error={datos.error} onReintentar={datos.reload} />}
      {datos.data?.length === 0 && <Vacio>Nada para mostrar acá todavía.</Vacio>}

      <div className="arv-card">
        {datos.data?.map((d) => (
          <Link to={linkPara(d.nombre)} className="arv-list-item arv-row-link" key={d.nombre}>
            <span>{d.nombre}</span>
            <span className="arv-muted">×{d.total}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
