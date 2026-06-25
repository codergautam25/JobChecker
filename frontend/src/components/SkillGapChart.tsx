"use client";

import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

type SkillGapData = {
  skill: string;
  demand: number;
  has_skill: boolean;
};

export function SkillGapChart() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["intel", "skill-gap"],
    queryFn: async () => {
      const res = await axios.get("http://localhost:8000/api/intel/skill-gap");
      return res.data.skill_gap as SkillGapData[];
    },
  });

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 h-80 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500"></div>
      </div>
    );
  }

  if (error || !data || data.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 h-80 flex items-center justify-center text-slate-500">
        No skill gap data available yet. Build your profile and collect intel!
      </div>
    );
  }

  // Define custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const { skill, demand, has_skill } = payload[0].payload;
      return (
        <div className="bg-slate-800 border border-slate-700 p-3 rounded-lg shadow-xl text-xs">
          <p className="font-bold text-slate-200 mb-1">{skill}</p>
          <p className="text-slate-400">Demand: <span className="text-sky-400 font-medium">{demand} mentions</span></p>
          <p className="text-slate-400">Status: {has_skill ? <span className="text-emerald-400 font-medium">On Resume</span> : <span className="text-rose-400 font-medium">Missing</span>}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 h-80 flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-200">Skill Gap Analysis</h3>
        <div className="flex items-center gap-4 text-xs font-medium">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-emerald-500/80"></span>
            <span className="text-slate-400">On Resume</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-rose-500/80"></span>
            <span className="text-slate-400">Missing</span>
          </div>
        </div>
      </div>
      <div className="flex-1 w-full min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 0, left: 30, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
            <XAxis type="number" stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis 
              type="category" 
              dataKey="skill" 
              stroke="#cbd5e1" 
              fontSize={12} 
              tickLine={false} 
              axisLine={false} 
              width={100}
              tickFormatter={(value) => value.length > 15 ? value.substring(0, 15) + '...' : value}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#1e293b', opacity: 0.4 }} />
            <Bar dataKey="demand" radius={[0, 4, 4, 0]}>
              {data.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={entry.has_skill ? '#10b981' : '#f43f5e'} 
                  opacity={0.8} 
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
