"use client";

import { useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useState, useCallback } from 'react';
import { useStore } from '@/store';
import { Send, Globe, X, Filter, Camera, Mail, ExternalLink, Briefcase } from 'lucide-react';
import { PreviewModal } from '@/components/PreviewModal';

const getStatusBadge = (status: string) => {
  if (status === 'PENDING_APPROVAL') {
    return <span className="text-xs font-medium px-2.5 py-1 bg-amber-500/10 text-amber-400 rounded-full border border-amber-500/20">Pending</span>;
  }
  if (status === 'APPROVED' || status === 'APPLIED') {
    return <span className="text-xs font-medium px-2.5 py-1 bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20">Approved / Applied</span>;
  }
  if (status === 'REJECTED') {
    return <span className="text-xs font-medium px-2.5 py-1 bg-rose-500/10 text-rose-400 rounded-full border border-rose-500/20">Rejected</span>;
  }
  return <span className="text-xs font-medium px-2.5 py-1 bg-slate-500/10 text-slate-400 rounded-full border border-slate-500/20">{status}</span>;
};

function StatusDropdown({ approvalId, currentStatus, onStatusChange }: { approvalId: string; currentStatus: string; onStatusChange: (id: string, status: string) => void }) {
  const [loading, setLoading] = useState(false);

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    e.stopPropagation();
    const newStatus = e.target.value;
    setLoading(true);
    try {
      await axios.patch(`http://localhost:8000/api/approvals/${approvalId}/status`, { status: newStatus });
      onStatusChange(approvalId, newStatus);
    } catch (err) {
      console.error('Failed to update status', err);
    } finally {
      setLoading(false);
    }
  };

  let colorClass = "bg-slate-500/10 text-slate-400 border-slate-500/20";
  if (currentStatus === 'PENDING_APPROVAL') {
    colorClass = "bg-amber-500/10 text-amber-400 border-amber-500/20";
  } else if (currentStatus === 'APPROVED' || currentStatus === 'APPLIED') {
    colorClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  } else if (currentStatus === 'REJECTED') {
    colorClass = "bg-rose-500/10 text-rose-400 border-rose-500/20";
  }

  return (
    <div className="relative inline-block" onClick={(e) => e.stopPropagation()}>
      <select
        value={currentStatus}
        onChange={handleChange}
        disabled={loading}
        className={`appearance-none text-xs font-medium px-2.5 py-1 pr-6 rounded-full border transition-colors outline-none cursor-pointer ${colorClass} ${loading ? 'opacity-50' : ''}`}
      >
        <option value="PENDING_APPROVAL" className="bg-slate-900 text-slate-200 text-xs">Pending</option>
        <option value="APPLIED" className="bg-slate-900 text-slate-200 text-xs">Applied</option>
        <option value="INTERVIEWING" className="bg-slate-900 text-slate-200 text-xs">Interviewing</option>
        <option value="REJECTED" className="bg-slate-900 text-slate-200 text-xs">Rejected</option>
      </select>
      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-1.5 text-current opacity-70">
        <svg className="fill-current h-3 w-3" viewBox="0 0 20 20">
          <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
        </svg>
      </div>
    </div>
  );
}

function MatchedSkills({ matched_skills }: { matched_skills: string | string[] | null | undefined }) {
  if (!matched_skills) return null;
  let skills: string[] = [];
  try {
    skills = typeof matched_skills === 'string' ? JSON.parse(matched_skills) : matched_skills;
  } catch (e) {
    return null;
  }
  if (!Array.isArray(skills) || skills.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-2 mb-2">
      {skills.slice(0, 3).map((skill: string, idx: number) => (
        <span key={idx} className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 whitespace-nowrap">
          {skill}
        </span>
      ))}
      {skills.length > 3 && (
        <span title={skills.slice(3).join(', ')} className="cursor-help px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">
          +{skills.length - 3}
        </span>
      )}
    </div>
  );
}

