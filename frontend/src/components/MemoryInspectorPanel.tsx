import { X, Database, BrainCircuit, Activity, Edit3 } from 'lucide-react';

export function MemoryInspectorPanel({ 
  node, 
  onClose 
}: { 
  node: any; 
  onClose: () => void; 
}) {
  if (!node) return null;

  return (
    <div className="w-full max-w-xl max-h-[80vh] bg-[#0f172a]/95 backdrop-blur-xl border border-slate-700/50 shadow-2xl rounded-2xl flex flex-col animate-in fade-in zoom-in-95 duration-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-800/80 flex items-center justify-between sticky top-0 z-10 bg-slate-900/50">
        <div className="flex items-center gap-2">
          <BrainCircuit size={18} style={{ color: node.color || '#60a5fa' }} />
          <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-200">{node.type}</h3>
        </div>
        <button 
          onClick={onClose}
          className="text-slate-400 hover:text-white bg-slate-800/50 hover:bg-slate-700/80 p-1.5 rounded-md transition-colors"
        >
          <X size={16} />
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        <h2 className="text-xl font-bold text-white mb-2">{node.name}</h2>
        
        <div className="flex items-center gap-2 mb-6">
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-slate-800 text-slate-400 border border-slate-700">
            ID: {node.id.length > 15 ? node.id.substring(0, 15) + '...' : node.id}
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-emerald-950 text-emerald-400 border border-emerald-900">
            Node Strength: {node.val}
          </span>
        </div>

        <div className="space-y-6">
          <div>
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
              <Database size={14} /> Semantic Data
            </h4>
            <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 font-sans text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
              {node.details || "No extended details available for this node."}
            </div>
          </div>

          {(node.type === 'Memory Fragment' || node.type === 'User Instructions') && (
            <div>
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                <Activity size={14} /> Neural Actions
              </h4>
              <button className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 py-2 rounded-lg text-sm transition-colors">
                <Edit3 size={14} />
                Edit Memory Encoding
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
