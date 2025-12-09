import { useEffect, useMemo, useRef } from "react";
import {
  CandlestickData,
  ColorType,
  Time,
  UTCTimestamp,
  createChart,
} from "lightweight-charts";
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
  if (hit.direction === "short") return "rgba(239, 68, 68, 0.28)";
  if (hit.direction === "long") return "rgba(52, 211, 153, 0.28)";
  return "rgba(94, 234, 212, 0.22)";
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
      layout: { background: { type: ColorType.Solid, color: "#0b1220" }, textColor: "#cbd5e1" },
      width: containerRef.current.clientWidth,
      height: 420,
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 1 },
    });
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#34d399",
      downColor: "#ef4444",
      wickUpColor: "#34d399",
      wickDownColor: "#ef4444",
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
      if (!overlayLayer) return;
      overlayLayer.innerHTML = "";
      const timeScale = chart.timeScale();
      const maxBands = 160;
      hits.slice(0, maxBands).forEach((hit) => {
        if (!hit.start_ts || !hit.end_ts) return;
        const t0 = timeScale.timeToCoordinate(Math.floor(new Date(hit.start_ts).getTime() / 1000) as Time);
        const t1 = timeScale.timeToCoordinate(Math.floor(new Date(hit.end_ts).getTime() / 1000) as Time);
        if (t0 === null || t1 === null) return;
        const left = Math.min(t0, t1);
        const width = Math.max(2, Math.abs(t1 - t0));
        const band = document.createElement("div");
        band.style.position = "absolute";
        band.style.left = `${left}px`;
        band.style.width = `${width}px`;
        band.style.top = "0";
        band.style.bottom = "0";
        band.style.background = colorForHit(hit);
        band.style.border = hit.pattern_id === selectedPatternId ? "1px solid rgba(255,255,255,0.4)" : "1px solid transparent";
        band.style.pointerEvents = "none";
        overlayLayer.appendChild(band);
      });
      if (candidateWindow) {
        const t0 = timeScale.timeToCoordinate(Math.floor(new Date(candidateWindow.start_ts).getTime() / 1000) as Time);
        const t1 = timeScale.timeToCoordinate(Math.floor(new Date(candidateWindow.end_ts).getTime() / 1000) as Time);
        if (t0 !== null && t1 !== null) {
          const left = Math.min(t0, t1);
          const width = Math.max(4, Math.abs(t1 - t0));
          const band = document.createElement("div");
          band.style.position = "absolute";
          band.style.left = `${left}px`;
          band.style.width = `${width}px`;
          band.style.top = "0";
          band.style.bottom = "0";
          band.style.background = "rgba(59,130,246,0.18)";
          band.style.border = "1px solid rgba(59,130,246,0.5)";
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

    const markerData = hits.slice(0, 500).map((hit) => {
      const time = hit.entry_candle_ts || hit.end_ts || hit.start_ts;
      const ts = time ? (Math.floor(new Date(time).getTime() / 1000) as UTCTimestamp) : undefined;
      return ts
        ? {
            time: ts,
            position: "aboveBar" as const,
            color: hit.direction === "short" ? "#ef4444" : "#34d399",
            shape: hit.direction === "short" ? "arrowDown" : "arrowUp",
            text: hit.pattern_id,
          }
        : null;
    });
    candleSeries.setMarkers(markerData.filter(Boolean) as any[]);

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
