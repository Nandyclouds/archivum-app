import { useNavigate } from "react-router-dom";
import { Check } from "lucide-react";
import { useLongPress } from "../lib/useLongPress";

/** Fila de fic que navega con un tap normal, y con mantener apretado entra
 * en modo selección (para acciones en lote — ver BarraAccionesMasivas). Una
 * vez en modo selección, un tap normal en cualquier fila alterna su check
 * en vez de navegar. */
export function FilaFicSeleccionable({
  ficId,
  to,
  seleccionActiva,
  seleccionado,
  onLongPress,
  onToggle,
  className = "arv-fic-row",
  children,
}) {
  const navigate = useNavigate();
  const handlers = useLongPress(
    () => onLongPress(ficId),
    () => {
      if (seleccionActiva) onToggle(ficId);
      else navigate(to);
    }
  );

  return (
    <div
      className={`${className}${seleccionado ? " arv-fic-row-seleccionada" : ""}`}
      style={{ cursor: "pointer", userSelect: "none" }}
      {...handlers}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", minWidth: 0 }}>
        {seleccionActiva && (
          <span className={`arv-fic-check${seleccionado ? " arv-fic-check-activo" : ""}`}>
            {seleccionado && <Check size={12} strokeWidth={3} />}
          </span>
        )}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flex: 1, minWidth: 0, gap: 10 }}>
          {children}
        </div>
      </div>
    </div>
  );
}
