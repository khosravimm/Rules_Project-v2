export type Direction = 'long' | 'short' | 'neutral';

export interface Candle {
  time: number | string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface PatternHit {
  id: string;
  time: number | string;
  direction: Direction;
  name?: string;
  strength?: string;
  extra?: Record<string, unknown>;
}

export type Timeframe = '5m' | '15m' | '1h' | '4h' | '1d';
export type SymbolPair = 'BTCUSDT' | 'ETHUSDT' | (string & {});

export interface CandlesResponse {
  symbol: SymbolPair;
  timeframe: Timeframe;
  candles: Candle[];
}

export interface PatternHitsResponse {
  symbol: SymbolPair;
  timeframe: Timeframe;
  hits: PatternHit[];
}
