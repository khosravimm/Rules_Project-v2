import { useEffect, useRef } from 'react';
import type {
  CandlestickData,
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  SeriesMarker,
  Time,
} from 'lightweight-charts';
import { CandlestickSeries, createChart, createSeriesMarkers } from 'lightweight-charts';
import type { Candle, PatternHit } from '../types/trading';

export type ChartTheme = 'dark' | 'light';

export interface CandlestickChartProps {
  candles: Candle[];
  patternHits?: PatternHit[];
  height?: number;
  theme?: ChartTheme;
}

function normalizeTime(value: number | string): Time {
  if (typeof value === 'number') {
    // assume seconds; lightweight-charts expects unix seconds
    return value as Time;
  }
  return Math.floor(Date.parse(value) / 1000) as Time;
}

function mapCandles(candles: Candle[]): CandlestickData[] {
  return candles.map((c) => ({
    time: normalizeTime(c.time),
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));
}

function mapMarkers(hits: PatternHit[] = []): SeriesMarker<Time>[] {
  return hits.map((h) => {
    let color = '#7f8c8d';
    let position: SeriesMarker<Time>['position'] = 'inBar';
    let shape: SeriesMarker<Time>['shape'] = 'circle';
    if (h.direction === 'long') {
      color = '#2ecc71';
      position = 'belowBar';
      shape = 'arrowUp';
    } else if (h.direction === 'short') {
      color = '#e74c3c';
      position = 'aboveBar';
      shape = 'arrowDown';
    }
    return {
      time: normalizeTime(h.time),
      color,
      position,
      shape,
      text: h.id,
    };
  });
}

export function CandlestickChart({ candles, patternHits = [], height = 500, theme = 'dark' }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const isDark = theme === 'dark';
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: isDark ? '#0b0e11' : '#f7f8fa' },
        textColor: isDark ? '#d1d4dc' : '#1f2937',
      },
      grid: {
        vertLines: { color: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.08)' },
        horzLines: { color: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.08)' },
      },
      rightPriceScale: {
        borderColor: isDark ? 'rgba(197,203,206,0.4)' : 'rgba(0,0,0,0.1)',
      },
      timeScale: {
        borderColor: isDark ? 'rgba(197,203,206,0.4)' : 'rgba(0,0,0,0.1)',
      },
      crosshair: {
        mode: 0,
      },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: isDark ? '#26a69a' : '#0f9d58',
      downColor: isDark ? '#ef5350' : '#d93025',
      wickUpColor: isDark ? '#26a69a' : '#0f9d58',
      wickDownColor: isDark ? '#ef5350' : '#d93025',
      borderVisible: false,
    });
    chartRef.current = chart;
    seriesRef.current = series;
    markersPluginRef.current = createSeriesMarkers(series, []);

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const cr = entry.contentRect;
        chart.applyOptions({ width: cr.width });
      }
    });
    resizeObserverRef.current = ro;
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      markersPluginRef.current = null;
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !chartRef.current) return;
    const data = mapCandles(candles);
    seriesRef.current.setData(data);
    if (data.length > 0) {
      chartRef.current.timeScale().fitContent();
    }
  }, [candles]);

  useEffect(() => {
    if (!seriesRef.current) return;
    const markers = mapMarkers(patternHits);
    if (markersPluginRef.current) {
      markersPluginRef.current.setMarkers(markers);
    } else {
      markersPluginRef.current = createSeriesMarkers(seriesRef.current, markers);
    }
  }, [patternHits]);

  return <div ref={containerRef} style={{ width: '100%', height }} />;
}
