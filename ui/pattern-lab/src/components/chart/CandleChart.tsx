import { useEffect, useMemo, useRef } from "react";
import { CandlestickData, ColorType, Time, UTCTimestamp, createChart } from "lightweight-charts";
import { Candle, PatternHit } from "../../types/domain";
import { useSelectionState } from "../../hooks/useSelectionState";
import { useAppStore } from "../../store/useAppStore";

type CandleChartProps = {
  candles: Candle[];
  hits: PatternHit[];
  selectedPatternId?: string;
  selectedHit?: PatternHit | undefined;
  selectionMode?: boolean;
};

const MAX_VISIBLE_HITS = 200;

const toChartTime = (iso?: string | null): UTCTimestamp | null => {
  if (!iso) return null;
  const n = Date.parse(iso);
  if (Number.isNaN(n)) return null;
  return Math.floor(n / 1000) as UTCTimestamp;
};

export const CandleChart = ({ candles, hits, selectedPatternId, selectedHit, selectionMode }: CandleChartProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);

  const sortedCandles = useMemo(() => {
    const arr = candles
      .filter((c) => c.timestamp)
      .map((c) => ({ ...c, __ts: Date.parse(c.timestamp) }))
      .filter((c) => !Number.isNaN(c.__ts))
      .sort((a, b) => a.__ts - b.__ts);
    // enforce strictly increasing by dropping duplicates
    const unique: Candle[] = [];
    let lastTs = -Infinity;
    for (const c of arr) {
      if (c.__ts > lastTs) {
        unique.push({ ...c });
        lastTs = c.__ts;
      }
    }
    return unique;
  }, [candles]);

  const candleMap = useMemo(() => {
    const map = new Map<UTCTimestamp, Candle>();
    sortedCandles.forEach((c) => {
      const ts = toChartTime(c.timestamp);
      if (ts !== null) {
        map.set(ts, c);
      }
    });
    return map;
  }, [sortedCandles]);

  const { startSelection, extendSelection, candidateWindow } = useSelectionState();
  const setSelectedCandle = useAppStore((s) => s.setSelectedCandle);
  const setSelectedHit = useAppStore((s) => s.setSelectedHit);

  const bandColor = (hit: PatternHit) => {
    if (hit.direction === "short") return "rgba(239, 68, 68, 0.35)";
    if (hit.direction === "long") return "rgba(16, 185, 129, 0.35)";
    return "rgba(59, 130, 246, 0.25)";
  };

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

    const updateOverlays = () => {
      if (!overlayLayer || !containerRef.current) return;
      overlayLayer.innerHTML = "";
      const timeScale = chart.timeScale();
      const visible = timeScale.getVisibleRange();
      const chartWidth = containerRef.current.clientWidth;
      if (!visible) {
        candleSeries.setMarkers([]);
        return;
      }

      const visibleHits = hits
        .map((hit) => {
          const startSec = toChartTime(hit.start_ts);
          const endSec = toChartTime(hit.end_ts);
          const entrySec = toChartTime(hit.entry_candle_ts);
          const times = [startSec, endSec, entrySec].filter((t): t is number => t !== null);
          if (!times.length) return null;
          const minT = Math.min(...times);
          const maxT = Math.max(...times);
          return { hit, startSec, endSec, entrySec, minT, maxT };
        })
        .filter((item): item is NonNullable<typeof item> => Boolean(item))
        .filter((item) => item.maxT >= visible.from && item.minT <= visible.to)
        .slice(0, MAX_VISIBLE_HITS);

      visibleHits.forEach(({ hit, startSec, endSec }) => {
        if (startSec === null || endSec === null) return;
        const t0 = timeScale.timeToCoordinate(startSec as Time);
        const t1 = timeScale.timeToCoordinate(endSec as Time);
        if (t0 === null || t1 === null) return;
        const left = Math.min(t0, t1);
        const right = Math.max(t0, t1);
        if (right < 0 || left > chartWidth) return;
        const bandWidth = Math.max(2, Math.abs(t1 - t0));
        const band = document.createElement("div");
        band.style.position = "absolute";
        band.style.left = `${left}px`;
        band.style.width = `${bandWidth}px`;
        band.style.top = "0";
        band.style.bottom = "0";
        band.style.background = bandColor(hit);
        const isSelected = selectedHit?.pattern_id
          ? hit.pattern_id === selectedHit.pattern_id
          : hit.pattern_id === selectedPatternId;
        band.style.border = isSelected ? "1px solid rgba(16,185,129,0.7)" : "1px solid transparent";
        band.style.pointerEvents = "none";
        overlayLayer.appendChild(band);
      });

      if (candidateWindow) {
        const startSec = toChartTime(candidateWindow.start_ts);
        const endSec = toChartTime(candidateWindow.end_ts);
        if (startSec !== null && endSec !== null && endSec >= visible.from && startSec <= visible.to) {
          const t0 = timeScale.timeToCoordinate(startSec as Time);
          const t1 = timeScale.timeToCoordinate(endSec as Time);
          if (t0 !== null && t1 !== null) {
            const left = Math.min(t0, t1);
            const bandWidth = Math.max(4, Math.abs(t1 - t0));
            const band = document.createElement("div");
            band.style.position = "absolute";
            band.style.left = `${left}px`;
            band.style.width = `${bandWidth}px`;
            band.style.top = "0";
            band.style.bottom = "0";
            band.style.background = "rgba(59,130,246,0.18)";
            band.style.border = "1px solid rgba(59,130,246,0.7)";
            band.style.pointerEvents = "none";
            overlayLayer.appendChild(band);
          }
        }
      }

      const bestMarkerByCandle = new Map<UTCTimestamp, PatternHit>();
      visibleHits.forEach(({ hit, entrySec, startSec, endSec }) => {
        const tsChoice = entrySec ?? endSec ?? startSec;
        if (tsChoice === null || tsChoice === undefined) return;
        const ts = tsChoice as UTCTimestamp;
        const current = bestMarkerByCandle.get(ts);
        const score = (hit.accuracy ?? hit.lift ?? 0) as number;
        const currentScore = current ? (current.accuracy ?? current.lift ?? 0) : -Infinity;
        if (!current || score > currentScore) {
          bestMarkerByCandle.set(ts, hit);
        }
      });
      const markerData = Array.from(bestMarkerByCandle.entries())
        .map(([ts, hit]) => {
          const dir = hit.direction;
          const isShort = dir === "short";
          const isLong = dir === "long";
          return {
            time: ts,
            position: "aboveBar" as const,
            color: isShort ? "#ef4444" : isLong ? "#16a34a" : "#3b82f6",
            shape: isShort ? "arrowDown" : isLong ? "arrowUp" : "circle",
            text: hit.pattern_id,
          };
        })
        .filter((m) => Number.isFinite(m.time))
        .sort((a, b) => (a.time as number) - (b.time as number));
      candleSeries.setMarkers(markerData);
    };

    const resize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
      updateOverlays();
    };
    window.addEventListener("resize", resize);

    const candleData: CandlestickData[] = sortedCandles.reduce((acc: CandlestickData[], c) => {
      const t = toChartTime(c.timestamp);
      if (t !== null) {
        acc.push({
          time: t,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        });
      }
      return acc;
    }, []);
    candleSeries.setData(candleData);

    const onRangeChange = () => updateOverlays();
    chart.timeScale().subscribeVisibleTimeRangeChange(onRangeChange);
    updateOverlays();

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
      chart.timeScale().unsubscribeVisibleTimeRangeChange(onRangeChange);
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
    selectedHit,
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
