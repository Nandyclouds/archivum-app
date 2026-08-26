import { useCallback, useState } from "react";

/** Estado de selección múltiple para listas de fics (Buscar, ColeccionDetalle...).
 * Mantener apretado un fic activa el modo (lo selecciona a él solo);
 * de ahí en más, tocar cualquier fic suma/saca del set. */
export function useSeleccionMultiple() {
  const [seleccion, setSeleccion] = useState(new Set());

  const activar = useCallback((id) => {
    setSeleccion(new Set([id]));
  }, []);

  const alternar = useCallback((id) => {
    setSeleccion((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const limpiar = useCallback(() => setSeleccion(new Set()), []);

  return { seleccion, activa: seleccion.size > 0, activar, alternar, limpiar };
}
