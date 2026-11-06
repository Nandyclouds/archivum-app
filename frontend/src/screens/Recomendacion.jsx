import { useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { getToken } from "../lib/auth";
import { abrirEnNavegadorExterno } from "../lib/abrirExterno";
import { Cargando } from "../components/EstadoCarga";

export function Recomendacion() {
  const { t } = useTranslation();
  const { token } = useParams();
  const lista = useFetch(() => api.recomendaciones.get(token), [token]);
  const estaLogueada = !!getToken();
  const [estadoTodos, setEstadoTodos] = useState("idle"); // idle | agregando | hecho | error
  const [mensajeTodos, setMensajeTodos] = useState("");

  async function agregarTodos() {
    setEstadoTodos("agregando");
    try {
      const ficIds = lista.data.fics.map((f) => f.id);
      const resultado = await api.recomendaciones.importar(token, ficIds);
      setMensajeTodos(
        t("recomendacion.resultadoImportar", {
          nuevos: resultado.importados,
          yaTenia: resultado.ya_en_biblioteca,
        })
      );
      setEstadoTodos("hecho");
    } catch (err) {
      setMensajeTodos(t("recomendacion.errorAgregar", { msg: err.message }));
      setEstadoTodos("error");
    }
  }

  return (
    <div className="arv-reco-page">
      <div className="arv-reco-header">
        <h2 className="arv-reco-marca">Archivum</h2>
      </div>

      {lista.loading && <Cargando />}

      {lista.error && (
        <div className="arv-card">
          <p className="arv-muted">
            {lista.error.message?.startsWith("404")
              ? t("recomendacion.noExiste")
              : t("common.errorApi", { msg: lista.error.message })}
          </p>
        </div>
      )}

      {lista.data && (
        <>
          {lista.data.titulo && <h1 className="arv-reco-titulo">{lista.data.titulo}</h1>}
          {lista.data.nota && <p className="arv-reco-nota">“{lista.data.nota}”</p>}

          {estaLogueada && lista.data.fics.length > 1 && (
            <div className="arv-reco-agregar-todos">
              <button className="arv-btn" disabled={estadoTodos === "agregando"} onClick={agregarTodos}>
                {estadoTodos === "agregando" ? t("recomendacion.agregando") : t("recomendacion.agregarTodosALecturas")}
              </button>
              {mensajeTodos && <p className="arv-muted">{mensajeTodos}</p>}
            </div>
          )}
          {!estaLogueada && (
            <p className="arv-muted arv-reco-aviso-login">{t("recomendacion.iniciaSesionParaAgregar")}</p>
          )}

          {lista.data.fics.map((fic, i) => (
            <FicRecomendado fic={fic} token={token} estaLogueada={estaLogueada} key={i} />
          ))}
        </>
      )}

      <p className="arv-reco-footer">{t("recomendacion.hechoCon")}</p>
    </div>
  );
}

function FicRecomendado({ fic, token, estaLogueada }) {
  const { t } = useTranslation();
  const [estado, setEstado] = useState("idle"); // idle | agregando | hecho | error
  const [error, setError] = useState(null);
  const otrosTags = [
    ...fic.fandoms.map((f) => f.nombre),
    ...fic.ships.map((s) => s.nombre),
    ...fic.personajes.map((p) => p.nombre),
    ...fic.tags_adicionales.map((tg) => tg.nombre),
  ];

  async function agregar() {
    setEstado("agregando");
    setError(null);
    try {
      await api.recomendaciones.importar(token, [fic.id]);
      setEstado("hecho");
    } catch (err) {
      setEstado("error");
      setError(err.message);
    }
  }

  return (
    <div className="arv-reco-fic">
      <a href={fic.url} target="_blank" rel="noreferrer" className="arv-reco-fic-titulo">
        {fic.titulo}
      </a>
      <div className="arv-reco-fic-autor">{t("ficDetalle.por", { autor: fic.autor })}</div>

      {(fic.rating || fic.categorias.length > 0 || fic.warnings.length > 0) && (
        <div className="arv-reco-fic-tags">
          {fic.rating && <span className="arv-tag arv-tag-accent">{fic.rating}</span>}
          {fic.categorias.map((c) => (
            <span className="arv-tag arv-tag-accent" key={c}>
              {c}
            </span>
          ))}
          {fic.warnings.map((w) => (
            <span className="arv-tag arv-tag-accent" key={w}>
              {w}
            </span>
          ))}
        </div>
      )}

      {fic.summary && <p className="arv-reco-fic-resumen">{fic.summary}</p>}

      {otrosTags.length > 0 && (
        <div className="arv-reco-fic-tags">
          {otrosTags.map((nombre, i) => (
            <span className="arv-tag arv-tag-accent-2" key={i}>
              {nombre}
            </span>
          ))}
        </div>
      )}

      <div className="arv-reco-fic-footer">
        <span>
          {fic.word_count.toLocaleString()} {t("common.palabras")} · {fic.chapters_published}/
          {fic.chapters_total ?? "?"} · {fic.complete ? t("buscar.completos") : t("buscar.wip")}
          {fic.idioma ? ` · ${fic.idioma}` : ""}
        </span>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <a href={fic.url} target="_blank" rel="noreferrer" className="arv-btn arv-btn-secondary arv-reco-fic-link">
            {t("ficDetalle.verEnAo3")}
          </a>
          {fic.tiene_copia_html && (
            <button
              className="arv-btn arv-btn-secondary arv-reco-fic-link"
              onClick={() => abrirEnNavegadorExterno(api.recomendaciones.copiaArchivadaUrl(token, fic.id))}
            >
              {t("recomendacion.verCopiaArchivada")}
            </button>
          )}
          {estaLogueada && (
            <button
              className={`arv-btn arv-btn-secondary arv-reco-fic-link${
                estado === "hecho" ? " arv-reco-fic-link-hecho" : ""
              }`}
              disabled={estado === "agregando" || estado === "hecho"}
              onClick={agregar}
            >
              {estado === "hecho" ? `✓ ${t("recomendacion.agregado")}` : t("recomendacion.agregarALecturas")}
            </button>
          )}
        </div>
      </div>
      {error && (
        <p className="arv-muted" style={{ color: "var(--color-accent)", marginTop: 8, marginBottom: 0 }}>
          {t("recomendacion.errorAgregar", { msg: error })}
        </p>
      )}
    </div>
  );
}
