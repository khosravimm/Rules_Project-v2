import { useMemo } from "react";
import { useAppStore } from "../../store/useAppStore";

const CandleInspector = () => {
  const { selectedCandle, patternHits, setSelectedHit, setSelectedPatternId, patternMeta } = useAppStore();

  const coveringHits = useMemo(() => {
    if (!selectedCandle) return [];
    const ts = new Date(selectedCandle.timestamp);
    return patternHits.filter((hit) => {
      if (!hit.start_ts || !hit.end_ts) return false;
      const s = new Date(hit.start_ts);
      const e = new Date(hit.end_ts);
      return ts >= s && ts <= e;
    });
  }, [patternHits, selectedCandle]);

  if (!selectedCandle) {
    return (
      <div className="glass-panel p-4">
        <p className="section-title mb-2">Candle Inspector</p>
        <p className="text-slate-300">Click on the chart to inspect a candle.</p>
      </div>
    );
  }

  return (
    <div className="glass-panel p-4">
      <p className="section-title mb-1">Candle Inspector</p>
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-white font-semibold">{selectedCandle.timestamp}</p>
          <p className="text-slate-300 text-sm">
            O {selectedCandle.open.toFixed(2)} · H {selectedCandle.high.toFixed(2)} · L {selectedCandle.low.toFixed(2)} · C{" "}
            {selectedCandle.close.toFixed(2)}
          </p>
        </div>
        <div className="chip">
          Direction{" "}
          {selectedCandle.close > selectedCandle.open ? "Up" : selectedCandle.close < selectedCandle.open ? "Down" : "Flat"}
        </div>
      </div>
      <div>
        <p className="text-slate-200 mb-2">Patterns covering this candle ({coveringHits.length})</p>
        <div className="space-y-1 max-h-40 overflow-y-auto pr-2">
          {coveringHits.map((hit) => {
            const meta = patternMeta[hit.pattern_id];
            return (
              <div
                key={`${hit.pattern_id}-${hit.start_ts}`}
                className="flex items-center justify-between bg-white/5 rounded-lg px-2 py-1 cursor-pointer hover:bg-white/10"
                onClick={() => {
                  setSelectedHit(hit);
                  setSelectedPatternId(hit.pattern_id);
                }}
              >
                <div>
                  <p className="text-white text-sm">{meta?.name || hit.pattern_id}</p>
                  <p className="text-slate-400 text-xs">
                    {hit.pattern_type} · {hit.direction || "?"}
                  </p>
                </div>
                <div className="text-xs text-slate-300">
                  lift {hit.lift?.toFixed(2) ?? "-"} | score {hit.accuracy?.toFixed(2) ?? "-"}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default CandleInspector;
