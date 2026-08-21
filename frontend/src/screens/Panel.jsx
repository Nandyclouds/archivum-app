import { Link } from "react-router-dom";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga } from "../components/EstadoCarga";

const ESTADO_LABEL = {
  leido: "Completos",
  leyendo: "Leyendo",
  abandonado: "Abandonados",
  pendiente: "Pendientes",
};

export function Panel() {
  const resumen = useFetch(() => api.stats.resumen());
  const topFandoms = useFetch(() => api.stats.topFandoms(6));
  const topShips = useFetch(() => api.stats.topShips(6, "romantico"));
  const topRelaciones = useFetch(() => api.stats.topShips(6, "platonico"));
  const estadoLectura = useFetch(() => api.stats.estadoLectura());

  if (resumen.loading) return <Cargando />;
  if (resumen.error) return <ErrorCarga error={resumen.error} onReintentar={resumen.reload} />;

  const r = resumen.data;
  const maxFandom = topFandoms.data?.[0]?.total ?? 1;

  return (
    <div>
      <div className="arv-card">
        <p className="arv-muted" style={{ marginBottom: 4 }}>
          {r.racha_dias > 0 ? `${r.racha_dias} día${r.racha_dias === 1 ? "" : "s"} seguidos leyendo` : "Todavía sin racha"}
        </p>
      </div>

      <div className="arv-grid-2" style={{ marginBottom: 14 }}>
        <div className="arv-stat">
          <div className="label">Palabras</div>
          <div className="value">{formatoCompacto(r.total_palabras_leidas)}</div>
        </div>
        <Link to="/buscar?estado=leido" className="arv-stat arv-row-link">
          <div className="label">Fics leídos</div>
          <div className="value">{r.total_lecturas_leido}</div>
        </Link>
        <div className="arv-stat">
          <div className="label">Fandoms</div>
          <div className="value">{r.total_fandoms}</div>
        </div>
        <div className="arv-stat">
          <div className="label">Ships</div>
          <div className="value">{r.total_ships}</div>
        </div>
      </div>

      <div className="arv-card">
        <h3>Top fandoms</h3>
        {topFandoms.loading && <Cargando />}
        {topFandoms.data?.length === 0 && <p className="arv-muted">Todavía no hay fics importados.</p>}
        {topFandoms.data?.map((f) => (
          <Link to={`/buscar?fandom=${encodeURIComponent(f.nombre)}`} className="arv-bar-row arv-row-link" key={f.nombre}>
            <span style={{ flex: "0 0 40%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {f.nombre}
            </span>
            <div className="arv-bar-track">
              <div className="arv-bar-fill" style={{ width: `${(f.total / maxFandom) * 100}%` }} />
            </div>
            <span className="arv-muted">{f.total}</span>
          </Link>
        ))}
      </div>

      <div className="arv-card">
        <h3>Estado de lectura</h3>
        {estadoLectura.loading && <Cargando />}
        {estadoLectura.data &&
          Object.entries(estadoLectura.data).map(([estado, total]) => (
            <Link to={`/buscar?estado=${estado}`} className="arv-list-item arv-row-link" key={estado}>
              <span>{ESTADO_LABEL[estado] ?? estado}</span>
              <strong>{total}</strong>
            </Link>
          ))}
        {estadoLectura.data && Object.keys(estadoLectura.data).length === 0 && (
          <p className="arv-muted">Todavía no marcaste ningún fic con un estado de lectura.</p>
        )}
      </div>

      <div className="arv-card">
        <h3>Ships favoritos</h3>
        <p className="arv-muted" style={{ marginTop: -6 }}>Parejas románticas (tag con "/")</p>
        {topShips.loading && <Cargando />}
        {topShips.data?.map((s) => (
          <Link to={`/buscar?ship=${encodeURIComponent(s.nombre)}`} className="arv-list-item arv-row-link" key={s.nombre}>
            <span>{s.nombre}</span>
            <span className="arv-muted">×{s.total}</span>
          </Link>
        ))}
        {topShips.data?.length === 0 && <p className="arv-muted">Sin ships todavía.</p>}
      </div>

      <div className="arv-card">
        <h3>Relaciones favoritas</h3>
        <p className="arv-muted" style={{ marginTop: -6 }}>Amistad/familia (tag con "&amp;")</p>
        {topRelaciones.loading && <Cargando />}
        {topRelaciones.data?.map((s) => (
          <Link to={`/buscar?ship=${encodeURIComponent(s.nombre)}`} className="arv-list-item arv-row-link" key={s.nombre}>
            <span>{s.nombre}</span>
            <span className="arv-muted">×{s.total}</span>
          </Link>
        ))}
        {topRelaciones.data?.length === 0 && <p className="arv-muted">Sin relaciones todavía.</p>}
      </div>
    </div>
  );
}

function formatoCompacto(numero) {
  if (numero >= 1_000_000) return `${(numero / 1_000_000).toFixed(1)}M`;
  if (numero >= 1_000) return `${(numero / 1_000).toFixed(1)}k`;
  return String(numero);
}
