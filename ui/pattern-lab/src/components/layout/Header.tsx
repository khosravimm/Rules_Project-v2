import { useMemo } from "react";
import { useAppStore } from "../../store/useAppStore";

type HeaderProps = {
  onRefresh: () => void;
  selectionMode: boolean;
  onToggleSelection: () => void;
};

const Header = ({ onRefresh, selectionMode, onToggleSelection }: HeaderProps) => {
  const { timeframe, setTimeframe, dateRange } = useAppStore();

  const rangeLabel = useMemo(() => {
    if (dateRange.start && dateRange.end) {
      return `${dateRange.start.slice(0, 16)} → ${dateRange.end.slice(0, 16)}`;
    }
    return "Full range";
  }, [dateRange.start, dateRange.end]);

  return (
    <header className="flex items-center justify-between gap-4 mb-4">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-slate-300">PrisonBreaker – Pattern Lab</p>
        <h1 className="text-2xl font-semibold text-white">BTCUSDT Futures Research Console</h1>
        <p className="text-slate-300 text-sm">{rangeLabel}</p>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex bg-white/5 rounded-xl border border-white/10 overflow-hidden">
          {(["4h", "5m"] as const).map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-2 text-sm ${timeframe === tf ? "bg-emerald-500 text-white" : "text-slate-200"}`}
            >
              {tf.toUpperCase()}
            </button>
          ))}
        </div>
        <button onClick={onToggleSelection} className={`button-ghost ${selectionMode ? "border-emerald-400 text-emerald-300" : ""}`}>
          {selectionMode ? "Selecting window…" : "Select window"}
        </button>
        <button onClick={onRefresh} className="button-primary">
          Refresh
        </button>
      </div>
    </header>
  );
};

export default Header;
