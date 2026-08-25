import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { ImportarPorUrl } from "../components/ImportarPorUrl";

export function Buscar() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get("q") || "";
  const fandom = searchParams.get("fandom") || "";
  const ship = searchParams.get("ship") || "";
  const etiqueta = searchParams.get("etiqueta") || "";
  const personaje = searchParams.get("personaje") || "";
  const tag = searchParams.get("tag") || "";
  const rating = searchParams.get("rating") || "";
  const warning = searchParams.get("warning") || "";
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
  const opciones = useFetch(() => api.fics.opcionesFiltro());
  const fics = useFetch(
    () =>
      api.fics.list({
        q,
        fandom,
        ship,
        etiqueta,
        personaje,
        tag,
        rating,
        warning,
        estado,
        ...(completo !== null ? { completo } : {}),
        limit: 100,
      }),
    [q, fandom, ship, etiqueta, personaje, tag, rating, warning, estado, completo]
  );

  const hayFiltrosExtra =
    ship || etiqueta || personaje || tag || rating || warning || estado || completo !== null;

  return (
    <div>
      <ImportarPorUrl />
      <input
        className="arv-input"
        placeholder={t("buscar.buscarPlaceholder")}
        value={q}
        onChange={(e) => setFiltro("q", e.target.value)}
        style={{ marginBottom: 10 }}
      />

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <input
          key={personaje}
          className="arv-input"
          style={{ flex: 1, minWidth: 0 }}
          list="opciones-personajes"
          placeholder={t("buscar.personajePlaceholder")}
          defaultValue={personaje}
          onBlur={(e) => setFiltro("personaje", e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && setFiltro("personaje", e.target.value)}
        />
        <input
          key={tag}
          className="arv-input"
          style={{ flex: 1, minWidth: 0 }}
          list="opciones-tags"
          placeholder={t("buscar.tagPlaceholder")}
          defaultValue={tag}
          onBlur={(e) => setFiltro("tag", e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && setFiltro("tag", e.target.value)}
        />
      </div>
      <datalist id="opciones-personajes">
        {opciones.data?.personajes.map((p) => <option value={p} key={p} />)}
      </datalist>
      <datalist id="opciones-tags">
        {opciones.data?.tags.map((tagOpcion) => <option value={tagOpcion} key={tagOpcion} />)}
      </datalist>

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <select
          className="arv-input"
          style={{ flex: 1, minWidth: 0 }}
          value={rating}
          onChange={(e) => setFiltro("rating", e.target.value)}
        >
          <option value="">{t("buscar.rating")}</option>
          {opciones.data?.ratings.map((r) => (
            <option value={r} key={r}>
              {r}
            </option>
          ))}
        </select>
        <select
          className="arv-input"
          style={{ flex: 1, minWidth: 0 }}
          value={warning}
          onChange={(e) => setFiltro("warning", e.target.value)}
        >
          <option value="">{t("buscar.warnings")}</option>
          {opciones.data?.warnings.map((w) => (
            <option value={w} key={w}>
              {w}
            </option>
          ))}
        </select>
      </div>

      <div className="arv-segmentado" style={{ marginBottom: 10, width: "fit-content" }}>
        <button className={completo === null ? "active" : ""} onClick={() => setFiltro("completo", "")}>
          {t("buscar.todos")}
        </button>
        <button className={completo === "true" ? "active" : ""} onClick={() => setFiltro("completo", "true")}>
          {t("buscar.completos")}
        </button>
        <button className={completo === "false" ? "active" : ""} onClick={() => setFiltro("completo", "false")}>
          {t("buscar.wip")}
        </button>
      </div>

      {hayFiltrosExtra && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10, alignItems: "center" }}>
          {ship && <span className="arv-tag arv-tag-accent-2">{ship}</span>}
          {etiqueta && <span className="arv-tag arv-tag-accent-2">{etiqueta}</span>}
          {personaje && <span className="arv-tag arv-tag-accent-2">{personaje}</span>}
          {tag && <span className="arv-tag arv-tag-accent-2">{tag}</span>}
          {rating && <span className="arv-tag arv-tag-accent-2">{rating}</span>}
          {warning && <span className="arv-tag arv-tag-accent-2">{warning}</span>}
          {estado && <span className="arv-tag arv-tag-accent-2">{t(`buscar.estadoLabel.${estado}`, estado)}</span>}
          {completo !== null && (
            <span className="arv-tag arv-tag-accent-2">{completo === "true" ? t("buscar.completos") : t("buscar.wip")}</span>
          )}
          <button
            className="arv-tab"
            onClick={() => {
              setSearchParams({ ...(q ? { q } : {}), ...(fandom ? { fandom } : {}) }, { replace: true });
            }}
          >
            {t("buscar.limpiar")}
          </button>
        </div>
      )}

      <div className="arv-scrollnav" style={{ marginBottom: 14 }}>
        <button className={`arv-tab${fandom === "" ? " active" : ""}`} onClick={() => setFiltro("fandom", "")}>
          {t("buscar.todos")}
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
      {fics.data?.length === 0 && <Vacio>{t("buscar.sinResultados")}</Vacio>}

      <div className="arv-card">
        {fics.data?.map((fic) => (
          <Link key={fic.id} to={`/fics/${fic.id}`} className="arv-fic-row">
            <div>
              <div className="fandom">{fic.fandoms[0]?.nombre ?? t("common.sinFandom")}</div>
              <div className="titulo">{fic.titulo}</div>
            </div>
            <div className="meta" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
              {formatoCompacto(fic.word_count)}
              <br />
              {fic.estado_actual ? t(`buscar.estadoLabel.${fic.estado_actual}`, fic.estado_actual) : t("common.sinEstado")}
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
