import { useEffect, useState } from "react";
import { fetchCandles } from "../services/api";
import { useAppStore } from "../store/useAppStore";
import { Candle } from "../types/domain";

export const useCandles = (refreshKey = 0) => {
  const { timeframe, dateRange, setCandles, selectedHit } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const center = selectedHit?.entry_candle_ts || selectedHit?.end_ts || selectedHit?.start_ts || undefined;
        const res = await fetchCandles(
          timeframe,
          center
            ? { center, beforeBars: 80, afterBars: 40 }
            : { start: dateRange.start || undefined, end: dateRange.end || undefined },
        );
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
  }, [timeframe, dateRange.start, dateRange.end, setCandles, refreshKey, selectedHit?.entry_candle_ts, selectedHit?.start_ts, selectedHit?.end_ts]);

  return { loading, error, candles: useAppStore.getState().candles as Candle[] };
};
