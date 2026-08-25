import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga } from "../components/EstadoCarga";

export function Panel() {
  const { t } = useTranslation();
  const [anio, setAnio] = useState("");

  const resumen = useFetch(() => api.stats.resumen(anio || undefined), [anio]);
  const anios = useFetch(() => api.stats.palabrasPorAnio());
  const topFandoms = useFetch(() => api.stats.topFandoms(6, anio || undefined), [anio]);
  const topShips = useFetch(() => api.stats.topShips(6, "romantico", anio || undefined), [anio]);
  const topRelaciones = useFetch(() => api.stats.topShips(6, "platonico", anio || undefined), [anio]);
  const estadoLectura = useFetch(() => api.stats.estadoLectura());
  const recientes = useFetch(() => api.fics.list({ limit: 8, orden: "recientes" }));

  if (resumen.loading) return <Cargando />;
  if (resumen.error) return <ErrorCarga error={resumen.error} onReintentar={resumen.reload} />;

  const r = resumen.data;
  const maxFandom = topFandoms.data?.[0]?.total ?? 1;
  const aniosDisponibles = (anios.data ?? []).map((p) => p.periodo).sort().reverse();
  const anioQuery = anio ? `?anio=${anio}` : "";

  return (
    <div>
      <div className="arv-card">
        <p className="arv-muted" style={{ marginBottom: 4 }}>
          {r.racha_dias > 0 ? t("panel.racha", { count: r.racha_dias }) : t("panel.sinRacha")}
        </p>
      </div>

      <div className="arv-grid-2" style={{ marginBottom: 14 }}>
        <Link to={`/panel/top/palabras${anioQuery}`} className="arv-stat arv-row-link">
          <div className="label">{t("panel.palabras")}</div>
          <div className="value">{formatoCompacto(r.total_palabras_leidas)}</div>
        </Link>
        <Link to="/buscar?estado=leido" className="arv-stat arv-row-link">
          <div className="label">{t("panel.ficsLeidos")}</div>
          <div className="value">{r.total_lecturas_leido}</div>
        </Link>
        <div className="arv-stat">
          <div className="label">{t("panel.fandoms")}</div>
          <div className="value">{r.total_fandoms}</div>
        </div>
        <div className="arv-stat">
          <div className="label">{t("panel.ships")}</div>
          <div className="value">{r.total_ships}</div>
        </div>
      </div>

      {aniosDisponibles.length > 0 && (
        <div className="arv-scrollnav" style={{ marginBottom: 14 }}>
          <button className={`arv-tab${anio === "" ? " active" : ""}`} onClick={() => setAnio("")}>
            {t("panel.todosLosAnios")}
          </button>
          {aniosDisponibles.map((a) => (
            <button
              key={a}
              className={`arv-tab${anio === a ? " active" : ""}`}
              onClick={() => setAnio(a === anio ? "" : a)}
            >
              {a}
            </button>
          ))}
        </div>
      )}

      <div className="arv-card">
        <h3>
          <Link to={`/panel/top/fandoms${anioQuery}`} className="arv-row-link">
            {anio ? t("panel.topFandomsEnAnio", { anio }) : t("panel.topFandoms")}
          </Link>
        </h3>
        {topFandoms.loading && <Cargando />}
        {topFandoms.data?.length === 0 && (
          <p className="arv-muted">
            {anio ? t("panel.sinFicsLeidosEnAnio", { anio }) : t("panel.todaviaNoHayFics")}
          </p>
        )}
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
        <h3>{t("panel.estadoDeLectura")}</h3>
        {estadoLectura.loading && <Cargando />}
        {estadoLectura.data &&
          Object.entries(estadoLectura.data).map(([estado, total]) => (
            <Link to={`/buscar?estado=${estado}`} className="arv-list-item arv-row-link" key={estado}>
              <span>{t(`panel.estadoLabel.${estado}`, estado)}</span>
              <strong>{total}</strong>
            </Link>
          ))}
        {estadoLectura.data && Object.keys(estadoLectura.data).length === 0 && (
          <p className="arv-muted">{t("panel.sinEstadoMarcado")}</p>
        )}
      </div>

      <div className="arv-card">
        <h3>
          <Link to={`/panel/top/romantico${anioQuery}`} className="arv-row-link">
            {anio ? t("panel.shipsFavoritosEnAnio", { anio }) : t("panel.shipsFavoritos")}
          </Link>
        </h3>
        {topShips.loading && <Cargando />}
        {topShips.data?.map((s) => (
          <Link to={`/buscar?ship=${encodeURIComponent(s.nombre)}`} className="arv-list-item arv-row-link" key={s.nombre}>
            <span>{s.nombre}</span>
            <span className="arv-muted">×{s.total}</span>
          </Link>
        ))}
        {topShips.data?.length === 0 && (
          <p className="arv-muted">{anio ? t("panel.sinShipsEnAnio", { anio }) : t("panel.sinShips")}</p>
        )}
      </div>

      <div className="arv-card">
        <h3>
          <Link to={`/panel/top/platonico${anioQuery}`} className="arv-row-link">
            {anio ? t("panel.relacionesFavoritasEnAnio", { anio }) : t("panel.relacionesFavoritas")}
          </Link>
        </h3>
        {topRelaciones.loading && <Cargando />}
        {topRelaciones.data?.map((s) => (
          <Link to={`/buscar?ship=${encodeURIComponent(s.nombre)}`} className="arv-list-item arv-row-link" key={s.nombre}>
            <span>{s.nombre}</span>
            <span className="arv-muted">×{s.total}</span>
          </Link>
        ))}
        {topRelaciones.data?.length === 0 && (
          <p className="arv-muted">{anio ? t("panel.sinRelacionesEnAnio", { anio }) : t("panel.sinRelaciones")}</p>
        )}
      </div>

      <div className="arv-card">
        <h3>{t("panel.agregadosRecientemente")}</h3>
        {recientes.loading && <Cargando />}
        {recientes.data?.length === 0 && <p className="arv-muted">{t("panel.todaviaNoHayFics")}</p>}
        {recientes.data?.map((f) => (
          <Link key={f.id} to={`/fics/${f.id}`} className="arv-fic-row">
            <div>
              <div className="fandom">{f.fandoms[0]?.nombre ?? t("common.sinFandom")}</div>
              <div className="titulo">{f.titulo}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function formatoCompacto(numero) {
  if (numero >= 1_000_000) return `${(numero / 1_000_000).toFixed(1)}M`;
  if (numero >= 1_000) return `${(numero / 1_000).toFixed(1)}k`;
  return String(numero);
}
