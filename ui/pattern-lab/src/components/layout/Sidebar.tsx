import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAppStore } from "../../store/useAppStore";

const navItems = [
  { label: "Dashboard", path: "/dashboard" },
  { label: "Pattern Lab", path: "/" },
  { label: "Pattern KB", path: "/patterns" },
  { label: "Backtests", path: "/backtests" },
  { label: "Reports", path: "/reports" },
  { label: "Settings", path: "/settings" },
];

const patternTypeOptions = [
  { label: "Sequence", value: "sequence" },
  { label: "Candle Shape", value: "candle_shape" },
  { label: "Feature Rule", value: "feature_rule" },
];

const strengthOptions = ["strong", "medium", "weak", "aging"];

type SidebarProps = {
  showFilters?: boolean;
};

const Sidebar = ({ showFilters = false }: SidebarProps) => {
  const location = useLocation();
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
    <aside className="glass-panel p-4 min-w-[260px] space-y-4 h-fit">
      <nav className="space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center justify-between px-3 py-2 rounded-lg text-sm ${
                isActive || location.pathname === item.path ? "bg-emerald-50 text-emerald-700 border border-emerald-100" : "text-slate-700 hover:bg-slate-100"
              }`
            }
          >
            <span>{item.label}</span>
            <span className="text-xs text-slate-400">v2</span>
          </NavLink>
        ))}
      </nav>

      {showFilters && (
        <div className="border-t border-slate-200 pt-3 space-y-3">
          <div>
            <p className="section-title mb-2">Pattern Type</p>
            <div className="flex flex-wrap gap-2">
              {patternTypeOptions.map((opt) => (
                <label key={opt.value} className="flex items-center gap-2 text-sm text-slate-800">
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
                <label key={s} className="flex items-center gap-2 text-sm text-slate-800 capitalize">
                  <input type="checkbox" checked={localFilters.strengths.includes(s)} onChange={() => toggleStrength(s)} />
                  {s}
                </label>
              ))}
            </div>
          </div>
          <div>
            <p className="section-title mb-2">Direction</p>
            <div className="flex gap-3 text-sm text-slate-800">
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
                className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-slate-800"
              />
              <input
                type="datetime-local"
                value={localRange.end || ""}
                onChange={(e) => setLocalRange((r) => ({ ...r, end: e.target.value || null }))}
                className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-slate-800"
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
      )}
    </aside>
  );
};

export default Sidebar;
