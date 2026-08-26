import { useState } from "react";
import { ChevronDown } from "lucide-react";

/** Botón que despliega una lista vertical de opciones (selección única) en
 * vez de una fila que corre horizontalmente — para fandom/etiqueta en
 * Buscar, donde puede haber decenas de opciones y una nube de chips queda
 * desordenada. */
export function SelectorDesplegable({ placeholder, valor, etiquetaValor, opciones, renderOpcion, onChange }) {
  const [abierto, setAbierto] = useState(false);

  function elegir(v) {
    onChange(v);
    setAbierto(false);
  }

  return (
    <div className="arv-selector-desplegable">
      <button
        type="button"
        className={`arv-selector-desplegable-boton${valor ? " arv-selector-desplegable-boton-activo" : ""}`}
        onClick={() => setAbierto((v) => !v)}
      >
        <span>{valor ? etiquetaValor : placeholder}</span>
        <ChevronDown size={15} style={{ transform: abierto ? "rotate(180deg)" : undefined, flex: "none" }} />
      </button>
      {abierto && (
        <div className="arv-selector-desplegable-lista">
          <button
            type="button"
            className={`arv-selector-desplegable-item${!valor ? " activo" : ""}`}
            onClick={() => elegir("")}
          >
            {placeholder}
          </button>
          {opciones.map((o) => (
            <button
              key={o.valor}
              type="button"
              className={`arv-selector-desplegable-item${valor === o.valor ? " activo" : ""}`}
              onClick={() => elegir(o.valor === valor ? "" : o.valor)}
            >
              {renderOpcion ? renderOpcion(o) : o.etiqueta}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
