import { useTranslation } from "react-i18next";

export function Cargando() {
  const { t } = useTranslation();
  return <p className="arv-muted">{t("common.cargando")}</p>;
}

export function ErrorCarga({ error, onReintentar }) {
  const { t } = useTranslation();
  return (
    <div className="arv-card">
      <p className="arv-muted">{t("common.errorApi", { msg: error.message })}</p>
      {onReintentar && (
        <button className="arv-btn arv-btn-secondary" onClick={onReintentar}>
          {t("common.reintentar")}
        </button>
      )}
    </div>
  );
}

export function Vacio({ children }) {
  return <div className="arv-empty">{children}</div>;
}
