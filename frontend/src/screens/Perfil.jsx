import { Link } from "react-router-dom";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

export function Perfil() {
  const fics = useFetch(() => api.fics.list({ limit: 200 }));

  return (
    <div>
      <div className="arv-card">
        <h2 style={{ marginBottom: 2 }}>Tu biblioteca</h2>
        <p className="arv-muted" style={{ marginTop: 0 }}>
          Conectado con AO3 · ver pestaña AO3 para el estado de sincronización
        </p>
      </div>

      <div className="arv-card">
        <h3>Historial de lectura</h3>
        {fics.loading && <Cargando />}
        {fics.error && <ErrorCarga error={fics.error} onReintentar={fics.reload} />}
        {fics.data?.length === 0 && <Vacio>Todavía no importaste ningún fic.</Vacio>}
        {fics.data?.map((f) => (
          <Link key={f.id} to={`/fics/${f.id}`} className="arv-fic-row">
            <div>
              <div className="fandom">{f.fandoms[0]?.nombre ?? "Sin fandom"}</div>
              <div className="titulo">{f.titulo}</div>
            </div>
            <div className="meta" style={{ textAlign: "right" }}>
              <div>{f.estado_actual ?? "sin estado"}</div>
              <div>{f.word_count.toLocaleString()} palabras</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
