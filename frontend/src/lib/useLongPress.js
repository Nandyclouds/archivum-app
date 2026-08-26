import { useCallback, useRef } from "react";

const UMBRAL_MS = 500;
const TOLERANCIA_PX = 10;

/** Detecta mantener apretado (vs. un tap normal) con Pointer Events, para
 * entrar a modo selección en una lista sin robarle el click normal (que
 * sigue navegando) ni romper el scroll (se cancela si el dedo se mueve). */
export function useLongPress(onLongPress, onClick) {
  const timerRef = useRef(null);
  const disparadoRef = useRef(false);
  const inicioRef = useRef({ x: 0, y: 0 });

  const limpiar = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const onPointerDown = useCallback(
    (e) => {
      disparadoRef.current = false;
      inicioRef.current = { x: e.clientX, y: e.clientY };
      timerRef.current = setTimeout(() => {
        disparadoRef.current = true;
        timerRef.current = null;
        onLongPress();
      }, UMBRAL_MS);
    },
    [onLongPress]
  );

  const onPointerMove = useCallback(
    (e) => {
      if (!timerRef.current) return;
      const dx = e.clientX - inicioRef.current.x;
      const dy = e.clientY - inicioRef.current.y;
      if (Math.hypot(dx, dy) > TOLERANCIA_PX) limpiar();
    },
    [limpiar]
  );

  const onClickCapturado = useCallback(
    (e) => {
      if (disparadoRef.current) {
        e.preventDefault();
        disparadoRef.current = false;
        return;
      }
      onClick?.(e);
    },
    [onClick]
  );

  return {
    onPointerDown,
    onPointerUp: limpiar,
    onPointerLeave: limpiar,
    onPointerMove,
    onClick: onClickCapturado,
  };
}
