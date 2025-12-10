import { useEffect, useState } from "react";
import { fetchPatternHits } from "../services/api";
import { useAppStore } from "../store/useAppStore";
import { PatternHit } from "../types/domain";
import { toUtcIsoFromLocalInput } from "../utils/time";

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
        const hasPatternTypes = Array.isArray(filters.patternTypes) && filters.patternTypes.length > 0;
        const hasFilters =
          hasPatternTypes ||
          (filters.strengths && filters.strengths.length > 0) ||
          filters.direction !== "all" ||
          dateRange.start ||
          dateRange.end;
        if (!hasFilters || !hasPatternTypes) {
          setPatternHits([]);
        } else {
          const res = await fetchPatternHits(timeframe, {
            patternType: filters.patternTypes.length === 1 ? filters.patternTypes[0] : undefined,
            direction: filters.direction !== "all" ? filters.direction : undefined,
            start: toUtcIsoFromLocalInput(dateRange.start),
            end: toUtcIsoFromLocalInput(dateRange.end),
            limit: 2000,
            strength: filters.strengths.length === 1 ? filters.strengths[0] : undefined,
          });
          if (!mounted) return;
          setPatternHits(res.hits);
        }
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
    setPatternHits,
    refreshKey,
  ]);

  return { loading, error, hits: useAppStore.getState().patternHits as PatternHit[] };
};
