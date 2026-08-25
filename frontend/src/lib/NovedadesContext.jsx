import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

const NovedadesContext = createContext(null);

export function NovedadesProvider({ children }) {
  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);

  const recargar = useCallback(() => {
    setCargando(true);
    return api.novedades
      .list()
      .then(setLista)
      .finally(() => setCargando(false));
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  return (
    <NovedadesContext.Provider value={{ lista, cargando, recargar }}>{children}</NovedadesContext.Provider>
  );
}

export function useNovedades() {
  return useContext(NovedadesContext);
}
