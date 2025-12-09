import { useEffect, useState } from "react";
import { fetchPatternHits } from "../services/api";
import { useAppStore } from "../store/useAppStore";
import { PatternHit } from "../types/domain";

export const usePatternHits = (refreshKey = 0) => {
  const { timeframe, filters, setPatternHits, dateRange } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchPatternHits(timeframe, {
          patternType: filters.patternTypes.length === 1 ? filters.patternTypes[0] : undefined,
          direction: filters.direction !== "all" ? filters.direction : undefined,
          start: dateRange.start,
          end: dateRange.end,
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
    dateRange.start,
    dateRange.end,
    setPatternHits,
    refreshKey,
  ]);

  return { loading, error, hits: useAppStore.getState().patternHits as PatternHit[] };
};
