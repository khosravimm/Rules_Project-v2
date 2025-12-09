import { useEffect, useState } from "react";
import { useAppStore } from "../../store/useAppStore";

const patternTypeOptions = [
  { label: "Sequence", value: "sequence" },
  { label: "Candle Shape", value: "candle_shape" },
  { label: "Feature Rule", value: "feature_rule" },
];

const strengthOptions = ["strong", "medium", "weak", "aging"];

const navItems = ["Dashboard", "Pattern KB", "Backtests", "Reports", "Settings"];

const Sidebar = () => {
  const { filters, setFilters, dateRange, setDateRange } = useAppStore();
  const [localFilters, setLocalFilters] = useState(filters);
  const [localRange, setLocalRange] = useState(dateRange);

  useEffect(() => {
    setLocalFilters(filters);
    setLocalRange(dateRange);
  }, [filters, dateRange]);

  const togglePatternType = (value: string) => {
    setLocalFilters((prev) => {
      const exists = prev.patternTypes.includes(value);
      const next = exists ? prev.patternTypes.filter((v) => v !== value) : [...prev.patternTypes, value];
      return { ...prev, patternTypes: next };
    });
  };

  const toggleStrength = (value: string) => {
    setLocalFilters((prev) => {
      const exists = prev.strengths.includes(value);
      const next = exists ? prev.strengths.filter((v) => v !== value) : [...prev.strengths, value];
      return { ...prev, strengths: next };
    });
  };

  const apply = () => {
    setFilters(localFilters);
    setDateRange(localRange);
  };

  const reset = () => {
    const defaults = {
      patternTypes: ["sequence", "candle_shape", "feature_rule"],
      direction: "all" as const,
      strengths: ["strong", "medium", "weak", "aging"],
      start: null,
      end: null,
    };
    setLocalFilters(defaults);
    setLocalRange({ start: null, end: null });
    setFilters(defaults);
    setDateRange({ start: null, end: null });
  };

  return (
    <aside className="glass-panel p-4 min-w-[260px] space-y-4">
      <nav className="space-y-2">
        {navItems.map((item) => (
          <div key={item} className="flex items-center justify-between text-slate-200">
            <span>{item}</span>
            <span className="text-xs text-slate-400">beta</span>
          </div>
        ))}
      </nav>
      <div className="border-t border-white/10 pt-3 space-y-3">
        <div>
          <p className="section-title mb-2">Pattern Type</p>
          <div className="flex flex-wrap gap-2">
            {patternTypeOptions.map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={localFilters.patternTypes.includes(opt.value)}
                  onChange={() => togglePatternType(opt.value)}
                />
                {opt.label}
              </label>
            ))}
          </div>
        </div>
        <div>
          <p className="section-title mb-2">Strength</p>
          <div className="flex flex-wrap gap-2">
            {strengthOptions.map((s) => (
              <label key={s} className="flex items-center gap-2 text-sm text-slate-200 capitalize">
                <input type="checkbox" checked={localFilters.strengths.includes(s)} onChange={() => toggleStrength(s)} />
                {s}
              </label>
            ))}
          </div>
        </div>
        <div>
          <p className="section-title mb-2">Direction</p>
          <div className="flex gap-3 text-sm text-slate-200">
            {["all", "long", "short"].map((d) => (
              <label key={d} className="flex items-center gap-2 capitalize">
                <input type="radio" checked={localFilters.direction === d} onChange={() => setLocalFilters({ ...localFilters, direction: d as any })} />
                {d}
              </label>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <p className="section-title">Time Window</p>
          <div className="flex flex-col gap-2">
            <input
              type="datetime-local"
              value={localRange.start || ""}
              onChange={(e) => setLocalRange((r) => ({ ...r, start: e.target.value || null }))}
              className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-slate-100"
            />
            <input
              type="datetime-local"
              value={localRange.end || ""}
              onChange={(e) => setLocalRange((r) => ({ ...r, end: e.target.value || null }))}
              className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-slate-100"
            />
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={apply} className="button-primary w-full">
            Apply
          </button>
          <button onClick={reset} className="button-ghost w-full">
            Reset
          </button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
