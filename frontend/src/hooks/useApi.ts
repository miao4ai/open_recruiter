import { useCallback, useEffect, useState } from "react";

/**
 * Generic hook for fetching data from the API.
 * Returns { data, loading, error, refresh }.
 */
export function useApi<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    fetcher()
      .then(setData)
      .catch((e) => setError(e?.message ?? "Unknown error"))
      .finally(() => setLoading(false));
  }, [fetcher]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { data, loading, error, refresh };
}
