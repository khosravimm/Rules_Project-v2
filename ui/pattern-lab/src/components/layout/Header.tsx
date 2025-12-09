import { useMemo } from "react";
import { useAppStore } from "../../store/useAppStore";

type HeaderProps = {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  selectionMode?: boolean;
  onToggleSelection?: () => void;
  onRefresh?: () => void;
  showTimeframeSwitcher?: boolean;
};

const Header = ({
  title = "PrisonBreaker - Pattern Lab",
  subtitle = "BTCUSDT Futures Research Console",
  actions,
  selectionMode,
  onToggleSelection,
  onRefresh,
  showTimeframeSwitcher = true,
}: HeaderProps) => {
  const { timeframe, setTimeframe, dateRange } = useAppStore();

  const rangeLabel = useMemo(() => {
    if (dateRange.start && dateRange.end) {
      return `${dateRange.start.slice(0, 16)} -> ${dateRange.end.slice(0, 16)}`;
    }
    return "Full range";
  }, [dateRange.start, dateRange.end]);

  return (
    <header className="mb-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">PrisonBreaker - Pattern Lab</p>
          <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
          <p className="text-slate-600 text-sm">{subtitle}</p>
          <p className="text-xs text-slate-500 mt-1">Range: {rangeLabel}</p>
        </div>
        <div className="flex items-center gap-2">
          {showTimeframeSwitcher && (
            <div className="flex bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
              {(["4h", "5m"] as const).map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-2 text-sm ${timeframe === tf ? "bg-emerald-500 text-white" : "text-slate-700"}`}
                >
                  {tf.toUpperCase()}
                </button>
              ))}
            </div>
          )}
          {onToggleSelection && (
            <button
              onClick={onToggleSelection}
              className={`button-ghost ${selectionMode ? "border-emerald-400 text-emerald-600 bg-emerald-50" : ""}`}
            >
              {selectionMode ? "Selecting window" : "Select window"}
            </button>
          )}
          {onRefresh && (
            <button onClick={onRefresh} className="button-primary">
              Refresh
            </button>
          )}
          {actions}
        </div>
      </div>
    </header>
  );
};

export default Header;
