import { create } from "zustand";
import { Candle, CandidateSearchResult, FiltersState, PatternHit, PatternMeta, Timeframe } from "../types/domain";

type DateRange = { start?: string | null; end?: string | null };

interface AppState {
  symbol: string;
  timeframe: Timeframe;
  candles: Candle[];
  patternHits: PatternHit[];
  patternMeta: Record<string, PatternMeta>;
  selectedCandle?: Candle;
  selectedPatternId?: string;
  selectedHit?: PatternHit;
  filters: FiltersState;
  dateRange: DateRange;
  candidateWindow?: { start_ts: string; end_ts: string };
  candidateResult?: CandidateSearchResult;
  setTimeframe: (tf: Timeframe) => void;
  setCandles: (candles: Candle[]) => void;
  setPatternHits: (hits: PatternHit[]) => void;
  setPatternMeta: (meta: PatternMeta[]) => void;
  setSelectedCandle: (candle?: Candle) => void;
  setSelectedPatternId: (patternId?: string) => void;
  setSelectedHit: (hit?: PatternHit) => void;
  setFilters: (filters: Partial<FiltersState>) => void;
  setDateRange: (range: DateRange) => void;
  setCandidateWindow: (win?: { start_ts: string; end_ts: string }) => void;
  setCandidateResult: (res?: CandidateSearchResult) => void;
}

const defaultFilters: FiltersState = {
  patternTypes: ["sequence", "candle_shape", "feature_rule"],
  direction: "all",
  strengths: ["strong", "medium", "weak", "aging"],
  start: null,
  end: null,
};

export const useAppStore = create<AppState>((set) => ({
  symbol: "BTCUSDT_PERP",
  timeframe: "4h",
  candles: [],
  patternHits: [],
  patternMeta: {},
  filters: defaultFilters,
  dateRange: { start: null, end: null },
  setTimeframe: (tf) => set({ timeframe: tf }),
  setCandles: (candles) => set({ candles }),
  setPatternHits: (patternHits) => set({ patternHits }),
  setPatternMeta: (entries) =>
    set((state) => {
      const current = { ...state.patternMeta };
      entries.forEach((p) => {
        current[p.pattern_id] = p;
      });
      return { patternMeta: current };
    }),
  setSelectedCandle: (selectedCandle) => set({ selectedCandle }),
  setSelectedPatternId: (selectedPatternId) => set({ selectedPatternId }),
  setSelectedHit: (selectedHit) => set({ selectedHit }),
  setFilters: (filters) =>
    set((state) => ({
      filters: { ...state.filters, ...filters },
    })),
  setDateRange: (dateRange) => set({ dateRange }),
  setCandidateWindow: (candidateWindow) => set({ candidateWindow }),
  setCandidateResult: (candidateResult) => set({ candidateResult }),
}));

