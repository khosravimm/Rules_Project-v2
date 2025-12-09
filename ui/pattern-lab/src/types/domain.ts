export type Timeframe = "4h" | "5m";

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export type PatternDirection = "long" | "short" | "neutral" | "up" | "down" | "flat";

export interface PatternHit {
  pattern_id: string;
  pattern_type?: string;
  direction?: PatternDirection | null;
  start_ts?: string | null;
  end_ts?: string | null;
  entry_candle_ts?: string | null;
  accuracy?: number | null;
  support?: number | null;
  lift?: number | null;
  stability?: number | null;
  strength_level?: string | null;
}

export interface PatternMeta {
  pattern_id: string;
  symbol: string;
  timeframe_origin?: string | null;
  pattern_type?: string | null;
  name?: string | null;
  description?: string | null;
  tags: string[];
  strength_level?: string | null;
  status?: string | null;
  support?: number | null;
  lift?: number | null;
  stability?: number | null;
}

export interface CandidateOccurrence {
  start_ts: string;
  end_ts: string;
  entry_candle_ts: string;
  label_next_dir?: PatternDirection | null;
  pnl_rr?: number | null;
  similarity: number;
}

export interface CandidateSummary {
  symbol: string;
  timeframe: Timeframe;
  num_candles: number;
  direction_hint?: PatternDirection | null;
  approx_support: number;
  approx_winrate?: number | null;
}

export interface CandidateSearchResult {
  candidate_summary: CandidateSummary;
  occurrences: CandidateOccurrence[];
}

export interface FiltersState {
  patternTypes: string[];
  direction: "all" | "long" | "short";
  strengths: string[];
  start?: string | null;
  end?: string | null;
}
