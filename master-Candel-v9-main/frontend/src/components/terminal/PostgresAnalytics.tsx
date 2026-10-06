import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Database } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { apiGet } from '@/lib/api';

interface PairRow { source: string; symbol: string; ticks: number; candles: number; lastTick: number | null; lastCandle: number | null }
interface Daily { date: string; observerTicks: number; observerCandles: number; derivTicks: number; derivCandles: number }
interface Analytics { enabled: boolean; days: number; pairs: PairRow[]; daily: Daily[]; totals: Partial<Record<keyof Omit<Daily, 'date'>, number>>; mirror?: { state: string; settings: { tickRetentionDays: number; candleRetentionDays: number } } }

const n = (value?: number | null) => value === undefined || value === null ? '—' : value.toLocaleString();
const when = (epoch: number | null) => epoch ? new Date(epoch * 1000).toISOString().replace('T', ' ').slice(0, 19) : '—';
const SERIES: { key: keyof Omit<Daily, 'date'>; label: string; color: string }[] = [
  { key: 'derivTicks', label: 'Deriv ticks', color: '#3b9dff' },
  { key: 'derivCandles', label: 'Deriv candles', color: '#1f5f9e' },
  { key: 'observerTicks', label: 'Observer ticks', color: '#f0c25c' },
  { key: 'observerCandles', label: 'Observer candles', color: '#a5812f' },
];

export default function PostgresAnalytics() {
  const [days, setDays] = useState(7);
  const [source, setSource] = useState<'all' | 'deriv' | 'market-qx-observer-v2'>('all');
  const query = useQuery({ queryKey: ['postgres-analytics', days], queryFn: () => apiGet<Analytics>(`/v1/postgres/analytics?days=${days}`), refetchInterval: 15000 });
  const data = query.data;
  const pairs = (data?.pairs || []).filter(row => source === 'all' || row.source === source);
  return (
    <section className="workspace-card" data-testid="postgres-analytics">
      <header>
        <div><p>POSTGRESQL MIRROR</p><h2>Tick &amp; candle counts per pair</h2></div>
        <div className="workspace-segment" role="group" aria-label="Analytics window">
          {[1, 7, 30].map(value => <button key={value} type="button" data-testid={`analytics-days-${value}`} className={days === value ? 'selected' : ''} onClick={() => setDays(value)}>{value}d</button>)}
        </div>
      </header>
      {query.isLoading ? <p className="workspace-empty" data-testid="postgres-analytics-loading">Loading PostgreSQL analytics…</p>
        : query.isError || !data?.enabled ? <p role="alert" className="workspace-empty" data-testid="postgres-analytics-error">PostgreSQL mirror unavailable. Check DATABASE_URL and connection health.</p>
        : <>
          <div className="workspace-stats" data-testid="postgres-analytics-totals">
            {SERIES.map(series => <span key={series.key}><i style={{ background: series.color }} />{series.label} <b data-testid={`analytics-total-${series.key}`}>{n(data.totals[series.key] ?? 0)}</b></span>)}
            <span><Database size={13} /> Retention <b>{data.mirror?.settings.tickRetentionDays ?? '—'}d ticks · {data.mirror?.settings.candleRetentionDays ?? '—'}d candles</b></span>
          </div>
          <div className="workspace-chart" data-testid="postgres-analytics-chart">
            {data.daily.length ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={data.daily} margin={{ top: 8, right: 12, left: 0, bottom: 0 }} barCategoryGap={18}>
                  <CartesianGrid stroke="#243044" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: '#8896ab', fontSize: 10 }} tickFormatter={value => String(value).slice(5)} axisLine={{ stroke: '#2b3547' }} tickLine={false} />
                  <YAxis tick={{ fill: '#8896ab', fontSize: 10 }} axisLine={false} tickLine={false} width={56} tickFormatter={value => Number(value) >= 1000 ? `${Math.round(Number(value) / 1000)}k` : String(value)} />
                  <Tooltip cursor={{ fill: '#ffffff08' }} contentStyle={{ background: '#161c29', border: '1px solid #2b3547', borderRadius: 6, fontSize: 11 }} labelStyle={{ color: '#dfe8f6' }} formatter={(value: number, name: string) => [value.toLocaleString(), name]} />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#b3c0d3' }} />
                  {SERIES.map(series => <Bar key={series.key} dataKey={series.key} name={series.label} fill={series.color} radius={[3, 3, 0, 0]} maxBarSize={38} />)}
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="workspace-empty" data-testid="postgres-analytics-empty">No mirrored rows in the selected window yet.</p>}
          </div>
          <div className="workspace-segment small" role="group" aria-label="Source filter">
            {([['all', 'All sources'], ['deriv', 'Deriv'], ['market-qx-observer-v2', 'QX observer']] as const).map(([value, label]) => <button key={value} type="button" data-testid={`analytics-source-${value}`} className={source === value ? 'selected' : ''} onClick={() => setSource(value)}>{label}</button>)}
          </div>
          <div className="workspace-table-wrap">
            <table data-testid="postgres-pairs-table">
              <thead><tr><th>Pair</th><th>Source</th><th>Ticks</th><th>Candles</th><th>Last tick (UTC)</th><th>Last candle (UTC)</th></tr></thead>
              <tbody>{pairs.map(row => <tr key={`${row.source}:${row.symbol}`} data-testid={`postgres-pair-${row.symbol}`}><td>{row.symbol}</td><td>{row.source === 'deriv' ? 'Deriv' : 'QX observer'}</td><td>{n(row.ticks)}</td><td>{n(row.candles)}</td><td>{when(row.lastTick)}</td><td>{when(row.lastCandle)}</td></tr>)}</tbody>
            </table>
            {!pairs.length && <p className="workspace-empty">No pairs mirrored for this source in the last {days} day{days > 1 ? 's' : ''}.</p>}
          </div>
        </>}
    </section>
  );
}