export default function Approvals() {
  const setProgress = useStore(state => state.setProgress);
  const setChatOpen = useStore(state => state.setChatOpen);
  const addChatMessage = useStore(state => state.addChatMessage);
  const queryClient = useQueryClient();

  // Preview modal state
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewTitle, setPreviewTitle] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);

  // Screenshot modal state
  const [screenshotOpen, setScreenshotOpen] = useState(false);
  const [screenshotUrl, setScreenshotUrl] = useState('');
  const [screenshotTitle, setScreenshotTitle] = useState('');
  const [selectedJobForPreview, setSelectedJobForPreview] = useState<any>(null);

  const handleViewScreenshot = useCallback((id: string, title: string) => {
    setScreenshotUrl(`http://localhost:8000/api/approvals/screenshot/${id}`);
    setScreenshotTitle(title);
    setScreenshotOpen(true);
  }, []);

  // Filter state
  const [statusFilter, setStatusFilter] = useState('PENDING_APPROVAL');
  const [viewMode, setViewMode] = useState<'list' | 'kanban'>('list');
  const [accountFilter, setAccountFilter] = useState('ALL');
  const [activeTab, setActiveTab] = useState<'emails' | 'portals' | 'interviews' | 'jobs'>('emails');

  const handleStatusChange = useCallback((id: string, newStatus: string) => {
    queryClient.setQueryData(['approvals', 'all', statusFilter, accountFilter], (old: any) => {
      if (!old) return old;
      return old.map((a: any) => a.id === id ? { ...a, status: newStatus } : a);
    });
  }, [queryClient, statusFilter, accountFilter]);

  const { data: gmailAccountsData } = useQuery({
    queryKey: ['settings', 'gmailAccounts'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/settings/gmail/accounts');
      return res.data.accounts || [];
    }
  });

  const { data: allApprovals, isLoading: approvalsLoading } = useQuery({
    queryKey: ['approvals', 'all', statusFilter, accountFilter],
    queryFn: async () => {
      const res = await axios.get(`http://localhost:8000/api/approvals/all?status=${statusFilter}&account=${accountFilter}`);
      return res.data.approvals;
    }
  });

  const { data: scrapedPostsData, isLoading: scrapedPostsLoading } = useQuery({
    queryKey: ['intel', 'posts'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/intel/posts?limit=100');
      return res.data.posts || [];
    }
  });

  const handleDraftEmail = async (jobId: string) => {
    setProgress(0.3, 'Generating cold application draft...');
    try {
      const res = await axios.post(`http://localhost:8000/api/intel/jobs/${encodeURIComponent(jobId)}/draft_email`);
      setProgress(0, '');
      setActiveTab('emails');
      alert("Application email draft generated successfully! You can review and send it under 'Email Drafts' section.");
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    } catch (err: any) {
      setProgress(0, '');
      alert(err.response?.data?.error || "Failed to generate draft email.");
    }
  };

  const scrapedJobs = scrapedPostsData?.filter((post: any) => post.id && post.id.startsWith('linkedin_job_')) || [];

  const sentMails = allApprovals?.filter((a: any) => a.action_type === 'sent_mail' || a.action_type === 'send_email');
  const agentApplies = allApprovals?.filter((a: any) => a.action_type === 'agent_apply');
  const interviews = allApprovals?.filter((a: any) => a.action_type === 'interview');

  const handlePreview = useCallback(async (id: string, title: string) => {
    setPreviewOpen(true);
    setPreviewTitle(title || 'Approval Detail');
    setPreviewLoading(true);
    setPreviewData(null);
    try {
      const res = await axios.get(`http://localhost:8000/api/approvals/${encodeURIComponent(id)}`);
      setPreviewData(res.data);
    } catch (err) {
      console.error('Failed to load approval detail:', err);
      setPreviewData(null);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const handleReview = async (type: string, id: string) => {
    const setActiveReviewId = useStore.getState().setActiveReviewId;
    setActiveReviewId(id);
    setChatOpen(true);
    
    addChatMessage({ 
      role: 'user', 
      content: `I want to review ${type === 'email' ? 'email draft' : 'portal application'} with ID: ${id}`
    });
    
    try {
      addChatMessage({ role: 'assistant', content: '' }); // Initial empty message
      
      const res = await fetch('http://localhost:8000/api/chat/start_review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approval_id: id, type: type })
      });
      
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await res.json();
        if (data.poll) {
          const ws = new WebSocket(`ws://localhost:8000/ws/logs/${id}`);
          
          ws.onmessage = (event) => {
            const text = event.data;
            if (text === '__DONE__') {
              ws.close();
            } else {
              useStore.getState().updateLastMessage(prev => prev + text);
            }
          };
          
          ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            useStore.getState().updateLastMessage(prev => prev + "\n\n*(WebSocket disconnected. Connection lost.)*");
          };
          
          return;
        }
      }
      
      if (!res.body) throw new Error('No response body');
      
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        useStore.getState().updateLastMessage(prev => prev + chunk);
      }
    } catch (err) {
      console.error(err);
      useStore.getState().updateLastMessage("*(Failed to start review session. Please try again.)*");
    }
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-12">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-3xl font-light tracking-wide text-sky-400" style={{ fontFamily: 'Georgia, serif' }}>
            Action Center
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Total Pending Approvals: <span className="text-slate-200 font-medium">{allApprovals?.length || 0}</span>
          </p>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex bg-slate-900 border border-slate-700 rounded-lg p-1">
            <button 
              onClick={() => setViewMode('list')}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${viewMode === 'list' ? 'bg-slate-700 text-slate-200' : 'text-slate-500 hover:text-slate-300'}`}
            >
              List
            </button>
            <button 
              onClick={() => { setViewMode('kanban'); setStatusFilter('ALL'); }}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${viewMode === 'kanban' ? 'bg-slate-700 text-slate-200' : 'text-slate-500 hover:text-slate-300'}`}
            >
              Kanban
            </button>
          </div>
          <div className="relative">
            <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select 
              value={accountFilter}
              onChange={(e) => setAccountFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-sm rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50 appearance-none cursor-pointer max-w-[200px] truncate"
            >
              <option value="ALL">All Accounts</option>
              {gmailAccountsData && gmailAccountsData.map((acc: string) => (
                <option key={acc} value={acc}>{acc === 'legacy' ? 'Legacy Account' : acc}</option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select 
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-sm rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50 appearance-none cursor-pointer"
            >
              <option value="ALL">All Status</option>
              <option value="PENDING_APPROVAL">Pending</option>
              <option value="APPLIED">Applied</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>
        </div>
      </div>

      
      {viewMode === 'kanban' ? (
        <div className="flex gap-4 overflow-x-auto pb-8 snap-x" style={{ minHeight: '600px' }}>
          {['PENDING_APPROVAL', 'APPLIED', 'INTERVIEWING', 'REJECTED'].map((colStatus) => {
            let colName = "Pending";
            let borderColor = "border-amber-500/20";
            let headerColor = "text-amber-400";
            if (colStatus === 'APPLIED') { colName = "Applied"; borderColor = "border-sky-500/20"; headerColor = "text-sky-400"; }
            if (colStatus === 'INTERVIEWING') { colName = "Interviewing"; borderColor = "border-emerald-500/20"; headerColor = "text-emerald-400"; }
            if (colStatus === 'REJECTED') { colName = "Rejected / Offer"; borderColor = "border-rose-500/20"; headerColor = "text-rose-400"; }
            
            const colItems = (allApprovals || []).filter((a: any) => {
              if (colStatus === 'INTERVIEWING') return a.status === 'INTERVIEWING' || a.status === 'SCHEDULED';
              return a.status === colStatus;
            });

            return (
              <div 
                key={colStatus}
                className={`flex-shrink-0 w-80 bg-slate-900/50 border ${borderColor} rounded-xl flex flex-col snap-center`}
                onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }}
                onDrop={(e) => {
                  e.preventDefault();
                  const itemId = e.dataTransfer.getData('text/plain');
                  if (itemId) handleStatusChange(itemId, colStatus);
                  
                  // Also hit backend
                  axios.patch(`http://localhost:8000/api/approvals/${itemId}/status`, { status: colStatus }).catch(err => console.error(err));
                }}
              >
                <div className={`px-4 py-3 border-b ${borderColor} flex items-center justify-between`}>
                  <h3 className={`font-bold text-sm ${headerColor}`}>{colName}</h3>
                  <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full">{colItems.length}</span>
                </div>
                
                <div className="flex-1 p-3 flex flex-col gap-3 overflow-y-auto custom-scrollbar">
                  {colItems.map((row: any) => {
                    const payload = JSON.parse(row.payload);
                    return (
                      <div 
                        key={row.id}
                        draggable
                        onDragStart={(e) => e.dataTransfer.setData('text/plain', row.id)}
                        className="bg-slate-800 border border-slate-700 hover:border-slate-500 rounded-lg p-4 cursor-grab active:cursor-grabbing transition-colors"
                        onClick={() => handlePreview(row.id, payload.job_title || payload.email_subject || 'Detail')}
                      >
                        <div className="flex justify-between items-start mb-2">
                          <span className="text-[10px] font-mono text-slate-500">{row.id.substring(0,6)}</span>
                          <span className="text-[10px] bg-slate-900 px-1.5 py-0.5 rounded text-slate-400 uppercase tracking-wider">{row.action_type.split('_')[0]}</span>
                        </div>
                        <h4 className="font-semibold text-slate-200 text-sm mb-1">{payload.job_title || payload.email_subject || 'Approval'}</h4>
                        <p className="text-xs text-slate-400 truncate">{payload.company_name || payload.email_sender || 'Unknown'}</p>
                      </div>
                    )
                  })}
                  {colItems.length === 0 && (
                    <div className="text-center py-8 text-xs text-slate-600 border border-dashed border-slate-700/50 rounded-lg">
                      Drop items here
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="space-y-6 flex flex-col">
          {/* Beautiful Tab Bar */}
          <div className="flex flex-wrap border-b border-slate-800/80 pb-px mb-2 bg-slate-900/30 p-1 rounded-xl gap-1.5 w-fit">
            <button
              onClick={() => setActiveTab('emails')}
              className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 duration-300 border ${
                activeTab === 'emails'
                  ? 'bg-gradient-to-r from-indigo-500/20 to-indigo-600/20 text-indigo-400 border-indigo-500/30 shadow-lg shadow-indigo-500/5'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border-transparent'
              }`}
            >
              <Send size={16} />
              <span>Email Drafts</span>
              <span className={`ml-1.5 px-2 py-0.5 text-xs font-semibold rounded-full ${
                activeTab === 'emails' ? 'bg-indigo-500/30 text-indigo-300 border border-indigo-500/20' : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}>
                {sentMails?.length || 0}
              </span>
            </button>
            
            <button
              onClick={() => setActiveTab('portals')}
              className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 duration-300 border ${
                activeTab === 'portals'
                  ? 'bg-gradient-to-r from-sky-500/20 to-sky-600/20 text-sky-400 border-sky-500/30 shadow-lg shadow-sky-500/5'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border-transparent'
              }`}
            >
              <Globe size={16} />
              <span>Portal Applications</span>
              <span className={`ml-1.5 px-2 py-0.5 text-xs font-semibold rounded-full ${
                activeTab === 'portals' ? 'bg-sky-500/30 text-sky-300 border border-sky-500/20' : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}>
                {agentApplies?.length || 0}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('interviews')}
              className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 duration-300 border ${
                activeTab === 'interviews'
                  ? 'bg-gradient-to-r from-emerald-500/20 to-emerald-600/20 text-emerald-400 border-emerald-500/30 shadow-lg shadow-emerald-500/5'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border-transparent'
              }`}
            >
              <Mail size={16} />
              <span>Interviews</span>
              <span className={`ml-1.5 px-2 py-0.5 text-xs font-semibold rounded-full ${
                activeTab === 'interviews' ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-500/20' : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}>
                {interviews?.length || 0}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('jobs')}
              className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 duration-300 border ${
                activeTab === 'jobs'
                  ? 'bg-gradient-to-r from-amber-500/20 to-amber-600/20 text-amber-400 border-amber-500/30 shadow-lg shadow-amber-500/5'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border-transparent'
              }`}
            >
              <Briefcase size={16} />
              <span>LinkedIn Jobs</span>
              <span className={`ml-1.5 px-2 py-0.5 text-xs font-semibold rounded-full ${
                activeTab === 'jobs' ? 'bg-amber-500/30 text-amber-300 border border-amber-500/20' : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}>
                {scrapedJobs?.length || 0}
              </span>
            </button>
          </div>

          {/* Tab Contents */}
          <div className="flex-1 min-h-0 pt-2">
            {activeTab === 'emails' && (
              <section className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="flex items-center gap-2 mb-4">
                  <div className="p-2 bg-indigo-500/10 rounded-lg">
                    <Send size={20} className="text-indigo-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-200">
                    {statusFilter === 'PENDING_APPROVAL' ? 'Email Drafts Pending Review' : 'Email Drafts'}
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {approvalsLoading ? (
                    [1, 2, 3].map(i => (
                      <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-40 animate-pulse">
                        <div className="h-4 bg-slate-800 rounded w-3/4 mb-4"></div>
                        <div className="h-3 bg-slate-800 rounded w-1/2 mb-2"></div>
                        <div className="h-3 bg-slate-800 rounded w-5/6"></div>
                      </div>
                    ))
                  ) : sentMails?.map((row: any, i: number) => {
                    const payload = JSON.parse(row.payload);
                    return (
                      <div 
                        key={i} 
                        className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-indigo-500/50 transition-all group flex flex-col cursor-pointer"
                        onClick={() => handlePreview(row.id, payload.draft?.subject || 'Email Draft')}
                      >
                        <div className="flex justify-between items-start mb-3">
                          <StatusDropdown approvalId={row.id} currentStatus={row.status} onStatusChange={handleStatusChange} />
                          <span className="text-xs text-slate-500 font-mono">
                            {row.id.substring(0, 8)}
                          </span>
                        </div>
                        <h4 className="font-semibold text-slate-200 mb-1 break-words">
                          {payload.draft?.subject || 'No Subject'}
                        </h4>
                        <div className="flex-1 flex flex-col gap-1.5 mb-3">
                          <p className="text-sm text-slate-400 break-words">To: {payload.draft?.to || 'Unknown'}</p>
                          {payload.classification?.category && (
                            <span className="text-[11px] font-medium text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded w-fit">
                              {payload.classification.category}
                            </span>
                          )}
                        </div>
                        
                        <div className="flex gap-2 mt-auto pt-4 border-t border-slate-800/50 opacity-0 group-hover:opacity-100 transition-opacity">
                          {row.status === 'PENDING_APPROVAL' ? (
                            <button 
                              onClick={(e) => { e.stopPropagation(); handleReview('email', row.id); }}
                              className="flex-1 bg-indigo-500 hover:bg-indigo-400 text-slate-950 font-semibold py-1.5 rounded-lg text-sm transition-colors"
                            >
                              Review &amp; Approve
                            </button>
                          ) : (
                            <div className="flex-1 text-center py-1.5 text-xs text-slate-500 italic">No actions available</div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                  {sentMails?.length === 0 && (
                    <div className="col-span-full py-12 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 bg-slate-900/50">
                      No pending email drafts at the moment.
                    </div>
                  )}
                </div>
              </section>
            )}

            {activeTab === 'portals' && (
              <section className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="flex items-center gap-2 mb-4">
                  <div className="p-2 bg-sky-500/10 rounded-lg">
                    <Globe size={20} className="text-sky-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-200">
                    {statusFilter === 'PENDING_APPROVAL' ? 'Portal Applications Pending Execution' : 'Portal Applications'}
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {approvalsLoading ? (
                     [1, 2].map(i => (
                      <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-40 animate-pulse">
                        <div className="h-4 bg-slate-800 rounded w-2/3 mb-4"></div>
                        <div className="h-3 bg-slate-800 rounded w-1/3 mb-2"></div>
                        <div className="h-3 bg-slate-800 rounded w-4/5"></div>
                      </div>
                    ))
                  ) : agentApplies?.map((row: any, i: number) => {
                    const payload = JSON.parse(row.payload);
                    return (
                      <div 
                        key={i} 
                        className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-sky-500/50 transition-all group flex flex-col cursor-pointer"
                        onClick={() => handlePreview(row.id, payload.job_title || payload.email_subject || 'Application')}
                      >
                        <div className="flex justify-between items-start mb-3">
                          <StatusDropdown approvalId={row.id} currentStatus={row.status} onStatusChange={handleStatusChange} />
                          <div className="flex items-center gap-2">
                            {(payload.apply_url || payload.job_info?.url) && (
                              <a
                                href={payload.apply_url || payload.job_info?.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20 hover:bg-sky-500/20 transition-colors"
                                title="Open Job Posting"
                              >
                                <ExternalLink size={14} />
                              </a>
                            )}
                            {row.has_screenshot && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleViewScreenshot(row.id, payload.job_title || payload.email_subject || 'Application');
                                }}
                                className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                                title="View application screenshot"
                              >
                                <Camera size={14} />
                              </button>
                            )}
                            <span className="text-xs text-slate-500 font-mono">
                              {row.id.substring(0, 8)}
                            </span>
                          </div>
                        </div>
                        <h4 className="font-semibold text-slate-200 mb-1 break-words">
                          {payload.job_title || payload.email_subject || 'Application'}
                        </h4>
                        <div className="flex-1 flex flex-col gap-1.5 mb-3">
                          <p className="text-sm text-slate-400 break-words">@ {payload.company_name || 'Unknown Company'}</p>
                          {(payload.job_info?.location || payload.suggested_resume) && (
                            <div className="flex items-center gap-1.5 overflow-hidden mt-0.5">
                              {payload.job_info?.location && (
                                <span className="text-[11px] font-medium text-slate-400 bg-slate-800 border border-slate-700 px-2 py-0.5 rounded truncate max-w-[120px]" title={payload.job_info.location}>
                                  {payload.job_info.location}
                                </span>
                              )}
                              {payload.suggested_resume && (
                                <span className="text-[11px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded flex-shrink-0">
                                  Resume ready
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        <MatchedSkills matched_skills={row.matched_skills} />
                        
                        {row.status === 'PENDING_APPROVAL' ? (
                          <div className="flex gap-2 mt-auto pt-4 border-t border-slate-800/50 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button 
                              onClick={(e) => { e.stopPropagation(); handleReview('portal', row.id); }}
                              className="flex-1 bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold py-1.5 rounded-lg text-sm transition-colors"
                            >
                              Automate Application
                            </button>
                            <button 
                              onClick={(e) => e.stopPropagation()}
                              className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors border border-slate-700"
                            >
                              <X size={18} />
                            </button>
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                  {agentApplies?.length === 0 && (
                    <div className="col-span-full py-12 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 bg-slate-900/50">
                      No portal applications pending execution.
                    </div>
                  )}
                </div>
              </section>
            )}

            {activeTab === 'interviews' && (
              <section className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="flex items-center gap-2 mb-4">
                  <div className="p-2 bg-emerald-500/10 rounded-lg">
                    <Mail size={20} className="text-emerald-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-200">
                    {statusFilter === 'PENDING_APPROVAL' ? 'Interview Invitations Pending' : 'Interview Invitations'}
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {approvalsLoading ? (
                     [1].map(i => (
                      <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-40 animate-pulse">
                        <div className="h-4 bg-slate-800 rounded w-2/3 mb-4"></div>
                        <div className="h-3 bg-slate-800 rounded w-1/3 mb-2"></div>
                        <div className="h-3 bg-slate-800 rounded w-4/5"></div>
                      </div>
                    ))
                  ) : interviews?.map((row: any, i: number) => {
                    const payload = JSON.parse(row.payload);
                    return (
                      <div 
                        key={i} 
                        className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-emerald-500/50 transition-all group flex flex-col cursor-pointer"
                        onClick={() => handlePreview(row.id, payload.email_subject || 'Interview')}
                      >
                        <div className="flex justify-between items-start mb-3">
                          <StatusDropdown approvalId={row.id} currentStatus={row.status} onStatusChange={handleStatusChange} />
                          <span className="text-xs text-slate-500 font-mono">
                            {row.id.substring(0, 8)}
                          </span>
                        </div>
                        <h4 className="font-semibold text-slate-200 mb-1 break-words">
                          {payload.email_subject || 'Interview Invitation'}
                        </h4>
                        <div className="flex-1 flex flex-col gap-1.5 mb-3">
                          <p className="text-sm text-slate-400 break-words">From: {payload.email_sender || 'Unknown Sender'}</p>
                          {payload.classification?.category && (
                            <span className="text-[11px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded w-fit">
                              {payload.classification.category}
                            </span>
                          )}
                        </div>
                        <MatchedSkills matched_skills={row.matched_skills} />
                      </div>
                    )
                  })}
                  {interviews?.length === 0 && (
                    <div className="col-span-full py-12 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 bg-slate-900/50">
                      No pending interview invitations.
                    </div>
                  )}
                </div>
              </section>
            )}

            {activeTab === 'jobs' && (
              <section className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="flex items-center gap-2 mb-4">
                  <div className="p-2 bg-indigo-500/10 rounded-lg">
                    <Briefcase size={20} className="text-indigo-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-200">
                    LinkedIn Job Opportunities (Scraped)
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {scrapedPostsLoading ? (
                    [1, 2, 3].map(i => (
                      <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-40 animate-pulse">
                        <div className="h-4 bg-slate-800 rounded w-3/4 mb-4"></div>
                        <div className="h-3 bg-slate-800 rounded w-1/2 mb-2"></div>
                        <div className="h-3 bg-slate-800 rounded w-5/6"></div>
                      </div>
                    ))
                  ) : scrapedJobs?.map((post: any, i: number) => {
                    return (
                      <div 
                        key={i} 
                        className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-indigo-500/50 transition-all group flex flex-col cursor-pointer"
                        onClick={() => setSelectedJobForPreview(post)}
                      >
                        <div className="flex justify-between items-start mb-3">
                          <span className="text-xs text-slate-500 font-mono">
                            {post.id.substring(13, 21)}
                          </span>
                          <a
                            href={post.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 hover:bg-indigo-500/20 transition-colors"
                            title="Apply Directly"
                          >
                            <ExternalLink size={14} />
                          </a>
                        </div>
                        <h4 className="font-semibold text-slate-200 mb-1 break-words">
                          {post.text_content.split('\n')[0].replace('Job Title: ', '')}
                        </h4>
                        <div className="flex-1 flex flex-col gap-1.5 mb-3">
                          <p className="text-sm text-slate-400 break-words">@ {post.author}</p>
                        </div>
                        
                        <MatchedSkills matched_skills={post.matched_skills} />
                        
                        <div className="flex gap-2 mt-auto pt-4 border-t border-slate-800/50 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button 
                            onClick={(e) => { e.stopPropagation(); handleDraftEmail(post.id); }}
                            className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-1.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-1"
                          >
                            <Mail size={14} /> Draft Referral Email
                          </button>
                        </div>
                      </div>
                    )
                  })}
                  {scrapedJobs?.length === 0 && (
                    <div className="col-span-full py-12 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 bg-slate-900/50">
                      No scraped LinkedIn jobs available.
                    </div>
                  )}
                </div>
              </section>
            )}
          </div>
        </div>

      )}

      {/* Preview Modal */}
      <PreviewModal
        isOpen={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title={previewTitle}
        type="approval"
        data={previewData}
        isLoading={previewLoading}
      />

      {/* Screenshot Popup */}
      {screenshotOpen && (
        <div 
          className="fixed inset-0 z-[9999] flex items-center justify-center p-6"
          onClick={() => setScreenshotOpen(false)}
        >
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200" />
          <div 
            className="relative max-w-4xl max-h-[85vh] w-full bg-[#0f172a] border border-slate-700/80 rounded-2xl shadow-2xl shadow-black/50 flex flex-col animate-in fade-in zoom-in-95 duration-300 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/60 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 bg-emerald-500/10 rounded-lg">
                  <Camera size={16} className="text-emerald-400" />
                </div>
                <h3 className="text-sm font-semibold text-slate-200 truncate">
                  Screenshot — {screenshotTitle}
                </h3>
              </div>
              <button
                onClick={() => setScreenshotOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            {/* Image */}
            <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-slate-950/50">
              <img
                src={screenshotUrl}
                alt="Application proof screenshot"
                className="max-w-full max-h-[70vh] object-contain rounded-lg border border-slate-800"
              />
            </div>
          </div>
        </div>
      )}

      {/* Job Preview Modal */}
      {selectedJobForPreview && (
        <div 
          className="fixed inset-0 z-[9999] flex items-center justify-center p-6"
          onClick={() => setSelectedJobForPreview(null)}
        >
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200" />
          <div 
            className="relative max-w-2xl max-h-[80vh] w-full bg-[#0f172a] border border-slate-700/80 rounded-2xl shadow-2xl shadow-black/50 flex flex-col animate-in fade-in zoom-in-95 duration-300 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-900/60 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 bg-indigo-500/10 rounded-lg">
                  <Briefcase size={16} className="text-indigo-400" />
                </div>
                <h3 className="text-sm font-semibold text-slate-200 truncate">
                  {selectedJobForPreview.text_content.split('\n')[0].replace('Job Title: ', '')}
                </h3>
              </div>
              <button
                onClick={() => setSelectedJobForPreview(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            
            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
              <div>
                <h4 className="text-sm font-semibold text-slate-200">{selectedJobForPreview.author}</h4>
                <a href={selectedJobForPreview.url} target="_blank" rel="noreferrer" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mt-1 w-fit">
                  View on LinkedIn <ExternalLink size={10} />
                </a>
              </div>
              
              <MatchedSkills matched_skills={selectedJobForPreview.matched_skills} />
              
              <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-4">
                <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed max-h-96 overflow-y-auto">
                  {selectedJobForPreview.text_content}
                </pre>
              </div>
            </div>
            
            {/* Footer */}
            <div className="px-5 py-3 border-t border-slate-800 bg-slate-900/40 flex justify-end gap-2 shrink-0">
              <button
                onClick={() => setSelectedJobForPreview(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-semibold transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => {
                  const jobId = selectedJobForPreview.id;
                  setSelectedJobForPreview(null);
                  handleDraftEmail(jobId);
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors flex items-center gap-1"
              >
                <Mail size={12} /> Draft Referral Email
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
