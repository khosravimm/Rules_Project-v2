import { useEffect, useState } from "react";
import { fetchCandles } from "../services/api";
import { useAppStore } from "../store/useAppStore";
import { Candle } from "../types/domain";
import { toUtcIsoFromLocalInput } from "../utils/time";

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
            : {
                start: toUtcIsoFromLocalInput(dateRange.start),
                end: toUtcIsoFromLocalInput(dateRange.end),
                limit: timeframe === "4h" ? 10000 : 300000,
              },
        );
        if (!mounted) return;
        const sorted = [...res.candles]
          .filter((c) => c.timestamp)
          .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
        setCandles(sorted);
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
