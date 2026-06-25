"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Inbox, CheckSquare, Settings, Database, Cpu, Radar } from 'lucide-react';
import { useState, useEffect } from 'react';
import axios from 'axios';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/inbox', label: 'Inbox', icon: Inbox },
  { href: '/approvals', label: 'Approvals', icon: CheckSquare },
  { href: '/intel', label: 'LinkedIn Intel', icon: Radar },
  { href: '/memory', label: 'Memory', icon: Database },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [quota, setQuota] = useState({ tokens_total: 0, cost_total: 0.0 });

  useEffect(() => {
    const fetchQuota = () => {
      axios.get('http://localhost:8000/api/quota')
        .then(res => setQuota(res.data))
        .catch(err => console.error("Quota fetch error", err));
    };
    
    // Initial fetch
    fetchQuota();
    
    // Poll every 5 seconds to keep it active and accurate
    const interval = setInterval(fetchQuota, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-64 border-r border-slate-800 bg-[#0f172a] h-full flex flex-col shrink-0">
      <div className="p-6 flex flex-col h-full">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-400 to-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/20 shrink-0">
            <span className="text-white font-bold text-xl">CT</span>
          </div>
          <h1 className="text-lg font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent truncate">
            Career Tracker
          </h1>
        </div>
        
        <nav className="flex flex-col gap-2 flex-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            
            return (
              <Link 
                key={item.href} 
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive 
                    ? 'bg-sky-500/10 text-sky-400 shadow-[inset_2px_0_0_0_#38bdf8]' 
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                }`}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="mt-8 pt-6 border-t border-slate-800">
          <div className="flex flex-col p-4 rounded-xl bg-slate-800/30 border border-slate-800/50 hover:bg-slate-800/50 transition-colors">
            <h1 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">
              Total API Usage
            </h1>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 shrink-0">
                <Cpu size={16} className="text-emerald-400" />
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-semibold text-emerald-400">
                  {(quota.tokens_total / 1000).toFixed(1)}k <span className="text-[10px] font-medium text-emerald-400/70">TOKENS</span>
                </span>
                <span className="text-xs font-medium text-slate-500 mt-0.5">
                  Est. Cost: ${quota.cost_total.toFixed(3)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
