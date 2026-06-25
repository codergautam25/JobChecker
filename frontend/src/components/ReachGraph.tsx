"use client";

import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useState, useMemo, useRef, useEffect } from 'react';
import { TrendingUp } from 'lucide-react';

type WeekData = {
  week: number;
  label: string;
  date_range: string;
  count: number;
};

function smoothPath(points: [number, number][]): string {
  if (points.length < 2) return '';
  
  let d = `M ${points[0][0]},${points[0][1]}`;
  
  for (let i = 0; i < points.length - 1; i++) {
    const curr = points[i];
    const next = points[i + 1];
    const tension = 0.3;
    const dx = next[0] - curr[0];
    
    const cp1x = curr[0] + dx * tension;
    const cp1y = curr[1];
    const cp2x = next[0] - dx * tension;
    const cp2y = next[1];
    
    d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${next[0]},${next[1]}`;
  }
  
  return d;
}

export function ReachGraph() {
  const { data, isLoading } = useQuery({
    queryKey: ['weekly-reach'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/dashboard/weekly-reach?weeks=8');
      return res.data.weeks as WeekData[];
    }
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(700);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(entries => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const chartW = containerWidth - 2;
  const chartH = 220;
  const padL = 44;
  const padR = 20;
  const padT = 20;
  const padB = 52;
  const plotW = chartW - padL - padR;
  const plotH = chartH - padT - padB;

  const { points, areaPath, linePath, maxVal, yTicks } = useMemo(() => {
    if (!data || data.length === 0) return { points: [], areaPath: '', linePath: '', maxVal: 0, yTicks: [] };
    
    const maxCount = Math.max(...data.map(d => d.count), 1);
    const niceMax = Math.ceil(maxCount / 5) * 5 || 5;
    
    const pts: [number, number][] = data.map((d, i) => {
      const x = padL + (i / (data.length - 1)) * plotW;
      const y = padT + plotH - (d.count / niceMax) * plotH;
      return [x, y];
    });
    
    const line = smoothPath(pts);
    
    // Area: line + close at bottom
    const lastPt = pts[pts.length - 1];
    const firstPt = pts[0];
    const area = `${line} L ${lastPt[0]},${padT + plotH} L ${firstPt[0]},${padT + plotH} Z`;
    
    const tickCount = 5;
    const ticks = Array.from({ length: tickCount + 1 }, (_, i) => {
      const val = Math.round((niceMax / tickCount) * i);
      const y = padT + plotH - (val / niceMax) * plotH;
      return { val, y };
    });
    
    return { points: pts, areaPath: area, linePath: line, maxVal: niceMax, yTicks: ticks };
  }, [data, plotW, plotH]);

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 h-[320px] animate-pulse">
        <div className="h-5 bg-slate-800 rounded w-48 mb-6"></div>
        <div className="h-[220px] bg-slate-800/50 rounded-xl"></div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="p-2 bg-sky-500/10 rounded-lg">
            <TrendingUp size={20} className="text-sky-400" />
          </div>
          <h3 className="font-semibold text-slate-100">Application Reach</h3>
        </div>
        <div className="h-[220px] flex items-center justify-center text-slate-500 text-sm">
          No application data available yet.
        </div>
      </div>
    );
  }

  const total = data.reduce((s, d) => s + d.count, 0);
  const thisWeek = data[data.length - 1]?.count || 0;
  const lastWeek = data.length > 1 ? data[data.length - 2]?.count || 0 : 0;
  const trend = thisWeek - lastWeek;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-sky-500/10 rounded-lg">
            <TrendingUp size={20} className="text-sky-400" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-100 text-[15px]">Application Reach</h3>
            <p className="text-xs text-slate-500 mt-0.5">Accepted applications per week</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-xs text-slate-500">Total</p>
            <p className="text-lg font-bold text-slate-100">{total}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-500">This Week</p>
            <div className="flex items-center gap-1.5">
              <p className="text-lg font-bold text-slate-100">{thisWeek}</p>
              {trend !== 0 && (
                <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${trend > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                  {trend > 0 ? '+' : ''}{trend}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div ref={containerRef} className="w-full relative">
        <svg
          width={chartW}
          height={chartH}
          viewBox={`0 0 ${chartW} ${chartH}`}
          className="w-full"
          style={{ overflow: 'visible' }}
        >
          <defs>
            {/* Gradient for area fill */}
            <linearGradient id="reachGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.3" />
              <stop offset="50%" stopColor="#0ea5e9" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
            </linearGradient>
            {/* Glow filter for the line */}
            <filter id="lineGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            {/* Glow for dots */}
            <filter id="dotGlow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Horizontal grid lines */}
          {yTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={padL}
                y1={tick.y}
                x2={padL + plotW}
                y2={tick.y}
                stroke="#1e293b"
                strokeWidth={1}
                strokeDasharray={i === 0 ? "0" : "4 4"}
              />
              <text
                x={padL - 8}
                y={tick.y + 4}
                textAnchor="end"
                className="fill-slate-600"
                style={{ fontSize: '10px', fontFamily: 'ui-monospace, monospace' }}
              >
                {tick.val}
              </text>
            </g>
          ))}

          {/* Vertical grid lines + X labels */}
          {data.map((d, i) => {
            const x = padL + (i / (data.length - 1)) * plotW;
            return (
              <g key={i}>
                <line
                  x1={x}
                  y1={padT}
                  x2={x}
                  y2={padT + plotH}
                  stroke="#1e293b"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                />
                {/* Week label */}
                <text
                  x={x}
                  y={padT + plotH + 18}
                  textAnchor="middle"
                  className="fill-slate-400"
                  style={{ fontSize: '11px', fontWeight: 600 }}
                >
                  {d.label}
                </text>
                {/* Date range */}
                <text
                  x={x}
                  y={padT + plotH + 34}
                  textAnchor="middle"
                  className="fill-slate-600"
                  style={{ fontSize: '9px', fontFamily: 'ui-monospace, monospace' }}
                >
                  {d.date_range}
                </text>
              </g>
            );
          })}

          {/* Area fill */}
          <path
            d={areaPath}
            fill="url(#reachGradient)"
            className="transition-all duration-500"
          />

          {/* Main line with glow */}
          <path
            d={linePath}
            fill="none"
            stroke="#0ea5e9"
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#lineGlow)"
            className="transition-all duration-500"
          />

          {/* Seismic secondary lines (subtle offset echoes) */}
          <path
            d={linePath}
            fill="none"
            stroke="#0ea5e9"
            strokeWidth={1}
            strokeLinecap="round"
            opacity={0.15}
            transform="translate(0, 4)"
          />
          <path
            d={linePath}
            fill="none"
            stroke="#0ea5e9"
            strokeWidth={0.5}
            strokeLinecap="round"
            opacity={0.08}
            transform="translate(0, 8)"
          />

          {/* Data points */}
          {points.map(([px, py], i) => (
            <g key={i}>
              {/* Hover zone (invisible, larger for easier targeting) */}
              <circle
                cx={px}
                cy={py}
                r={16}
                fill="transparent"
                className="cursor-pointer"
                onMouseEnter={(e) => {
                  setHoveredIdx(i);
                  const rect = (e.target as SVGElement).closest('svg')?.getBoundingClientRect();
                  if (rect) {
                    setTooltipPos({ x: px, y: py });
                  }
                }}
                onMouseLeave={() => setHoveredIdx(null)}
              />
              {/* Outer glow ring */}
              <circle
                cx={px}
                cy={py}
                r={hoveredIdx === i ? 10 : 6}
                fill="#0ea5e9"
                opacity={hoveredIdx === i ? 0.15 : 0.08}
                className="transition-all duration-200"
              />
              {/* Dot */}
              <circle
                cx={px}
                cy={py}
                r={hoveredIdx === i ? 5 : 3.5}
                fill={hoveredIdx === i ? "#38bdf8" : "#0ea5e9"}
                stroke="#0f172a"
                strokeWidth={2}
                className="transition-all duration-200"
              />
              {/* Pulse on latest point */}
              {i === points.length - 1 && (
                <circle
                  cx={px}
                  cy={py}
                  r={3.5}
                  fill="none"
                  stroke="#0ea5e9"
                  strokeWidth={1.5}
                  opacity={0.5}
                >
                  <animate
                    attributeName="r"
                    values="3.5;12;3.5"
                    dur="2.5s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.5;0;0.5"
                    dur="2.5s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}
            </g>
          ))}

          {/* Hover vertical line */}
          {hoveredIdx !== null && (
            <line
              x1={tooltipPos.x}
              y1={padT}
              x2={tooltipPos.x}
              y2={padT + plotH}
              stroke="#38bdf8"
              strokeWidth={1}
              strokeDasharray="3 3"
              opacity={0.4}
            />
          )}
        </svg>

        {/* Tooltip */}
        {hoveredIdx !== null && data[hoveredIdx] && (
          <div
            className="absolute pointer-events-none z-50 animate-in fade-in duration-150"
            style={{
              left: `${tooltipPos.x}px`,
              top: `${tooltipPos.y - 16}px`,
              transform: 'translate(-50%, -100%)',
            }}
          >
            <div className="bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2.5 shadow-xl shadow-black/40 text-center min-w-[100px]">
              <p className="text-[11px] text-slate-400 font-medium">{data[hoveredIdx].date_range}</p>
              <p className="text-lg font-bold text-sky-400 mt-0.5">{data[hoveredIdx].count}</p>
              <p className="text-[10px] text-slate-500">applications</p>
            </div>
            <div className="w-2 h-2 bg-slate-800 border-r border-b border-slate-700 rotate-45 mx-auto -mt-1"></div>
          </div>
        )}
      </div>
    </div>
  );
}
