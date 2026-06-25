"use client";

import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Briefcase, FileText, Mail, Activity, ArrowUpRight, TrendingUp } from 'lucide-react';
import { ReachGraph } from '@/components/ReachGraph';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const COLORS = ['#38bdf8', '#fb7185', '#34d399', '#c084fc', '#fbbf24'];

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/dashboard');
      return res.data;
    }
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-500"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-xl">
        <h3 className="text-rose-400 font-semibold mb-2">Connection Error</h3>
        <p className="text-rose-300/80 text-sm">Failed to connect to the FastAPI backend. Make sure it is running on port 8000.</p>
      </div>
    );
  }

  const stats = [
    { label: 'Active Jobs', value: data.stats.total_jobs, icon: Briefcase, color: 'text-sky-400', bg: 'bg-sky-400/10' },
    { label: 'Emails Processed', value: data.stats.total_emails, icon: Mail, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { label: 'Applied', value: data.stats.total_applied, icon: Activity, color: 'text-rose-400', bg: 'bg-rose-400/10' },
    { label: 'Interviews', value: data.stats.total_interviews, icon: FileText, color: 'text-purple-400', bg: 'bg-purple-400/10' },
  ];

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-12">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-8 gap-4">
        <h2 className="text-2xl font-bold text-slate-100">Overview</h2>
        <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 rounded-xl">
          <TrendingUp size={20} className="text-emerald-400" />
          <div className="flex flex-col">
            <span className="text-[10px] font-semibold text-emerald-400/70 uppercase tracking-widest">Conversion Rate</span>
            <span className="text-lg font-bold text-emerald-400 leading-none mt-0.5">{data.stats.conversion_rate}%</span>
          </div>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-xl ${stat.bg} ${stat.color}`}>
                  <Icon size={24} />
                </div>
                <ArrowUpRight size={20} className="text-slate-600" />
              </div>
              <div className="text-3xl font-bold text-slate-100 mb-1">{stat.value}</div>
              <div className="text-sm text-slate-400 font-medium">{stat.label}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12">
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <h3 className="font-semibold text-slate-100 mb-6">Application Volume (30 Days)</h3>
          <div className="h-64 w-full">
            {data.volume?.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.volume}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                    itemStyle={{ color: '#e2e8f0' }}
                    cursor={{fill: '#1e293b', opacity: 0.4}}
                  />
                  <Bar dataKey="applications" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-slate-500">No application volume data</div>
            )}
          </div>
        </div>
        
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <h3 className="font-semibold text-slate-100 mb-2">Email Classifications</h3>
          <div className="h-64 w-full flex items-center justify-center">
            {data.classifications?.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.classifications}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {data.classifications.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-slate-500 text-sm">No classification data yet</div>
            )}
          </div>
          <div className="flex flex-wrap gap-2 justify-center mt-2">
            {data.classifications?.map((entry: any, index: number) => (
              <div key={index} className="flex items-center gap-1.5 text-xs text-slate-400">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }}></div>
                {entry.name || 'UNCLASSIFIED'} ({entry.value})
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-12">
        <ReachGraph />
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-800">
          <h3 className="font-semibold text-slate-100">Recent Activity Feed</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-800/50 text-slate-400 font-medium">
              <tr>
                <th className="px-6 py-4 rounded-tl-lg">Time</th>
                <th className="px-6 py-4">Event</th>
                <th className="px-6 py-4">Entity Type</th>
                <th className="px-6 py-4 rounded-tr-lg">Entity ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data.activity.map((row: any, i: number) => (
                <tr key={i} className="hover:bg-slate-800/20 transition-colors">
                  <td className="px-6 py-4 text-slate-400">
                    {new Date(row.timestamp + "Z").toLocaleString(undefined, {
                      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                    })}
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                      {row.event_name}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-300">{row.entity_type}</td>
                  <td className="px-6 py-4">
                    <span className="font-mono text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">
                      {row.entity_id?.toString().substring(0, 8)}...
                    </span>
                  </td>
                </tr>
              ))}
              {data.activity.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-slate-500">
                    No recent activity to display.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
