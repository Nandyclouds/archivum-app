import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Info } from "lucide-react";

export function InfoPopover({ children }) {
  const [abierto, setAbierto] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const botonRef = useRef(null);
  const popoverRef = useRef(null);

  useEffect(() => {
    if (!abierto) return;

    function calcularPosicion() {
      if (!botonRef.current) return;
      const rect = botonRef.current.getBoundingClientRect();
      const ANCHO_POPOVER = 240;
      const MARGEN = 10;
      let left = rect.left;
      // no dejar que se salga por la derecha de la pantalla
      left = Math.min(left, window.innerWidth - ANCHO_POPOVER - MARGEN);
      left = Math.max(left, MARGEN);
      setPos({ top: rect.bottom + 6, left });
    }

    calcularPosicion();
    window.addEventListener("scroll", calcularPosicion, true);
    window.addEventListener("resize", calcularPosicion);

    function onClickFuera(e) {
      if (
        botonRef.current?.contains(e.target) ||
        popoverRef.current?.contains(e.target)
      ) {
        return;
      }
      setAbierto(false);
    }
    document.addEventListener("mousedown", onClickFuera);
    document.addEventListener("touchstart", onClickFuera);

    return () => {
      window.removeEventListener("scroll", calcularPosicion, true);
      window.removeEventListener("resize", calcularPosicion);
      document.removeEventListener("mousedown", onClickFuera);
      document.removeEventListener("touchstart", onClickFuera);
    };
  }, [abierto]);

  return (
    <>
      <button
        type="button"
        ref={botonRef}
        onClick={() => setAbierto((v) => !v)}
        aria-label="Más información"
        style={{
          border: "none",
          background: "var(--color-surface-2)",
          borderRadius: "50%",
          width: 22,
          height: 22,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          color: "var(--color-text-muted)",
          verticalAlign: "middle",
        }}
      >
        <Info size={13} />
      </button>
      {abierto &&
        createPortal(
          <div
            ref={popoverRef}
            className="arv-card"
            style={{
              position: "fixed",
              zIndex: 1000,
              top: pos.top,
              left: pos.left,
              width: 240,
              fontSize: 13,
              fontWeight: 400,
              boxShadow: "0 4px 20px rgba(43, 33, 24, 0.25)",
              margin: 0,
            }}
          >
            {children}
          </div>,
          document.body
        )}
    </>
  );
}
