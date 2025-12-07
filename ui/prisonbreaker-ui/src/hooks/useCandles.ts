import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchCandles, fetchPatternHits } from '../api/candles';
import type {
  Candle,
  PatternHit,
  SymbolPair,
  Timeframe,
} from '../types/trading';

export interface UseCandlesOptions {
  symbol: SymbolPair;
  timeframe: Timeframe;
  autoRefreshMs?: number;
}

export interface UseCandlesResult {
  candles: Candle[];
  patternHits: PatternHit[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useCandles(options: UseCandlesOptions): UseCandlesResult {
  const { symbol, timeframe, autoRefreshMs = 0 } = options;
  const [candles, setCandles] = useState<Candle[]>([]);
  const [patternHits, setPatternHits] = useState<PatternHit[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const load = useMemo(
    () => async () => {
      setLoading(true);
      setError(null);
      try {
        const [cResp, pResp] = await Promise.all([
          fetchCandles(symbol, timeframe),
          fetchPatternHits(symbol, timeframe),
        ]);
        if (!mountedRef.current) return;
        setCandles(cResp.candles || []);
        setPatternHits(pResp.hits || []);
      } catch (err) {
        if (!mountedRef.current) return;
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [symbol, timeframe],
  );

  useEffect(() => {
    mountedRef.current = true;
    load();
    let interval: number | undefined;
    if (autoRefreshMs && autoRefreshMs > 0) {
      interval = window.setInterval(() => {
        load();
      }, autoRefreshMs);
    }
    return () => {
      mountedRef.current = false;
      if (interval) {
        window.clearInterval(interval);
      }
    };
  }, [load, autoRefreshMs]);

  return {
    candles,
    patternHits,
    loading,
    error,
    reload: load,
  };
}
