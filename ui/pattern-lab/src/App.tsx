import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import CandleChart from "./components/chart/CandleChart";
import CandleInspector from "./components/inspectors/CandleInspector";
import ManualPatternPlayground from "./components/inspectors/ManualPatternPlayground";
import PatternInspector from "./components/inspectors/PatternInspector";
import MainLayout from "./components/layout/MainLayout";
import PatternHitsTable from "./components/tables/PatternHitsTable";
import PatternListTable from "./components/tables/PatternListTable";
import { useCandles } from "./hooks/useCandles";
import { usePatternHits } from "./hooks/usePatternHits";
import { usePatternMeta } from "./hooks/usePatternMeta";
import { useAppStore } from "./store/useAppStore";
import { PatternMeta } from "./types/domain";

type PatternLabPageProps = {
  refreshKey: number;
  selectionMode: boolean;
};

const PatternLabPage = ({ refreshKey, selectionMode }: PatternLabPageProps) => {
  const {
    timeframe,
    candles,
    patternHits,
    setSelectedHit,
    setSelectedPatternId,
    patternMeta,
    selectedPatternId,
    candidateWindow,
    selectedHit,
    setDateRange,
  } = useAppStore();

  useCandles(refreshKey);
  const { loading: hitsLoading, error: hitsError } = usePatternHits(refreshKey);
  usePatternMeta(undefined, timeframe);

  useEffect(() => {
    setSelectedHit(undefined);
    setSelectedPatternId(undefined);
  }, [timeframe, setSelectedHit, setSelectedPatternId]);

  useEffect(() => {
    if (!selectedHit) return;
    const center = selectedHit.entry_candle_ts || selectedHit.end_ts || selectedHit.start_ts;
    if (!center) return;
    const deltaSec = timeframe === "4h" ? 4 * 3600 : 5 * 60;
    const c = new Date(center);
    const start = new Date(c.getTime() - 80 * deltaSec * 1000).toISOString();
    const end = new Date(c.getTime() + 40 * deltaSec * 1000).toISOString();
    setDateRange({ start, end });
  }, [selectedHit, timeframe, setDateRange]);

  const metaList = useMemo<PatternMeta[]>(() => Object.values(patternMeta), [patternMeta]);

  return (
    <div className="space-y-4">
      <CandleChart
        candles={candles}
        hits={patternHits}
        selectedPatternId={selectedPatternId}
        selectedHit={selectedHit}
        selectionMode={selectionMode}
      />
      <PatternHitsTable
        hits={patternHits}
        loading={hitsLoading}
        error={hitsError}
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
        <div className="text-xs text-slate-600">
          Selected window: {candidateWindow.start_ts} {"->"} {candidateWindow.end_ts}
        </div>
      )}
    </div>
  );
};

const DashboardPage = () => {
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div className="glass-panel p-4">
        <p className="section-title mb-2">Overview</p>
        <p className="text-slate-700 text-sm">High-level metrics coming soon (PnL, hit density, uptime).</p>
      </div>
      <div className="glass-panel p-4">
        <p className="section-title mb-2">Realtime Readiness</p>
        <p className="text-slate-700 text-sm">Hooks ready for streaming overlays; connect to live feed to activate.</p>
      </div>
    </div>
  );
};

const ReportsPage = () => (
  <div className="glass-panel p-4">
    <p className="section-title mb-2">Reports / Analytics</p>
    <p className="text-slate-700 text-sm">Placeholder for strategy analytics, export, and research dashboards.</p>
  </div>
);

const PatternKbPage = () => {
  const { patternMeta, timeframe } = useAppStore();
  usePatternMeta(undefined, timeframe);
  const metaList = useMemo<PatternMeta[]>(() => Object.values(patternMeta), [patternMeta]);
  return <PatternListTable patterns={metaList} />;
};

const BacktestsPage = () => (
  <div className="glass-panel p-4">
    <p className="section-title mb-2">Backtests</p>
    <p className="text-slate-700 text-sm">Hook your backtest summaries here. This panel is ready for integration.</p>
  </div>
);

const SettingsPage = () => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  return (
    <div className="space-y-3">
      <div className="glass-panel p-4">
        <p className="section-title mb-2">API Base URL</p>
        <p className="text-slate-700 text-sm">
          Current API base: <span className="font-mono text-slate-900">{baseUrl}</span>
        </p>
        <p className="text-slate-500 text-sm">Edit VITE_API_BASE_URL in .env or environment variables to point to another backend.</p>
      </div>
      <div className="glass-panel p-4">
        <p className="section-title mb-2">Display / Timezone</p>
        <p className="text-slate-700 text-sm">Future options for theme switching and timezone normalization will appear here.</p>
      </div>
    </div>
  );
};

const App = () => {
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectionMode, setSelectionMode] = useState(false);

  const commonSubtitle = "4h / 5m - Level-1 patterns - Research console";

  return (
    <Routes>
      <Route
        path="/"
        element={
          <MainLayout
            title="Pattern Lab"
            subtitle={commonSubtitle}
            showFilters
            selectionMode={selectionMode}
            onToggleSelection={() => setSelectionMode((v) => !v)}
            onRefresh={() => setRefreshKey((k) => k + 1)}
          >
            <PatternLabPage refreshKey={refreshKey} selectionMode={selectionMode} />
          </MainLayout>
        }
      />
      <Route
        path="/dashboard"
        element={
          <MainLayout title="Dashboard" subtitle={commonSubtitle}>
            <DashboardPage />
          </MainLayout>
        }
      />
      <Route
        path="/reports"
        element={
          <MainLayout title="Reports / Analytics" subtitle={commonSubtitle}>
            <ReportsPage />
          </MainLayout>
        }
      />
      <Route
        path="/patterns"
        element={
          <MainLayout title="Pattern KB" subtitle={commonSubtitle}>
            <PatternKbPage />
          </MainLayout>
        }
      />
      <Route
        path="/backtests"
        element={
          <MainLayout title="Backtests" subtitle={commonSubtitle}>
            <BacktestsPage />
          </MainLayout>
        }
      />
      <Route
        path="/settings"
        element={
          <MainLayout title="Settings" subtitle="Configure API endpoints and display options">
            <SettingsPage />
          </MainLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;
