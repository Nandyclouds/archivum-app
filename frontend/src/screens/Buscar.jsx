import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { SlidersHorizontal, Check, Star } from "lucide-react";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando, ErrorCarga, Vacio } from "../components/EstadoCarga";
import { ConEmoji } from "../components/ConEmoji";
import { ImportarPorUrl } from "../components/ImportarPorUrl";
import { MultiSelect } from "../components/MultiSelect";
import { SelectorDesplegable } from "../components/SelectorDesplegable";
import { FilaFicSeleccionable } from "../components/FilaFicSeleccionable";
import { BarraAccionesMasivas } from "../components/BarraAccionesMasivas";
import { useSeleccionMultiple } from "../lib/useSeleccionMultiple";

export function Buscar() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filtrosAbiertos, setFiltrosAbiertos] = useState(false);
  const { seleccion, activa: seleccionActiva, activar, alternar, limpiar } = useSeleccionMultiple();
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
  const anio = searchParams.get("anio") || "";
  const ratingExacto = searchParams.get("rating_exacto") || "";
  const hizoLlorar = searchParams.get("hizo_llorar") === "1";
  const esRelectura = searchParams.get("es_relectura") === "1";
  const conResena = searchParams.get("con_resena"); // "true" | "false" | null

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

  const fandoms = useFetch(() => api.stats.topFandoms(30), [], "buscar-top-fandoms");
  const etiquetas = useFetch(() => api.etiquetas.list(), [], "buscar-etiquetas");
  const opciones = useFetch(() => api.fics.opcionesFiltro(), [], "buscar-opciones-filtro");
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
        anio,
        rating_exacto: ratingExacto,
        ...(completo !== null ? { completo } : {}),
        ...(conNota ? { con_nota: true } : {}),
        ...(hizoLlorar ? { hizo_llorar: true } : {}),
        ...(esRelectura ? { es_relectura: true } : {}),
        ...(conResena !== null ? { con_resena: conResena } : {}),
        limit: 1000,
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
      anio,
      ratingExacto,
      hizoLlorar,
      esRelectura,
      conResena,
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
    conNota ||
    anio ||
    ratingExacto ||
    hizoLlorar ||
    esRelectura ||
    conResena !== null;

  const cantidadFiltrosPanel =
    (completo !== null ? 1 : 0) +
    (conResena !== null ? 1 : 0) +
    (conNota ? 1 : 0) +
    (hizoLlorar ? 1 : 0) +
    (esRelectura ? 1 : 0) +
    (ratingExacto ? 1 : 0);

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

      <div style={{ marginBottom: 10 }}>
        <button
          type="button"
          className={`arv-filtros-toggle${cantidadFiltrosPanel > 0 ? " arv-filtros-toggle-activo" : ""}`}
          onClick={() => setFiltrosAbiertos((v) => !v)}
        >
          <SlidersHorizontal size={15} />
          {t("buscar.filtros")}
          {cantidadFiltrosPanel > 0 && <span className="arv-filtros-badge">{cantidadFiltrosPanel}</span>}
        </button>

        {filtrosAbiertos && (
          <div className="arv-filtros-panel">
            <div className="arv-filtros-fila" style={{ flexDirection: "column", alignItems: "flex-start", gap: 8 }}>
              <span className="arv-muted">{t("buscar.estado")}</span>
              <div className="arv-segmentado" style={{ width: "fit-content" }}>
                <button className={completo === null ? "active" : ""} onClick={() => setFiltro("completo", "")}>
                  {t("buscar.todos")}
                </button>
                <button
                  className={completo === "true" ? "active" : ""}
                  onClick={() => setFiltro("completo", "true")}
                >
                  {t("buscar.completos")}
                </button>
                <button
                  className={completo === "false" ? "active" : ""}
                  onClick={() => setFiltro("completo", "false")}
                >
                  {t("buscar.wip")}
                </button>
              </div>
            </div>

            <div className="arv-filtros-fila" style={{ flexDirection: "column", alignItems: "flex-start", gap: 8 }}>
              <span className="arv-muted">{t("buscar.resena")}</span>
              <div className="arv-segmentado" style={{ width: "fit-content" }}>
                <button className={conResena === null ? "active" : ""} onClick={() => setFiltro("con_resena", "")}>
                  {t("buscar.todos")}
                </button>
                <button
                  className={conResena === "true" ? "active" : ""}
                  onClick={() => setFiltro("con_resena", "true")}
                >
                  {t("buscar.conResena")}
                </button>
                <button
                  className={conResena === "false" ? "active" : ""}
                  onClick={() => setFiltro("con_resena", "false")}
                >
                  {t("buscar.sinResena")}
                </button>
              </div>
            </div>

            <div className="arv-filtros-fila" style={{ flexDirection: "column", alignItems: "flex-start", gap: 8 }}>
              <span className="arv-muted">{t("buscar.puntajeExacto")}</span>
              <div style={{ display: "inline-flex", gap: 1 }}>
                {[1, 2, 3, 4, 5].map((n) => {
                  const activo = Number(ratingExacto) === n;
                  return (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setFiltro("rating_exacto", activo ? "" : String(n))}
                      aria-label={t("buscar.ratingExacto", { count: n })}
                      title={t("buscar.ratingExacto", { count: n })}
                      style={{
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        padding: 2,
                        color: activo ? "var(--color-accent)" : "var(--color-border)",
                        display: "inline-flex",
                      }}
                    >
                      <Star size={19} fill={activo ? "currentColor" : "none"} />
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="arv-filtros-fila">
              <button
                type="button"
                className={`arv-filtros-checkbox${conNota ? " arv-filtros-checkbox-activo" : ""}`}
                onClick={() => setFiltro("con_nota", conNota ? "" : "1")}
              >
                <span className="arv-filtros-checkbox-caja">{conNota && <Check size={12} strokeWidth={3} />}</span>
                {t("buscar.conNota")}
              </button>
            </div>
            <div className="arv-filtros-fila">
              <button
                type="button"
                className={`arv-filtros-checkbox${hizoLlorar ? " arv-filtros-checkbox-activo" : ""}`}
                onClick={() => setFiltro("hizo_llorar", hizoLlorar ? "" : "1")}
              >
                <span className="arv-filtros-checkbox-caja">
                  {hizoLlorar && <Check size={12} strokeWidth={3} />}
                </span>
                {t("buscar.hizoLlorar")}
              </button>
            </div>
            <div className="arv-filtros-fila">
              <button
                type="button"
                className={`arv-filtros-checkbox${esRelectura ? " arv-filtros-checkbox-activo" : ""}`}
                onClick={() => setFiltro("es_relectura", esRelectura ? "" : "1")}
              >
                <span className="arv-filtros-checkbox-caja">
                  {esRelectura && <Check size={12} strokeWidth={3} />}
                </span>
                {t("buscar.esRelectura")}
              </button>
            </div>
          </div>
        )}
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
          {anio && <span className="arv-tag arv-tag-accent-2">{anio}</span>}
          {ratingExacto && (
            <span className="arv-tag arv-tag-accent-2">{t("buscar.ratingExacto", { count: Number(ratingExacto) })}</span>
          )}
          {hizoLlorar && <span className="arv-tag arv-tag-accent-2">{t("buscar.hizoLlorar")}</span>}
          {esRelectura && <span className="arv-tag arv-tag-accent-2">{t("buscar.esRelectura")}</span>}
          {conResena !== null && (
            <span className="arv-tag arv-tag-accent-2">
              {conResena === "true" ? t("buscar.conResena") : t("buscar.sinResena")}
            </span>
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

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <SelectorDesplegable
          placeholder={t("buscar.fandom")}
          valor={fandom}
          etiquetaValor={fandom}
          opciones={(fandoms.data ?? []).map((f) => ({ valor: f.nombre, etiqueta: f.nombre, total: f.total }))}
          onChange={(v) => setFiltro("fandom", v)}
          renderOpcion={(o) => (
            <>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {o.etiqueta}
              </span>
              <span className="arv-muted" style={{ flex: "none" }}>
                {o.total}
              </span>
            </>
          )}
        />
        {etiquetas.data?.length > 0 && (
          <SelectorDesplegable
            placeholder={t("buscar.etiqueta")}
            valor={etiqueta}
            etiquetaValor={`#${etiqueta}`}
            opciones={etiquetas.data.map((et) => ({ valor: et.nombre, etiqueta: `#${et.nombre}` }))}
            onChange={(v) => setFiltro("etiqueta", v)}
          />
        )}
      </div>

      {fics.loading && <Cargando />}
      {fics.error && <ErrorCarga error={fics.error} onReintentar={fics.reload} />}
      {fics.data?.length === 0 && <Vacio>{t("buscar.sinResultados")}</Vacio>}

      <div className="arv-card" style={seleccionActiva ? { marginBottom: 90 } : undefined}>
        {fics.data?.map((fic) => (
          <FilaFicSeleccionable
            key={fic.id}
            ficId={fic.id}
            to={`/fics/${fic.id}`}
            seleccionActiva={seleccionActiva}
            seleccionado={seleccion.has(fic.id)}
            onLongPress={activar}
            onToggle={alternar}
          >
            <div style={{ minWidth: 0 }}>
              <div className="fandom">{fic.fandoms[0]?.nombre ?? t("common.sinFandom")}</div>
              <div className="titulo">{fic.titulo}</div>
              {conNota && fic.nota_bookmark && (
                <ConEmoji
                  as="div"
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
                </ConEmoji>
              )}
            </div>
            <div className="meta" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
              {formatoCompacto(fic.word_count)}
              <br />
              {fic.estado_actual ? t(`buscar.estadoLabel.${fic.estado_actual}`, fic.estado_actual) : t("common.sinEstado")}
            </div>
          </FilaFicSeleccionable>
        ))}
      </div>

      {seleccionActiva && (
        <BarraAccionesMasivas
          seleccionIds={seleccion}
          onLimpiar={limpiar}
          onAplicado={() => {
            limpiar();
            fics.reload();
          }}
        />
      )}
    </div>
  );
}

function formatoCompacto(numero) {
  if (numero >= 1_000) return `${(numero / 1_000).toFixed(1)}k`;
  return String(numero);
}
