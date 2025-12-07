import { useMemo, useState } from 'react';
import { Toolbar } from './components/Toolbar';
import { CandlestickChart } from './components/CandlestickChart';
import { useCandles } from './hooks/useCandles';
import type { SymbolPair, Timeframe } from './types/trading';

const SYMBOLS: SymbolPair[] = ['BTCUSDT', 'ETHUSDT'];
const TIMEFRAMES: Timeframe[] = ['5m', '15m', '1h', '4h', '1d'];

export default function App() {
  const [symbol, setSymbol] = useState<SymbolPair>('BTCUSDT');
  const [timeframe, setTimeframe] = useState<Timeframe>('4h');
  const [theme, setTheme] = useState<'dark' | 'light'>('light');

  const { candles, patternHits, loading, error } = useCandles({
    symbol,
    timeframe,
    autoRefreshMs: 0, // disable auto refresh to prevent page reloads
  });

  const recentHits = useMemo(() => {
    const normalize = (t: number | string) =>
      typeof t === 'number' ? t : Math.floor(Date.parse(t) / 1000);
    return [...patternHits]
      .sort((a, b) => normalize(b.time) - normalize(a.time))
      .slice(0, 50);
  }, [patternHits]);

  return (
    <div
      style={{
        minHeight: '100vh',
        background: theme === 'dark' ? '#0b0e11' : '#f7f8fa',
        color: theme === 'dark' ? '#d1d4dc' : '#1f2937',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Toolbar
        symbol={symbol}
        timeframe={timeframe}
        symbols={SYMBOLS}
        timeframes={TIMEFRAMES}
        onChangeSymbol={setSymbol}
        onChangeTimeframe={setTimeframe}
        theme={theme}
        onChangeTheme={setTheme}
      />

      <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
        <div style={{ fontSize: '12px', color: '#9ba0aa' }}>
          {loading ? 'Loading...' : error ? `Error: ${error}` : candles.length ? `${candles.length} candles` : 'No data'}
        </div>
        <div
          style={{
            border: theme === 'dark' ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
            borderRadius: 8,
            background: theme === 'dark' ? '#0f131a' : '#ffffff',
            padding: '8px',
            flex: 1,
            minHeight: '480px',
          }}
        >
          <CandlestickChart candles={candles} patternHits={patternHits} height={520} theme={theme} />
        </div>

        <div
          style={{
            border: theme === 'dark' ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
            borderRadius: 8,
            background: theme === 'dark' ? '#0f131a' : '#ffffff',
            padding: '8px',
            maxHeight: '260px',
            overflowY: 'auto',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '6px' }}>Latest pattern hits</div>
          {recentHits.length === 0 ? (
            <div style={{ color: theme === 'dark' ? '#9ba0aa' : '#4b5563' }}>No pattern hits</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead style={{ textAlign: 'left', color: theme === 'dark' ? '#9ba0aa' : '#4b5563' }}>
                <tr>
                  <th style={{ padding: '4px' }}>Time</th>
                  <th style={{ padding: '4px' }}>ID</th>
                  <th style={{ padding: '4px' }}>Dir</th>
                  <th style={{ padding: '4px' }}>Strength</th>
                </tr>
              </thead>
              <tbody>
                {recentHits.map((hit) => (
                  <tr
                    key={`${hit.id}-${hit.time}`}
                    style={{
                      borderTop: theme === 'dark' ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)',
                    }}
                  >
                    <td style={{ padding: '4px' }}>
                      {typeof hit.time === 'string'
                        ? hit.time
                        : new Date(Number(hit.time) * 1000).toISOString()}
                    </td>
                    <td style={{ padding: '4px' }}>{hit.id}</td>
                    <td
                      style={{
                        padding: '4px',
                        color:
                          hit.direction === 'long'
                            ? theme === 'dark'
                              ? '#2ecc71'
                              : '#0f9d58'
                            : theme === 'dark'
                              ? '#e74c3c'
                              : '#d93025',
                      }}
                    >
                      {hit.direction}
                    </td>
                    <td style={{ padding: '4px' }}>{hit.strength ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
