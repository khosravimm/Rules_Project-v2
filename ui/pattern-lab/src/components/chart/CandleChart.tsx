import { useEffect, useMemo, useRef } from "react";
import { CandlestickData, ColorType, Time, UTCTimestamp, createChart } from "lightweight-charts";
import { Candle, PatternHit } from "../../types/domain";
import { useSelectionState } from "../../hooks/useSelectionState";
import { useAppStore } from "../../store/useAppStore";

type CandleChartProps = {
  candles: Candle[];
  hits: PatternHit[];
  selectedPatternId?: string;
  selectionMode?: boolean;
};

const colorForHit = (hit: PatternHit) => {
  if (hit.direction === "short") return "rgba(239, 68, 68, 0.18)";
  if (hit.direction === "long") return "rgba(16, 185, 129, 0.18)";
  return "rgba(59, 130, 246, 0.12)";
};

export const CandleChart = ({ candles, hits, selectedPatternId, selectionMode }: CandleChartProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const candleMap = useMemo(() => {
    const map = new Map<UTCTimestamp, Candle>();
    candles.forEach((c) => {
      const ts = Math.floor(new Date(c.timestamp).getTime() / 1000) as UTCTimestamp;
      map.set(ts, c);
    });
    return map;
  }, [candles]);

  const { startSelection, extendSelection, candidateWindow } = useSelectionState();
  const setSelectedCandle = useAppStore((s) => s.setSelectedCandle);
  const setSelectedHit = useAppStore((s) => s.setSelectedHit);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#f8fafc" }, textColor: "#1f2937" },
      width: containerRef.current.clientWidth,
      height: 420,
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 1 },
    });
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
      borderVisible: false,
    });

    const overlayLayer = overlayRef.current;

    const resize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
      renderBands();
    };
    window.addEventListener("resize", resize);

    const renderBands = () => {
      if (!overlayLayer || !containerRef.current) return;
      overlayLayer.innerHTML = "";
      const timeScale = chart.timeScale();
      const width = containerRef.current.clientWidth;
      const maxBands = 160;
      hits.slice(0, maxBands).forEach((hit) => {
        if (!hit.start_ts || !hit.end_ts) return;
        const t0 = timeScale.timeToCoordinate(Math.floor(new Date(hit.start_ts).getTime() / 1000) as Time);
        const t1 = timeScale.timeToCoordinate(Math.floor(new Date(hit.end_ts).getTime() / 1000) as Time);
        if (t0 === null || t1 === null) return;
        const left = Math.min(t0, t1);
        const right = Math.max(t0, t1);
        if (right < 0 || left > width) return;
        const bandWidth = Math.max(2, Math.abs(t1 - t0));
        const band = document.createElement("div");
        band.style.position = "absolute";
        band.style.left = `${left}px`;
        band.style.width = `${bandWidth}px`;
        band.style.top = "0";
        band.style.bottom = "0";
        band.style.background = colorForHit(hit);
        band.style.border = hit.pattern_id === selectedPatternId ? "1px solid rgba(16,185,129,0.6)" : "1px solid transparent";
        band.style.pointerEvents = "none";
        overlayLayer.appendChild(band);
      });
      if (candidateWindow) {
        const t0 = timeScale.timeToCoordinate(Math.floor(new Date(candidateWindow.start_ts).getTime() / 1000) as Time);
        const t1 = timeScale.timeToCoordinate(Math.floor(new Date(candidateWindow.end_ts).getTime() / 1000) as Time);
        if (t0 !== null && t1 !== null) {
          const left = Math.min(t0, t1);
          const bandWidth = Math.max(4, Math.abs(t1 - t0));
          const band = document.createElement("div");
          band.style.position = "absolute";
          band.style.left = `${left}px`;
          band.style.width = `${bandWidth}px`;
          band.style.top = "0";
          band.style.bottom = "0";
          band.style.background = "rgba(59,130,246,0.15)";
          band.style.border = "1px solid rgba(59,130,246,0.4)";
          band.style.pointerEvents = "none";
          overlayLayer.appendChild(band);
        }
      }
    };

    const candleData: CandlestickData[] = candles.map((c) => ({
      time: Math.floor(new Date(c.timestamp).getTime() / 1000) as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candleSeries.setData(candleData);

    const bestMarkerByCandle = new Map<UTCTimestamp, PatternHit>();
    hits.forEach((hit) => {
      const time = hit.entry_candle_ts || hit.end_ts || hit.start_ts;
      if (!time) return;
      const ts = Math.floor(new Date(time).getTime() / 1000) as UTCTimestamp;
      const current = bestMarkerByCandle.get(ts);
      const score = (hit.accuracy ?? hit.lift ?? 0) as number;
      const currentScore = current ? (current.accuracy ?? current.lift ?? 0) : -Infinity;
      if (!current || score > currentScore) {
        bestMarkerByCandle.set(ts, hit);
      }
    });
    const markerData = Array.from(bestMarkerByCandle.entries()).map(([ts, hit]) => ({
      time: ts,
      position: "aboveBar" as const,
      color: hit.direction === "short" ? "#ef4444" : "#22c55e",
      shape: hit.direction === "short" ? "arrowDown" : "arrowUp",
      text: hit.pattern_id,
    }));
    candleSeries.setMarkers(markerData);

    chart.timeScale().subscribeVisibleLogicalRangeChange(renderBands);
    renderBands();

    chart.subscribeClick((param) => {
      if (param.time === undefined) return;
      const ts = param.time as UTCTimestamp;
      const candle = candleMap.get(ts);
      if (!candle) return;
      if (selectionMode) {
        if (!candidateWindow) {
          startSelection(candle);
        } else {
          extendSelection(candle);
        }
      } else {
        setSelectedCandle(candle);
        const hit = hits.find(
          (h) =>
            h.start_ts &&
            h.end_ts &&
            new Date(h.start_ts) <= new Date(candle.timestamp) &&
            new Date(h.end_ts) >= new Date(candle.timestamp),
        );
        if (hit) setSelectedHit(hit);
      }
    });

    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, [
    candles,
    hits,
    candleMap,
    selectedPatternId,
    selectionMode,
    candidateWindow,
    extendSelection,
    setSelectedCandle,
    setSelectedHit,
    startSelection,
  ]);

  return (
    <div className="relative glass-panel overflow-hidden">
      <div className="absolute inset-0" ref={overlayRef} style={{ pointerEvents: "none", zIndex: 2 }} />
      <div ref={containerRef} className="h-[420px] w-full" />
    </div>
  );
};

export default CandleChart;
