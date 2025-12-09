import { useEffect, useMemo, useState } from "react";
import CandleChart from "./components/chart/CandleChart";
import CandleInspector from "./components/inspectors/CandleInspector";
import ManualPatternPlayground from "./components/inspectors/ManualPatternPlayground";
import PatternInspector from "./components/inspectors/PatternInspector";
import Header from "./components/layout/Header";
import Sidebar from "./components/layout/Sidebar";
import PatternHitsTable from "./components/tables/PatternHitsTable";
import PatternListTable from "./components/tables/PatternListTable";
import { useCandles } from "./hooks/useCandles";
import { usePatternHits } from "./hooks/usePatternHits";
import { usePatternMeta } from "./hooks/usePatternMeta";
import { useAppStore } from "./store/useAppStore";

const App = () => {
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectionMode, setSelectionMode] = useState(false);
  const {
    timeframe,
    candles,
    patternHits,
    setSelectedHit,
    setSelectedPatternId,
    patternMeta,
    selectedPatternId,
    candidateWindow,
  } = useAppStore();

  useCandles(refreshKey);
  usePatternHits(refreshKey);
  usePatternMeta(undefined, timeframe);

  useEffect(() => {
    // reset selection when timeframe changes
    setSelectedHit(undefined);
    setSelectedPatternId(undefined);
  }, [timeframe, setSelectedHit, setSelectedPatternId]);

  const metaList = useMemo(() => Object.values(patternMeta), [patternMeta]);

  return (
    <div className="min-h-screen px-6 py-4">
      <Header
        onRefresh={() => setRefreshKey((k) => k + 1)}
        selectionMode={selectionMode}
        onToggleSelection={() => setSelectionMode((v) => !v)}
      />
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
        <Sidebar />
        <div className="space-y-4">
          <CandleChart
            candles={candles}
            hits={patternHits}
            selectedPatternId={selectedPatternId}
            selectionMode={selectionMode}
          />
          <PatternHitsTable
            hits={patternHits}
            onSelect={(hit) => {
              setSelectedHit(hit);
              setSelectedPatternId(hit.pattern_id);
            }}
          />
          <div className="grid md:grid-cols-2 gap-4">
            <CandleInspector />
            <PatternInspector />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <ManualPatternPlayground />
            <PatternListTable patterns={metaList} />
          </div>
          {candidateWindow && (
            <div className="text-xs text-slate-300">
              Selected window: {candidateWindow.start_ts} → {candidateWindow.end_ts}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
