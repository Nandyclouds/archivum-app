import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

/** Resumen de un fic, recortado a 2 líneas con un "Leer más" que lo
 * despliega entero — usado en todas las listas de títulos (Buscar, panel,
 * perfil, colecciones, tops, recomendar). El toggle lleva stopPropagation
 * porque casi todas esas filas navegan al fic con cualquier click. */
export function ResumenFic({ texto }) {
  const { t } = useTranslation();
  const [expandido, setExpandido] = useState(false);
  const [truncado, setTruncado] = useState(false);
  const ref = useRef(null);

  useLayoutEffect(() => {
    if (!ref.current || expandido) return;
    setTruncado(ref.current.scrollHeight > ref.current.clientHeight + 1);
  }, [texto, expandido]);

  if (!texto) return null;

  return (
    <div>
      <div ref={ref} className={`arv-fic-resumen${expandido ? " arv-fic-resumen-abierto" : ""}`}>
        {texto}
      </div>
      {(truncado || expandido) && (
        <button
          type="button"
          className="arv-fic-resumen-toggle"
          onClick={(e) => {
            e.stopPropagation();
            e.preventDefault();
            setExpandido((v) => !v);
          }}
        >
          {expandido ? t("common.leerMenos") : t("common.leerMas")}
        </button>
      )}
    </div>
  );
}
