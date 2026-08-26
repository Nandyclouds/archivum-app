import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { FilaFicSeleccionable } from "../components/FilaFicSeleccionable";
import { BarraAccionesMasivas } from "../components/BarraAccionesMasivas";
import { useSeleccionMultiple } from "../lib/useSeleccionMultiple";

export function TopCompleto() {
  const { t } = useTranslation();
  const { tipo } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const anio = searchParams.get("anio") || "";
  const { seleccion, activa: seleccionActiva, activar, alternar, limpiar } = useSeleccionMultiple();

  const anios = useFetch(() => api.stats.palabrasPorAnio());
  const aniosDisponibles = (anios.data ?? []).map((p) => p.periodo).sort().reverse();

  const datos = useFetch(() => {
    if (tipo === "palabras") {
      // "anio" ya implica leído ese año (ver /api/fics); sin año, hay que
      // pedir estado=leido a mano o traería también pendientes/abandonados.
      return api.fics.list({
        orden: "palabras",
        limit: 500,
        ...(anio ? { anio } : { estado: "leido" }),
      });
    }
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
        <h2 style={{ marginBottom: 2 }}>
          {t(`topCompleto.titulos.${tipo}`, t("topCompleto.todos"))}
          {anio ? ` ${t("topCompleto.enAnio", { anio })}` : ""}
        </h2>
      </div>

      {aniosDisponibles.length > 0 && (
        <div className="arv-scrollnav" style={{ marginBottom: 14 }}>
          <button
            className={`arv-tab${anio === "" ? " active" : ""}`}
            onClick={() => setSearchParams({}, { replace: true })}
          >
            {t("topCompleto.todosLosAnios")}
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
      {datos.data?.length === 0 && <Vacio>{t("topCompleto.sinDatos")}</Vacio>}

      <div className="arv-card" style={tipo === "palabras" && seleccionActiva ? { marginBottom: 90 } : undefined}>
        {tipo === "palabras"
          ? datos.data?.map((fic) => (
              <FilaFicSeleccionable
                key={fic.id}
                ficId={fic.id}
                to={`/fics/${fic.id}`}
                seleccionActiva={seleccionActiva}
                seleccionado={seleccion.has(fic.id)}
                onLongPress={activar}
                onToggle={alternar}
              >
                <div>
                  <div className="fandom">{fic.fandoms[0]?.nombre ?? t("common.sinFandom")}</div>
                  <div className="titulo">{fic.titulo}</div>
                </div>
                <div className="meta" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {fic.word_count.toLocaleString()} {t("common.palabras")}
                </div>
              </FilaFicSeleccionable>
            ))
          : datos.data?.map((d) => (
              <Link to={linkPara(d.nombre)} className="arv-list-item arv-row-link" key={d.nombre}>
                <span>{d.nombre}</span>
                <span className="arv-muted">×{d.total}</span>
              </Link>
            ))}
      </div>

      {tipo === "palabras" && seleccionActiva && (
        <BarraAccionesMasivas
          seleccionIds={seleccion}
          onLimpiar={limpiar}
          onAplicado={() => {
            limpiar();
            datos.reload();
          }}
        />
      )}
    </div>
  );
}
