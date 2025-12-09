import { useMemo, useState } from "react";
import { PatternHit } from "../../types/domain";
import { useAppStore } from "../../store/useAppStore";

type Props = {
  hits: PatternHit[];
  onSelect: (hit: PatternHit) => void;
};

const PatternHitsTable = ({ hits, onSelect }: Props) => {
  const [query, setQuery] = useState("");
  const selectedHit = useAppStore((s) => s.selectedHit);

  const rows = useMemo(() => {
    const filtered = query ? hits.filter((h) => h.pattern_id.toLowerCase().includes(query.toLowerCase())) : hits;
    return filtered.slice(0, 200);
  }, [hits, query]);

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="section-title mb-1">Pattern Hits</p>
          <p className="text-slate-300 text-sm">{rows.length} visible · total {hits.length}</p>
        </div>
        <input
          type="text"
          placeholder="Search pattern_id"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-sm text-slate-100"
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-slate-100">
          <thead className="text-slate-300">
            <tr>
              <th className="text-left pb-2">Pattern</th>
              <th className="text-left pb-2">Type</th>
              <th className="text-left pb-2">Dir</th>
              <th className="text-left pb-2">Start</th>
              <th className="text-left pb-2">End</th>
              <th className="text-left pb-2">Score</th>
              <th className="text-left pb-2">Lift</th>
              <th className="text-left pb-2">Support</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((hit) => {
              const active = selectedHit?.pattern_id === hit.pattern_id && selectedHit?.start_ts === hit.start_ts;
              return (
                <tr
                  key={`${hit.pattern_id}-${hit.start_ts}`}
                  className={`hover:bg-white/5 cursor-pointer ${active ? "bg-emerald-500/10" : ""}`}
                  onClick={() => onSelect(hit)}
                >
                  <td className="py-1">{hit.pattern_id}</td>
                  <td className="py-1 capitalize">{hit.pattern_type}</td>
                  <td className="py-1">{hit.direction || "?"}</td>
                  <td className="py-1 text-slate-300">{hit.start_ts?.slice(0, 16)}</td>
                  <td className="py-1 text-slate-300">{hit.end_ts?.slice(0, 16)}</td>
                  <td className="py-1">{hit.accuracy?.toFixed(2) ?? "-"}</td>
                  <td className="py-1">{hit.lift ? hit.lift.toFixed(2) : "-"}</td>
                  <td className="py-1">{hit.support ? hit.support.toFixed(0) : "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PatternHitsTable;
