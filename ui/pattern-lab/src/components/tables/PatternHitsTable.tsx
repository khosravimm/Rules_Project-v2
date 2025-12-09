import { useMemo, useState } from "react";
import { PatternHit } from "../../types/domain";
import { useAppStore } from "../../store/useAppStore";

type Props = {
  hits: PatternHit[];
  onSelect: (hit: PatternHit) => void;
};

type SortField = "pattern_id" | "score" | "lift" | "support" | "start_ts" | "end_ts";

const PatternHitsTable = ({ hits, onSelect }: Props) => {
  const [query, setQuery] = useState("");
  const [sortField, setSortField] = useState<SortField>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const selectedHit = useAppStore((s) => s.selectedHit);

  const rows = useMemo(() => {
    const filtered = query ? hits.filter((h) => h.pattern_id.toLowerCase().includes(query.toLowerCase())) : hits;
    const sorted = [...filtered].sort((a, b) => {
      const getVal = (h: PatternHit) => {
        switch (sortField) {
          case "pattern_id":
            return h.pattern_id;
          case "score":
            return h.accuracy ?? 0;
          case "lift":
            return h.lift ?? 0;
          case "support":
            return h.support ?? 0;
          case "start_ts":
            return h.start_ts || "";
          case "end_ts":
            return h.end_ts || "";
          default:
            return 0;
        }
      };
      const va = getVal(a);
      const vb = getVal(b);
      if (va === vb) return 0;
      if (sortDir === "asc") return va > vb ? 1 : -1;
      return va < vb ? 1 : -1;
    });
    return sorted.slice(0, 200);
  }, [hits, query, sortField, sortDir]);

  const toggleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const headerCell = (label: string, field: SortField) => (
    <th className="text-left pb-2 cursor-pointer select-none" onClick={() => toggleSort(field)}>
      {label} {sortField === field ? (sortDir === "asc" ? "^" : "v") : ""}
    </th>
  );

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="section-title mb-1">Pattern Hits</p>
          <p className="text-slate-600 text-sm">
            {rows.length} visible - total {hits.length}
          </p>
        </div>
        <input
          type="text"
          placeholder="Search pattern_id"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-sm text-slate-800"
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-slate-800">
          <thead className="text-slate-500">
            <tr>
              {headerCell("Pattern", "pattern_id")}
              <th className="text-left pb-2">Type</th>
              <th className="text-left pb-2">Dir</th>
              {headerCell("Start", "start_ts")}
              {headerCell("End", "end_ts")}
              {headerCell("Score", "score")}
              {headerCell("Lift", "lift")}
              {headerCell("Support", "support")}
            </tr>
          </thead>
          <tbody>
            {rows.map((hit) => {
              const active = selectedHit?.pattern_id === hit.pattern_id && selectedHit?.start_ts === hit.start_ts;
              return (
                <tr
                  key={`${hit.pattern_id}-${hit.start_ts}`}
                  className={`hover:bg-slate-50 cursor-pointer ${active ? "bg-emerald-50" : ""}`}
                  onClick={() => onSelect(hit)}
                >
                  <td className="py-1">{hit.pattern_id}</td>
                  <td className="py-1 capitalize">{hit.pattern_type}</td>
                  <td className="py-1">{hit.direction || "?"}</td>
                  <td className="py-1 text-slate-500">{hit.start_ts?.slice(0, 16)}</td>
                  <td className="py-1 text-slate-500">{hit.end_ts?.slice(0, 16)}</td>
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
