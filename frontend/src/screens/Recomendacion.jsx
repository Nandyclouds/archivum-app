import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFetch } from "../lib/useFetch";
import { api } from "../lib/api";
import { Cargando } from "../components/EstadoCarga";

export function Recomendacion() {
  const { t } = useTranslation();
  const { token } = useParams();
  const lista = useFetch(() => api.recomendaciones.get(token), [token]);

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

          {lista.data.fics.map((fic, i) => (
            <FicRecomendado fic={fic} key={i} />
          ))}
        </>
      )}

      <p className="arv-reco-footer">{t("recomendacion.hechoCon")}</p>
    </div>
  );
}

function FicRecomendado({ fic }) {
  const { t } = useTranslation();
  const otrosTags = [
    ...fic.fandoms.map((f) => f.nombre),
    ...fic.ships.map((s) => s.nombre),
    ...fic.personajes.map((p) => p.nombre),
    ...fic.tags_adicionales.map((tg) => tg.nombre),
  ];

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
        <a href={fic.url} target="_blank" rel="noreferrer" className="arv-btn arv-btn-secondary arv-reco-fic-link">
          {t("ficDetalle.verEnAo3")}
        </a>
      </div>
    </div>
  );
}
