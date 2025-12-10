import { useMemo } from "react";
import { usePatternMeta } from "../../hooks/usePatternMeta";
import { useAppStore } from "../../store/useAppStore";
import { PatternHit } from "../../types/domain";
import { formatTehran } from "../../utils/time";

const PatternInspector = () => {
  const { selectedPatternId, patternMeta, patternHits, setSelectedHit, timeframe } = useAppStore();
  usePatternMeta(selectedPatternId, timeframe);

  const meta = selectedPatternId ? patternMeta[selectedPatternId] : undefined;
  const occurrences: PatternHit[] = useMemo(() => {
    if (!selectedPatternId) return [];
    return patternHits.filter((h) => h.pattern_id === selectedPatternId).slice(0, 100);
  }, [patternHits, selectedPatternId]);

  const stats = useMemo(() => {
    if (occurrences.length === 0) return null;
    const lifts = occurrences.map((h) => h.lift ?? 0).filter((n) => !Number.isNaN(n));
    const scores = occurrences.map((h) => h.accuracy ?? 0).filter((n) => !Number.isNaN(n));
    const avg = (arr: number[]) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);
    return {
      hits: occurrences.length,
      avgLift: avg(lifts),
      avgScore: avg(scores),
    };
  }, [occurrences]);

  const sparklinePoints = useMemo(() => {
    if (!occurrences.length) return "";
    const times = occurrences.map((h) => new Date(h.start_ts || h.entry_candle_ts || "").getTime()).filter((t) => !Number.isNaN(t));
    const minT = Math.min(...times);
    const maxT = Math.max(...times);
    const span = maxT - minT || 1;
    return times
      .sort((a, b) => a - b)
      .map((t, idx) => {
        const x = (idx / Math.max(times.length - 1, 1)) * 100;
        const y = 40 - ((t - minT) / span) * 30;
        return `${x},${y}`;
      })
      .join(" ");
  }, [occurrences]);

  if (!selectedPatternId) {
    return (
      <div className="glass-panel p-4">
        <p className="section-title mb-2">Pattern Inspector</p>
        <p className="text-slate-700">Select a pattern from the table to inspect metadata.</p>
      </div>
    );
  }

  return (
    <div className="glass-panel p-4">
      <p className="section-title mb-2">Pattern Inspector</p>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-slate-900 text-lg">{meta?.name || selectedPatternId}</h3>
          <p className="text-slate-600 text-sm max-w-xl">{meta?.description || "No description available."}</p>
          <div className="flex flex-wrap gap-2 mt-2">
            <span className="chip">{meta?.pattern_type || "unknown"}</span>
            <span className="chip">Strength {meta?.strength_level || "-"}</span>
            <span className="chip">{meta?.status || "active"}</span>
            {meta?.tags?.map((t) => (
              <span key={t} className="chip">
                {t}
              </span>
            ))}
          </div>
        </div>
        {stats && (
          <div className="text-right text-sm text-slate-800">
            <div>Hits: {stats.hits}</div>
            <div>Avg lift: {stats.avgLift.toFixed(2)}</div>
            <div>Avg score: {stats.avgScore.toFixed(2)}</div>
          </div>
        )}
      </div>
      {sparklinePoints && (
        <div className="mt-3">
          <svg width="100%" height="48" viewBox="0 0 100 48" preserveAspectRatio="none">
            <polyline fill="none" stroke="#22c55e" strokeWidth="1.5" points={sparklinePoints} />
          </svg>
        </div>
      )}
      <div className="mt-3">
        <p className="text-slate-700 mb-2">Occurrences</p>
        <div className="max-h-52 overflow-y-auto pr-2 space-y-1">
          {occurrences.map((hit) => (
            <div
              key={`${hit.pattern_id}-${hit.start_ts}`}
              className="flex items-center justify-between bg-slate-50 rounded-lg px-2 py-1 cursor-pointer hover:bg-slate-100"
              onClick={() => setSelectedHit(hit)}
            >
              <span className="text-slate-800 text-sm">
                {formatTehran(hit.start_ts)} {"->"} {formatTehran(hit.end_ts)}
              </span>
              <span className="text-xs text-slate-600">
                lift {hit.lift?.toFixed(2) ?? "-"} | score {hit.accuracy?.toFixed(2) ?? "-"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default PatternInspector;
