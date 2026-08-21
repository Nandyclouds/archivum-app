import { useEffect, useState, useCallback } from "react";

export function useFetch(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    let cancelado = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then((resultado) => {
        if (!cancelado) setData(resultado);
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
  }, deps);

  useEffect(() => reload(), [reload]);

  return { data, error, loading, reload };
}
