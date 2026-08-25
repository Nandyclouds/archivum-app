import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";

const EmojiPersonalizadoContext = createContext({ lista: [], mapa: {}, recargar: () => {} });

export function EmojiPersonalizadoProvider({ children }) {
  const [lista, setLista] = useState([]);

  const recargar = useCallback(() => {
    api.emojis.list().then(setLista).catch(() => {});
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  // nombre -> url de la imagen, para que <ConEmoji> resuelva :nombre: sin
  // pedirle la lista a la API en cada instancia.
  const mapa = useMemo(
    () => Object.fromEntries(lista.map((e) => [e.nombre, api.emojis.imagenUrl(e.id)])),
    [lista]
  );

  return (
    <EmojiPersonalizadoContext.Provider value={{ lista, mapa, recargar }}>
      {children}
    </EmojiPersonalizadoContext.Provider>
  );
}

export function useEmojisPersonalizados() {
  return useContext(EmojiPersonalizadoContext);
}
