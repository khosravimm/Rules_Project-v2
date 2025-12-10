import { useEffect, useState } from "react";
import { fetchPatternHits } from "../services/api";
import { useAppStore } from "../store/useAppStore";
import { PatternHit } from "../types/domain";

const TIMEFRAME_SECONDS: Record<string, number> = {
  "4h": 4 * 3600,
  "5m": 5 * 60,
};
const WINDOW_BEFORE = 80;
const WINDOW_AFTER = 40;

export const usePatternHits = (refreshKey = 0) => {
  const { timeframe, filters, setPatternHits, dateRange, selectedHit } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        let start = dateRange.start;
        let end = dateRange.end;
        const center = selectedHit?.entry_candle_ts || selectedHit?.end_ts || selectedHit?.start_ts;
        if (center) {
          const deltaSec = TIMEFRAME_SECONDS[timeframe] ?? 0;
          const centerDate = new Date(center);
          const startTs = new Date(centerDate.getTime() - WINDOW_BEFORE * deltaSec * 1000);
          const endTs = new Date(centerDate.getTime() + WINDOW_AFTER * deltaSec * 1000);
          start = startTs.toISOString();
          end = endTs.toISOString();
        }
        const res = await fetchPatternHits(timeframe, {
          patternType: filters.patternTypes.length === 1 ? filters.patternTypes[0] : undefined,
          direction: filters.direction !== "all" ? filters.direction : undefined,
          start,
          end,
          limit: 1500,
          strength: filters.strengths.length === 1 ? filters.strengths[0] : undefined,
        });
        if (!mounted) return;
        setPatternHits(res.hits);
      } catch (err: any) {
        if (!mounted) return;
        setError(err?.message || "Failed to load pattern hits");
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [
    timeframe,
    filters.patternTypes.join(","),
    filters.direction,
    filters.strengths.join(","),
    dateRange.start,
    dateRange.end,
    selectedHit?.entry_candle_ts,
    selectedHit?.start_ts,
    selectedHit?.end_ts,
    setPatternHits,
    refreshKey,
  ]);

  return { loading, error, hits: useAppStore.getState().patternHits as PatternHit[] };
};
