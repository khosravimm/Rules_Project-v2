import { useEffect, useMemo, useState } from "react";
import { PatternHit } from "../../types/domain";
import { useAppStore } from "../../store/useAppStore";

type Props = {
  hits: PatternHit[];
  onSelect: (hit: PatternHit) => void;
  loading?: boolean;
  error?: string | null;
};

type SortField = "pattern_id" | "score" | "lift" | "support" | "start_ts" | "end_ts";

const PAGE_SIZE_OPTIONS = [50, 100, 200];

const PatternHitsTable = ({ hits, onSelect, loading = false, error = null }: Props) => {
  const [query, setQuery] = useState("");
  const [sortField, setSortField] = useState<SortField>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [pageSize, setPageSize] = useState<number>(100);
  const [page, setPage] = useState<number>(1);
  const selectedHit = useAppStore((s) => s.selectedHit);

  const { rows, total, totalPages } = useMemo(() => {
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
    const totalHits = sorted.length;
    const pages = Math.max(1, Math.ceil(totalHits / pageSize));
    const currentPage = Math.min(Math.max(page, 1), pages);
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const pageRows = sorted.slice(startIndex, endIndex);
    return { rows: pageRows, total: totalHits, totalPages: pages };
  }, [hits, query, sortField, sortDir, page, pageSize]);

  useEffect(() => {
    const newTotalPages = Math.max(1, Math.ceil(total / pageSize));
    if (page > newTotalPages) {
      setPage(newTotalPages);
    }
  }, [page, pageSize, total]);

  useEffect(() => {
    setPage(1);
  }, [query, hits.length, pageSize]);

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
            showing {rows.length} of {total} hits (page {page} / {totalPages})
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
      {loading && <div className="text-xs text-slate-500 mb-2">Loading pattern hits...</div>}
      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-2 py-1 mb-2 whitespace-pre-wrap break-words">
          {error}
        </div>
      )}
      <div className="flex items-center justify-between mb-2 text-sm text-slate-700">
        <div className="flex items-center gap-2">
          <span>Rows per page</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-sm text-slate-800"
          >
            {PAGE_SIZE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="button-ghost px-2 py-1 text-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </button>
          <span>
            Page {page} / {totalPages}
          </span>
          <button
            className="button-ghost px-2 py-1 text-sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Next
          </button>
        </div>
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
            {loading && rows.length === 0 ? (
              <tr>
                <td className="py-2 text-center text-slate-500" colSpan={8}>
                  Loading...
                </td>
              </tr>
            ) : null}
            {!loading && rows.length === 0 ? (
              <tr>
                <td className="py-2 text-center text-slate-500" colSpan={8}>
                  No hits match the current filters.
                </td>
              </tr>
            ) : null}
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
