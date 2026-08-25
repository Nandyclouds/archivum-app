import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { StickyNote } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { ImportarPorUrl } from "../components/ImportarPorUrl";
import { MultiSelect } from "../components/MultiSelect";

export function Buscar() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get("q") || "";
  const fandom = searchParams.get("fandom") || "";
  const ship = searchParams.getAll("ship");
  const etiqueta = searchParams.get("etiqueta") || "";
  const personaje = searchParams.getAll("personaje");
  const tag = searchParams.getAll("tag");
  const rating = searchParams.get("rating") || "";
  const warning = searchParams.get("warning") || "";
  const categoria = searchParams.get("categoria") || "";
  const idioma = searchParams.get("idioma") || "";
  const estado = searchParams.get("estado") || "";
  const completo = searchParams.get("completo"); // "true" | "false" | null
  const conNota = searchParams.get("con_nota") === "1";

  function setFiltro(clave, valor) {
    const next = new URLSearchParams(searchParams);
    if (valor) next.set(clave, valor);
    else next.delete(clave);
    setSearchParams(next, { replace: true });
  }

  function setFiltroMulti(clave, valores) {
    const next = new URLSearchParams(searchParams);
    next.delete(clave);
    for (const v of valores) next.append(clave, v);
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
        categoria,
        idioma,
        estado,
        ...(completo !== null ? { completo } : {}),
        ...(conNota ? { con_nota: true } : {}),
        limit: 100,
      }),
    [
      q,
      fandom,
      ship.join(","),
      etiqueta,
      personaje.join(","),
      tag.join(","),
      rating,
      warning,
      categoria,
      idioma,
      estado,
      completo,
      conNota,
    ]
  );

  const hayFiltrosExtra =
    ship.length > 0 ||
    etiqueta ||
    personaje.length > 0 ||
    tag.length > 0 ||
    rating ||
    warning ||
    categoria ||
    idioma ||
    estado ||
    completo !== null ||
    conNota;

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

      <div style={{ marginBottom: 10 }}>
        <MultiSelect
          opciones={opciones.data?.ships}
          seleccionados={ship}
          onChange={(v) => setFiltroMulti("ship", v)}
          placeholder={t("buscar.relationshipPlaceholder")}
        />
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <MultiSelect
          opciones={opciones.data?.personajes}
          seleccionados={personaje}
          onChange={(v) => setFiltroMulti("personaje", v)}
          placeholder={t("buscar.personajePlaceholder")}
        />
        <MultiSelect
          opciones={opciones.data?.tags}
          seleccionados={tag}
          onChange={(v) => setFiltroMulti("tag", v)}
          placeholder={t("buscar.tagPlaceholder")}
        />
      </div>

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

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <select
          className="arv-input"
          style={{ flex: 1, minWidth: 0 }}
          value={categoria}
          onChange={(e) => setFiltro("categoria", e.target.value)}
        >
          <option value="">{t("buscar.categoria")}</option>
          {opciones.data?.categorias.map((c) => (
            <option value={c} key={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="arv-input"
          style={{ flex: 1, minWidth: 0 }}
          value={idioma}
          onChange={(e) => setFiltro("idioma", e.target.value)}
        >
          <option value="">{t("buscar.idioma")}</option>
          {opciones.data?.idiomas.map((i) => (
            <option value={i} key={i}>
              {i}
            </option>
          ))}
        </select>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10, alignItems: "center" }}>
        <div className="arv-segmentado" style={{ width: "fit-content" }}>
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
        <button
          className={`arv-icon-btn${conNota ? " active" : ""}`}
          onClick={() => setFiltro("con_nota", conNota ? "" : "1")}
          aria-label={t("buscar.conNota")}
          title={t("buscar.conNota")}
          style={conNota ? { background: "var(--color-accent)", color: "var(--color-surface)" } : undefined}
        >
          <StickyNote size={16} />
        </button>
      </div>

      {hayFiltrosExtra && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10, alignItems: "center" }}>
          {etiqueta && <span className="arv-tag arv-tag-accent-2">{etiqueta}</span>}
          {rating && <span className="arv-tag arv-tag-accent-2">{rating}</span>}
          {warning && <span className="arv-tag arv-tag-accent-2">{warning}</span>}
          {categoria && <span className="arv-tag arv-tag-accent-2">{categoria}</span>}
          {idioma && <span className="arv-tag arv-tag-accent-2">{idioma}</span>}
          {estado && <span className="arv-tag arv-tag-accent-2">{t(`buscar.estadoLabel.${estado}`, estado)}</span>}
          {completo !== null && (
            <span className="arv-tag arv-tag-accent-2">{completo === "true" ? t("buscar.completos") : t("buscar.wip")}</span>
          )}
          {conNota && <span className="arv-tag arv-tag-accent-2">{t("buscar.conNota")}</span>}
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
            <div style={{ minWidth: 0 }}>
              <div className="fandom">{fic.fandoms[0]?.nombre ?? t("common.sinFandom")}</div>
              <div className="titulo">{fic.titulo}</div>
              {conNota && fic.nota_bookmark && (
                <div
                  className="arv-muted"
                  style={{
                    fontStyle: "italic",
                    fontSize: 12.5,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  “{fic.nota_bookmark}”
                </div>
              )}
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
