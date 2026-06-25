"use client";

import { useStore } from '@/store';
import { useState, useEffect } from 'react';

export function GlobalProgress() {
  const [mounted, setMounted] = useState(false);
  const pct = useStore(state => state.progressPct);
  const msg = useStore(state => state.progressMsg);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || (pct <= 0 && !msg)) return null;

  return (
    <>
      <div className="fixed top-0 left-0 w-full h-[8px] bg-slate-800/80 z-[100000] overflow-hidden pointer-events-none">
        <div 
          className="h-full bg-gradient-to-r from-rose-500 via-rose-300 to-rose-500 transition-all duration-300 ease-out animate-rgb-shift"
          style={{ width: `${pct * 100}%` }}
        />
      </div>
      <div className="fixed top-3 left-1/2 -translate-x-1/2 text-[13px] text-rose-300 font-semibold bg-slate-900/95 px-4 py-1.5 rounded-xl backdrop-blur-md border border-rose-500/40 shadow-xl z-[100001] text-center max-w-[80%] pointer-events-none">
        {msg}
      </div>
    </>
  );
}
