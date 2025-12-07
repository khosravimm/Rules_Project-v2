import type { SymbolPair, Timeframe } from '../types/trading';

interface ToolbarProps {
  symbol: SymbolPair;
  timeframe: Timeframe;
  symbols: SymbolPair[];
  timeframes: Timeframe[];
  onChangeSymbol: (symbol: SymbolPair) => void;
  onChangeTimeframe: (tf: Timeframe) => void;
  theme: 'dark' | 'light';
  onChangeTheme: (t: 'dark' | 'light') => void;
}

export function Toolbar({
  symbol,
  timeframe,
  symbols,
  timeframes,
  onChangeSymbol,
  onChangeTimeframe,
  theme,
  onChangeTheme,
}: ToolbarProps) {
  const isDark = theme === 'dark';
  return (
    <header
      style={{
        background: isDark ? '#0f131a' : '#f0f2f5',
        color: isDark ? '#d1d4dc' : '#1f2937',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        borderBottom: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
      }}
    >
      <div style={{ fontWeight: 700, fontSize: '18px' }}>PrisonBreaker</div>
      <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>Symbol</span>
        <select
          value={symbol}
          onChange={(e) => onChangeSymbol(e.target.value)}
          style={{
            background: isDark ? '#151a21' : '#ffffff',
            color: isDark ? '#d1d4dc' : '#1f2937',
            border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.15)',
            borderRadius: 4,
            padding: '6px 8px',
          }}
        >
          {symbols.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>TF</span>
        <select
          value={timeframe}
          onChange={(e) => onChangeTimeframe(e.target.value as Timeframe)}
          style={{
            background: isDark ? '#151a21' : '#ffffff',
            color: isDark ? '#d1d4dc' : '#1f2937',
            border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.15)',
            borderRadius: 4,
            padding: '6px 8px',
          }}
        >
          {timeframes.map((tf) => (
            <option key={tf} value={tf}>
              {tf}
            </option>
          ))}
        </select>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>Theme</span>
        <select
          value={theme}
          onChange={(e) => onChangeTheme(e.target.value as 'dark' | 'light')}
          style={{
            background: isDark ? '#151a21' : '#ffffff',
            color: isDark ? '#d1d4dc' : '#1f2937',
            border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.15)',
            borderRadius: 4,
            padding: '6px 8px',
          }}
        >
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </label>
    </header>
  );
}
