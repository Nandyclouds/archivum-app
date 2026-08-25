import { useEffect, useRef } from "react";
import twemoji from "@twemoji/api";

/** Reemplaza los emojis de Unicode dentro del texto por los dibujos de
 * Twemoji — mismo look "lindo" en cualquier celu, en vez del emoji nativo
 * (que varía según el teléfono y en algunos Android se ve chato/feo).
 * Opera sobre el DOM ya renderizado (twemoji.parse camina los nodos de
 * texto), no arma HTML a mano, así que es seguro con texto que escribió la
 * usuaria — no hay riesgo de inyectar nada. */
export function ConEmoji({ as: Tag = "span", children, ...props }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) {
      twemoji.parse(ref.current, { folder: "svg", ext: ".svg" });
    }
  });

  return (
    <Tag ref={ref} {...props}>
      {children}
    </Tag>
  );
}
