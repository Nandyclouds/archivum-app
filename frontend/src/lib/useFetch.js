import { useEffect, useState, useCallback } from "react";

// Cache en memoria del último resultado por clave — para que volver a una
// pestaña ya visitada (Perfil, Panel...) muestre al toque lo último que se
// vio, en vez de la pantalla de "Cargando" de nuevo, mientras se refresca
// solo atrás. React desmonta la pantalla entera al cambiar de tab (son
// <Route> distintas), así que sin esto cada visita repite el pedido al
// servidor de cero — y PythonAnywhere free tier no es rápido respondiendo.
// Vive mientras dure la pestaña del navegador (se pierde al recargar); es
// opt-in vía el tercer argumento, así que un llamado sin cacheKey se
// comporta exactamente igual que antes.
const cache = new Map();

export function useFetch(fetcher, deps = [], cacheKey = null) {
  const enCache = () => cacheKey != null && cache.has(cacheKey);

  const [data, setData] = useState(() => (enCache() ? cache.get(cacheKey) : null));
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(() => !enCache());

  const reload = useCallback(() => {
    let cancelado = false;
    if (enCache()) {
      // Ya hay algo para mostrar: no tapamos la pantalla con el spinner,
      // se ve la versión vieja mientras esta actualiza en segundo plano.
      setData(cache.get(cacheKey));
      setLoading(false);
    } else {
      setLoading(true);
    }
    setError(null);
    fetcher()
      .then((resultado) => {
        if (cancelado) return;
        if (cacheKey != null) cache.set(cacheKey, resultado);
        setData(resultado);
      })
      .catch((err) => {
        if (!cancelado) setError(err);
      })
      .finally(() => {
        if (!cancelado) setLoading(false);
      });
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, cacheKey]);

  useEffect(() => reload(), [reload]);

  return { data, error, loading, reload };
}
