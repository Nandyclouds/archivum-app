import { useMemo } from "react";
import twemoji from "@twemoji/api";
import { useEmojisPersonalizados } from "../lib/EmojiPersonalizadoContext";

const PATRON_SHORTCODE = /:([a-z0-9_]{2,30}):/g;

function escaparHtml(texto) {
  return texto
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function conShortcodes(htmlEscapado, mapa) {
  if (Object.keys(mapa).length === 0) return htmlEscapado;
  return htmlEscapado.replace(PATRON_SHORTCODE, (match, nombre) => {
    const url = mapa[nombre];
    if (!url) return match;
    return `<img src="${url}" alt="${match}" class="emoji emoji-personalizado" />`;
  });
}

/** Reemplaza los emojis de Unicode dentro del texto por los dibujos de
 * Twemoji — mismo look "lindo" en cualquier celu, en vez del emoji nativo
 * (que varía según el teléfono). También resuelve :shortcode: contra los
 * emojis personalizados que subiste (ver Ajustes → Emojis personalizados).
 *
 * Arma el resultado como un string de HTML (escapando primero el texto
 * propio, para que no sea un vector de inyección) y lo mete con
 * dangerouslySetInnerHTML, en vez de dejar que twemoji mute el DOM ya
 * renderizado por React directamente: eso último rompía la página con
 * "Failed to execute 'removeChild'" apenas React necesitaba re-renderizar
 * ese nodo (ej. al borrar un emoji personalizado) porque React perdía el
 * rastro de nodos que twemoji había reemplazado por su cuenta. */
export function ConEmoji({ as: Tag = "span", children, ...props }) {
  const { mapa } = useEmojisPersonalizados();

  const html = useMemo(() => {
    if (typeof children !== "string") return null;
    const conCustom = conShortcodes(escaparHtml(children), mapa);
    return twemoji.parse(conCustom, { folder: "svg", ext: ".svg" });
  }, [children, mapa]);

  if (html === null) {
    return <Tag {...props}>{children}</Tag>;
  }

  return <Tag {...props} dangerouslySetInnerHTML={{ __html: html }} />;
}
