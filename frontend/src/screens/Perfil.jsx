import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, User } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";

const BUCKET_LABEL = {
  "drabble (<1k)": "Drabble (<1k)",
  "corto (1k-10k)": "Corto (1k-10k)",
  "mediano (10k-40k)": "Mediano (10k-40k)",
  "largo (40k-100k)": "Largo (40k-100k)",
  "epico (100k+)": "Épico (100k+)",
  sin_clasificar: "Sin clasificar",
};

export function Perfil() {
  const fics = useFetch(() => api.fics.list({ limit: 200, orden: "ultima_lectura" }));

  return (
    <div>
      <CabeceraPerfil />
      <Graficos />

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

function CabeceraPerfil() {
  const perfil = useFetch(() => api.perfil.get());
  const [version, setVersion] = useState(0);
  const portadaInput = useRef(null);
  const avatarInput = useRef(null);

  async function subir(tipo, archivo) {
    if (!archivo) return;
    try {
      await api.perfil.subirImagen(tipo, archivo);
      setVersion((v) => v + 1);
      perfil.reload();
    } catch (err) {
      alert(err.message);
    }
  }

  const conCache = (url) => `${url}${url.includes("?") ? "&" : "?"}v=${version}`;

  return (
    <div className="arv-perfil-header">
      <div
        className="arv-perfil-portada"
        style={
          perfil.data?.tiene_portada
            ? { backgroundImage: `url(${conCache(api.perfil.imagenUrl("portada"))})` }
            : undefined
        }
      >
        <button
          className="arv-perfil-editar arv-perfil-editar-portada"
          onClick={() => portadaInput.current.click()}
          aria-label="Cambiar portada"
        >
          <Camera size={15} />
        </button>
        <input
          ref={portadaInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(e) => subir("portada", e.target.files[0])}
        />
      </div>
      <div className="arv-perfil-avatar-wrap">
        <div
          className="arv-perfil-avatar"
          style={
            perfil.data?.tiene_avatar
              ? { backgroundImage: `url(${conCache(api.perfil.imagenUrl("avatar"))})` }
              : undefined
          }
        >
          {!perfil.data?.tiene_avatar && <User size={32} />}
        </div>
        <button
          className="arv-perfil-editar arv-perfil-editar-avatar"
          onClick={() => avatarInput.current.click()}
          aria-label="Cambiar foto de perfil"
        >
          <Camera size={13} />
        </button>
        <input
          ref={avatarInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(e) => subir("avatar", e.target.files[0])}
        />
      </div>
    </div>
  );
}

function Graficos() {
  const porAnio = useFetch(() => api.stats.palabrasPorAnio());
  const longitud = useFetch(() => api.stats.distribucionLongitud());
  const wipCompletos = useFetch(() => api.stats.ratioWipCompletos());

  const maxAnio = Math.max(1, ...(porAnio.data?.map((p) => p.palabras) ?? [1]));
  const maxLongitud = Math.max(1, ...(longitud.data?.map((b) => b.total) ?? [1]));
  const totalWipCompletos = (wipCompletos.data?.completos ?? 0) + (wipCompletos.data?.wip ?? 0);

  return (
    <div className="arv-card">
      <h3>Gráficos</h3>

      <p className="arv-muted" style={{ marginBottom: 4 }}>Palabras leídas por año</p>
      {porAnio.loading && <Cargando />}
      {porAnio.data?.map((p) => (
        <div className="arv-bar-row" key={p.periodo}>
          <span style={{ flex: "0 0 15%" }}>{p.periodo}</span>
          <div className="arv-bar-track">
            <div className="arv-bar-fill" style={{ width: `${(p.palabras / maxAnio) * 100}%` }} />
          </div>
          <span className="arv-muted">{(p.palabras / 1000).toFixed(0)}k</span>
        </div>
      ))}
      {porAnio.data?.length === 0 && <p className="arv-muted">Sin datos todavía.</p>}

      <p className="arv-muted" style={{ margin: "16px 0 4px" }}>Distribución por longitud</p>
      {longitud.loading && <Cargando />}
      {longitud.data?.map(({ bucket, total }) => (
        <div className="arv-bar-row" key={bucket}>
          <span style={{ flex: "0 0 35%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {BUCKET_LABEL[bucket] ?? bucket}
          </span>
          <div className="arv-bar-track">
            <div className="arv-bar-fill" style={{ width: `${(total / maxLongitud) * 100}%` }} />
          </div>
          <span className="arv-muted">{total}</span>
        </div>
      ))}

      <p className="arv-muted" style={{ margin: "16px 0 4px" }}>Completos vs. WIP</p>
      {wipCompletos.data && totalWipCompletos > 0 && (
        <div className="arv-bar-row">
          <span style={{ flex: "0 0 35%" }}>Completos</span>
          <div className="arv-bar-track">
            <div
              className="arv-bar-fill"
              style={{ width: `${(wipCompletos.data.completos / totalWipCompletos) * 100}%` }}
            />
          </div>
          <span className="arv-muted">{wipCompletos.data.completos}</span>
        </div>
      )}
      {wipCompletos.data && totalWipCompletos > 0 && (
        <div className="arv-bar-row">
          <span style={{ flex: "0 0 35%" }}>WIP</span>
          <div className="arv-bar-track">
            <div
              className="arv-bar-fill"
              style={{ width: `${(wipCompletos.data.wip / totalWipCompletos) * 100}%` }}
            />
          </div>
          <span className="arv-muted">{wipCompletos.data.wip}</span>
        </div>
      )}
    </div>
  );
}
