import { useEffect, useState } from "react";
import { fetchPatternMeta } from "../services/api";
import { useAppStore } from "../store/useAppStore";
import { PatternMeta, Timeframe } from "../types/domain";

export const usePatternMeta = (patternId?: string, timeframe?: Timeframe) => {
  const { setPatternMeta } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      if (!patternId && !timeframe) return;
      setLoading(true);
      setError(null);
      try {
        const meta = await fetchPatternMeta(timeframe, patternId);
        if (!mounted) return;
        setPatternMeta(meta);
      } catch (err: any) {
        if (!mounted) return;
        setError(err?.message || "Failed to load pattern metadata");
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [patternId, timeframe, setPatternMeta]);

  const currentMeta = patternId ? useAppStore.getState().patternMeta[patternId] : undefined;
  return { loading, error, meta: currentMeta as PatternMeta | undefined };
};

