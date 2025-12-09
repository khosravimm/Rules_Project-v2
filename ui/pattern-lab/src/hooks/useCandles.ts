import { useEffect, useState } from "react";
import { fetchCandles } from "../services/api";
import { useAppStore } from "../store/useAppStore";
import { Candle } from "../types/domain";

export const useCandles = (refreshKey = 0) => {
  const { timeframe, dateRange, setCandles } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchCandles(timeframe, dateRange.start || undefined, dateRange.end || undefined);
        if (!mounted) return;
        setCandles(res.candles);
      } catch (err: any) {
        if (!mounted) return;
        setError(err?.message || "Failed to load candles");
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [timeframe, dateRange.start, dateRange.end, setCandles, refreshKey]);

  return { loading, error, candles: useAppStore.getState().candles as Candle[] };
};
