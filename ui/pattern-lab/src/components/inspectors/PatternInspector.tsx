import { useMemo } from "react";
import { usePatternMeta } from "../../hooks/usePatternMeta";
import { useAppStore } from "../../store/useAppStore";
import { PatternHit } from "../../types/domain";

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

  if (!selectedPatternId) {
    return (
      <div className="glass-panel p-4">
        <p className="section-title mb-2">Pattern Inspector</p>
        <p className="text-slate-300">Select a pattern from the table to inspect metadata.</p>
      </div>
    );
  }

  return (
    <div className="glass-panel p-4">
      <p className="section-title mb-2">Pattern Inspector</p>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-white text-lg">{meta?.name || selectedPatternId}</h3>
          <p className="text-slate-300 text-sm max-w-xl">{meta?.description || "No description available."}</p>
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
          <div className="text-right text-sm text-slate-200">
            <div>Hits: {stats.hits}</div>
            <div>Avg lift: {stats.avgLift.toFixed(2)}</div>
            <div>Avg score: {stats.avgScore.toFixed(2)}</div>
          </div>
        )}
      </div>
      <div className="mt-4">
        <p className="text-slate-200 mb-2">Occurrences</p>
        <div className="max-h-52 overflow-y-auto pr-2 space-y-1">
          {occurrences.map((hit) => (
            <div
              key={`${hit.pattern_id}-${hit.start_ts}`}
              className="flex items-center justify-between bg-white/5 rounded-lg px-2 py-1 cursor-pointer hover:bg-white/10"
              onClick={() => setSelectedHit(hit)}
            >
              <span className="text-slate-100 text-sm">{hit.start_ts?.slice(0, 16)} → {hit.end_ts?.slice(0, 16)}</span>
              <span className="text-xs text-slate-300">
                lift {hit.lift?.toFixed(2) ?? "-"} · score {hit.accuracy?.toFixed(2) ?? "-"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default PatternInspector;
