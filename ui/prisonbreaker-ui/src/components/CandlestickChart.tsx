import { useEffect, useRef } from 'react';
import {
  CandlestickData,
  IChartApi,
  ISeriesApi,
  SeriesMarker,
  Time,
  createChart,
} from 'lightweight-charts';
import type { Candle, PatternHit } from '../types/trading';

export interface CandlestickChartProps {
  candles: Candle[];
  patternHits?: PatternHit[];
  height?: number;
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

export function CandlestickChart({ candles, patternHits = [], height = 500 }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0b0e11' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.05)' },
        horzLines: { color: 'rgba(255,255,255,0.05)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(197,203,206,0.4)',
      },
      timeScale: {
        borderColor: 'rgba(197,203,206,0.4)',
      },
      crosshair: {
        mode: 0,
      },
    });
    const series = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: false,
    });
    chartRef.current = chart;
    seriesRef.current = series;

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
    seriesRef.current.setMarkers(markers);
  }, [patternHits]);

  return <div ref={containerRef} style={{ width: '100%', height }} />;
}
