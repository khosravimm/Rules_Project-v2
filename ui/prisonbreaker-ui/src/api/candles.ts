import { apiGet } from './client';
import type { CandlesResponse, PatternHitsResponse, SymbolPair, Timeframe } from '../types/trading';

export function fetchCandles(symbol: SymbolPair, timeframe: Timeframe): Promise<CandlesResponse> {
  const url = `/api/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
  return apiGet<CandlesResponse>(url);
}

export function fetchPatternHits(symbol: SymbolPair, timeframe: Timeframe): Promise<PatternHitsResponse> {
  const url = `/api/pattern-hits?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
  return apiGet<PatternHitsResponse>(url);
}
