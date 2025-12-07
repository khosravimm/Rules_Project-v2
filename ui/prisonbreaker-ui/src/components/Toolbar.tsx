import type { SymbolPair, Timeframe } from '../types/trading';

interface ToolbarProps {
  symbol: SymbolPair;
  timeframe: Timeframe;
  symbols: SymbolPair[];
  timeframes: Timeframe[];
  onChangeSymbol: (symbol: SymbolPair) => void;
  onChangeTimeframe: (tf: Timeframe) => void;
}

export function Toolbar({
  symbol,
  timeframe,
  symbols,
  timeframes,
  onChangeSymbol,
  onChangeTimeframe,
}: ToolbarProps) {
  return (
    <header
      style={{
        background: '#0f131a',
        color: '#d1d4dc',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div style={{ fontWeight: 700, fontSize: '18px' }}>PrisonBreaker</div>
      <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>Symbol</span>
        <select
          value={symbol}
          onChange={(e) => onChangeSymbol(e.target.value)}
          style={{
            background: '#151a21',
            color: '#d1d4dc',
            border: '1px solid rgba(255,255,255,0.15)',
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
            background: '#151a21',
            color: '#d1d4dc',
            border: '1px solid rgba(255,255,255,0.15)',
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
    </header>
  );
}
