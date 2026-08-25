import { useEffect, useRef, useState } from "react";

export function MultiSelect({ opciones, seleccionados, onChange, placeholder }) {
  const [abierto, setAbierto] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const ref = useRef(null);

  useEffect(() => {
    function onClickFuera(e) {
      if (ref.current && !ref.current.contains(e.target)) setAbierto(false);
    }
    document.addEventListener("mousedown", onClickFuera);
    return () => document.removeEventListener("mousedown", onClickFuera);
  }, []);

  function alternar(valor) {
    if (seleccionados.includes(valor)) {
      onChange(seleccionados.filter((v) => v !== valor));
    } else {
      onChange([...seleccionados, valor]);
    }
  }

  const filtradas = (opciones ?? []).filter((o) => o.toLowerCase().includes(busqueda.toLowerCase()));

  return (
    <div className="arv-multiselect" ref={ref}>
      <button
        type="button"
        className="arv-input arv-multiselect-trigger"
        onClick={() => setAbierto((v) => !v)}
      >
        <span className="arv-multiselect-trigger-label">
          {seleccionados.length > 0 ? seleccionados.join(", ") : placeholder}
        </span>
        <span className="arv-multiselect-chevron" />
      </button>

      {abierto && (
        <div className="arv-multiselect-panel">
          <input
            className="arv-input"
            style={{ marginBottom: 6 }}
            placeholder={placeholder}
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            autoFocus
          />
          <div className="arv-multiselect-lista">
            {filtradas.length === 0 && <p className="arv-muted" style={{ margin: "6px 2px" }}>—</p>}
            {filtradas.map((op) => (
              <label className="arv-multiselect-opcion" key={op}>
                <input
                  type="checkbox"
                  checked={seleccionados.includes(op)}
                  onChange={() => alternar(op)}
                />
                {op}
              </label>
            ))}
          </div>
        </div>
      )}

      {seleccionados.length > 0 && (
        <div className="arv-multiselect-chips">
          {seleccionados.map((s) => (
            <span key={s} className="arv-tag arv-tag-accent-2" style={{ display: "inline-flex", gap: 6 }}>
              {s}
              <button
                onClick={() => alternar(s)}
                style={{ border: "none", background: "transparent", cursor: "pointer", color: "inherit", padding: 0 }}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
