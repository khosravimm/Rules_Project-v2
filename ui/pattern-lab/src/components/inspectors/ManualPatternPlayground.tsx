import { useState } from "react";
import { createPatternFromCandidate, searchCandidate } from "../../services/api";
import { useAppStore } from "../../store/useAppStore";
import { CandidateOccurrence } from "../../types/domain";

const ManualPatternPlayground = () => {
  const {
    candidateWindow,
    candidateResult,
    setCandidateResult,
    timeframe,
    setSelectedPatternId,
    setPatternMeta,
  } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("manual,custom");
  const [patternType, setPatternType] = useState("sequence");
  const [strength, setStrength] = useState("weak");
  const [error, setError] = useState<string | null>(null);

  const doSearch = async () => {
    if (!candidateWindow) return;
    setLoading(true);
    setError(null);
    try {
      const res = await searchCandidate(timeframe, {
        start_ts: candidateWindow.start_ts,
        end_ts: candidateWindow.end_ts,
      });
      setCandidateResult(res);
    } catch (err: any) {
      setError(err?.message || "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const savePattern = async () => {
    if (!candidateWindow) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        timeframe,
        pattern_type: patternType,
        base_window: { start_ts: candidateWindow.start_ts, end_ts: candidateWindow.end_ts },
        name: name || `Custom ${timeframe} pattern`,
        description: description || "Manual pattern created from selected window.",
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        initial_strength_level: strength,
      };
      const res = await createPatternFromCandidate(payload);
      setPatternMeta([res.pattern]);
      setSelectedPatternId(res.pattern.pattern_id);
    } catch (err: any) {
      setError(err?.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const Summary = () => {
    if (!candidateResult) return null;
    const s = candidateResult.candidate_summary;
    return (
      <div className="glass-panel p-3 mt-3 bg-slate-50">
        <p className="text-slate-800 text-sm">Occurrences: {s.approx_support}</p>
        <p className="text-slate-800 text-sm">Winrate: {s.approx_winrate ? (s.approx_winrate * 100).toFixed(1) + "%" : "-"}</p>
        <p className="text-slate-800 text-sm">Direction hint: {s.direction_hint}</p>
      </div>
    );
  };

  const OccTable = () => {
    if (!candidateResult?.occurrences?.length) return null;
    return (
      <div className="mt-3 max-h-48 overflow-y-auto space-y-1">
        {candidateResult.occurrences.map((o: CandidateOccurrence) => (
          <div key={o.start_ts} className="flex items-center justify-between bg-slate-50 rounded-lg px-2 py-1">
            <div className="text-slate-800 text-sm">
              {o.start_ts.slice(0, 16)} -> {o.end_ts.slice(0, 16)}
            </div>
            <div className="text-xs text-slate-600">
              sim {(o.similarity * 100).toFixed(1)} | next {o.label_next_dir || "-"} | rr {o.pnl_rr?.toFixed(2) ?? "-"}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="glass-panel p-4">
      <p className="section-title mb-2">Manual Pattern Playground</p>
      {!candidateWindow ? (
        <p className="text-slate-700 text-sm">Enable "Select window" and click two candles to define a range.</p>
      ) : (
        <div className="space-y-2 text-slate-800 text-sm">
          <div>
            Selected window: {candidateWindow.start_ts.slice(0, 16)} -> {candidateWindow.end_ts.slice(0, 16)}
          </div>
          <div className="flex gap-2">
            <button onClick={doSearch} disabled={loading} className="button-primary">
              {loading ? "Searching..." : "Search in history"}
            </button>
            <button onClick={savePattern} disabled={saving} className="button-ghost border-emerald-400 text-emerald-600">
              {saving ? "Saving..." : "Save as pattern"}
            </button>
          </div>
          {error && <div className="text-red-500 text-sm">{error}</div>}
          <div className="grid grid-cols-2 gap-2">
            <input
              className="bg-white border border-slate-200 rounded-lg px-2 py-1"
              placeholder="Pattern name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <select
              value={patternType}
              onChange={(e) => setPatternType(e.target.value)}
              className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-slate-800"
            >
              <option value="sequence">Sequence</option>
              <option value="candle_shape">Candle Shape</option>
              <option value="feature_rule">Feature Rule</option>
            </select>
            <textarea
              className="bg-white border border-slate-200 rounded-lg px-2 py-1 col-span-2"
              rows={3}
              placeholder="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <input
              className="bg-white border border-slate-200 rounded-lg px-2 py-1"
              placeholder="Tags (comma separated)"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
            <select
              value={strength}
              onChange={(e) => setStrength(e.target.value)}
              className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-slate-800"
            >
              <option value="strong">Strong</option>
              <option value="medium">Medium</option>
              <option value="weak">Weak</option>
            </select>
          </div>
          <Summary />
          <OccTable />
        </div>
      )}
    </div>
  );
};

export default ManualPatternPlayground;
