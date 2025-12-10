import axios from "axios";
import {
  Candle,
  CandidateSearchResult,
  CandidateSummary,
  PatternHit,
  PatternMeta,
  Timeframe,
} from "../types/domain";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 15000,
});

export interface CandlesResponse {
  symbol: string;
  timeframe: string;
  candles: Candle[];
}

export interface PatternHitsResponse {
  symbol: string;
  timeframe: string;
  hits: PatternHit[];
}

export interface PatternMetaResponse {
  patterns: PatternMeta[];
}

export const fetchCandles = async (
  timeframe: Timeframe,
  opts: { start?: string; end?: string; center?: string; beforeBars?: number; afterBars?: number; limit?: number } = {},
) => {
  const params: Record<string, string | number> = { timeframe };
  if (opts.center) {
    params.center = opts.center;
    if (opts.beforeBars !== undefined) params.before_bars = opts.beforeBars;
    if (opts.afterBars !== undefined) params.after_bars = opts.afterBars;
  } else {
    if (opts.start) params.start = opts.start;
    if (opts.end) params.end = opts.end;
  }
    if (opts.limit) params.limit = opts.limit;
  const { data } = await api.get<CandlesResponse>("/api/candles", { params });
  return data;
};

export const fetchPatternHits = async (
  timeframe: Timeframe,
  filters: { patternType?: string; direction?: string; start?: string | null; end?: string | null; strength?: string; limit?: number } = {},
) => {
  const params: Record<string, string> = { timeframe };
  if (filters.patternType) params.pattern_type = filters.patternType;
  if (filters.direction && filters.direction !== "all") params.direction = filters.direction;
  if (filters.start) params.start = filters.start;
  if (filters.end) params.end = filters.end;
  if (filters.strength) params.strength_level = filters.strength;
  if (filters.limit) params.limit = String(filters.limit);
  const { data } = await api.get<PatternHitsResponse>("/api/pattern-hits", { params });
  return data;
};

export const fetchPatternMeta = async (timeframe?: Timeframe, patternId?: string) => {
  const params: Record<string, string> = {};
  if (timeframe) params.timeframe = timeframe;
  if (patternId) params.pattern_id = patternId;
  const { data } = await api.get<PatternMetaResponse>("/api/patterns/meta", { params });
  return data.patterns;
};

export const searchCandidate = async (
  timeframe: Timeframe,
  window: { start_ts: string; end_ts: string },
): Promise<CandidateSearchResult> => {
  const { data } = await api.post<CandidateSearchResult>("/api/patterns/search_candidate", {
    timeframe,
    symbol: "BTCUSDT_PERP",
    selected_window: window,
  });
  return data;
};

export const createPatternFromCandidate = async (payload: {
  timeframe: Timeframe;
  pattern_type: string;
  base_window: { start_ts: string; end_ts: string };
  name: string;
  description: string;
  tags: string[];
  initial_strength_level: string;
}) => {
  const { data } = await api.post<{ pattern: PatternMeta; candidate_summary?: CandidateSummary }>(
    "/api/patterns/create_from_candidate",
    payload,
  );
  return data;
};
