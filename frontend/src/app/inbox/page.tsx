"use client";

import { useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useState, useCallback, useRef, useEffect } from 'react';
import { useStore } from '@/store';
import { RefreshCw, Play, Filter, ChevronLeft, ChevronRight, Inbox as InboxIcon, Search, X, Mail, Paperclip, Clock } from 'lucide-react';
import { PreviewModal } from '@/components/PreviewModal';
import { cn } from '@/lib/utils';

const PAGE_SIZE = 15;

const STATUS_OPTIONS = [
  { value: 'PENDING', label: 'Pending', style: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  { value: 'APPROVED', label: 'Approved', style: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  { value: 'REJECTED', label: 'Rejected', style: 'bg-rose-500/10 text-rose-400 border-rose-500/20' },
];

function getStatusStyle(status: string) {
  return STATUS_OPTIONS.find(s => s.value === status)?.style || 'bg-slate-500/10 text-slate-400 border-slate-500/20';
}

function StatusDropdown({ emailId, currentStatus, onStatusChange }: { emailId: string; currentStatus: string; onStatusChange: (id: string, status: string) => void }) {
  const [open, setOpen] = useState(false);
  const [updating, setUpdating] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const handleSelect = async (status: string) => {
    if (status === currentStatus) { setOpen(false); return; }
    setUpdating(true);
    try {
      await axios.patch(`http://localhost:8000/api/emails/${encodeURIComponent(emailId)}/status`, { status });
      onStatusChange(emailId, status);
    } catch (err) {
      console.error('Failed to update status:', err);
    } finally {
      setUpdating(false);
      setOpen(false);
    }
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        disabled={updating}
        className={cn(
          "px-2.5 py-1 rounded-full text-xs font-semibold border transition-all cursor-pointer hover:ring-2 hover:ring-sky-500/30",
          getStatusStyle(currentStatus),
          updating && "opacity-50"
        )}
      >
        {updating ? '...' : (currentStatus || 'UNKNOWN')}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 z-50 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl shadow-black/50 py-1.5 min-w-[160px] animate-in fade-in zoom-in-95 duration-150">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={(e) => { e.stopPropagation(); handleSelect(opt.value); }}
              className={cn(
                "w-full text-left px-3.5 py-2 text-xs font-medium flex items-center gap-2 transition-colors",
                opt.value === currentStatus
                  ? "bg-sky-500/10 text-sky-400"
                  : "text-slate-300 hover:bg-slate-800 hover:text-slate-100"
              )}
            >
              <span className={cn("w-2 h-2 rounded-full shrink-0 border", opt.style)} />
              {opt.label}
              {opt.value === currentStatus && (
                <span className="ml-auto text-[10px] text-sky-500 font-bold">✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Inbox() {
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [accountFilter, setAccountFilter] = useState('ALL');
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const setProgress = useStore(state => state.setProgress);
  const queryClient = useQueryClient();

  useEffect(() => {
    axios.get('http://localhost:8000/api/emails/sync/status')
      .then(res => {
        if (res.data.last_synced_at) {
          setLastSyncedAt(res.data.last_synced_at);
        }
      })
      .catch(err => console.error('Failed to fetch sync status', err));
  }, []);

  // Preview modal state
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewTitle, setPreviewTitle] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);

  const { data: cvStatusData } = useQuery({
    queryKey: ['settings', 'cv'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/cv/status');
      return res.data.status_text;
    }
  });

  const isCvUploaded = cvStatusData && cvStatusData.startsWith('Active CV');

  const { data: gmailAccountsData } = useQuery({
    queryKey: ['settings', 'gmailAccounts'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/settings/gmail/accounts');
      return res.data.accounts || [];
    }
  });

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['emails', statusFilter, accountFilter, page, searchQuery],
    queryFn: async () => {
      const params = new URLSearchParams({
        status: statusFilter,
        account: accountFilter,
        limit: String(PAGE_SIZE),
        page: String(page),
      });
      if (searchQuery) params.set('search', searchQuery);
      const res = await axios.get(`http://localhost:8000/api/emails?${params.toString()}`);
      return res.data; // { emails: [], total: 0 }
    }
  });

  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set());

  const handleSearchChange = (val: string) => {
    setSearchInput(val);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      setSearchQuery(val);
      setPage(1);
    }, 500);
  };

  const clearSearch = () => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    setSearchInput('');
    setSearchQuery('');
    setPage(1);
  };

  const toggleSelectAll = () => {
    if (selectedEmails.size === data?.emails?.length && data?.emails?.length > 0) {
      setSelectedEmails(new Set());
    } else {
      setSelectedEmails(new Set(data?.emails?.map((e: any) => e.id) || []));
    }
  };

  const toggleSelectEmail = (emailId: string, e?: any) => {
    e.stopPropagation();
    const newSet = new Set(selectedEmails);
    if (newSet.has(emailId)) {
      newSet.delete(emailId);
    } else {
      newSet.add(emailId);
    }
    setSelectedEmails(newSet);
  };

  const handleBulkAction = async (action: 'archive' | 'read' | 'delete') => {
    if (selectedEmails.size === 0) return;
    try {
      await axios.post('http://localhost:8000/api/emails/bulk-action', {
        ids: Array.from(selectedEmails),
        action: action
      });
      setSelectedEmails(new Set());
      refetch();
    } catch (err) {
      console.error(`Bulk action ${action} failed`, err);
    }
  };

  const handleStatusChange = useCallback((emailId: string, newStatus: string) => {
    // Optimistically update the cache
    queryClient.setQueryData(['emails', statusFilter, page, searchQuery], (old: any) => {
      if (!old) return old;
      return {
        ...old,
        emails: old.emails.map((e: any) => e.id === emailId ? { ...e, status: newStatus } : e)
      };
    });
  }, [queryClient, statusFilter, page, searchQuery]);

  const handleSync = async () => {
    setProgress(0.5, 'Syncing emails... Please wait.');
    try {
      const res = await axios.post('http://localhost:8000/api/emails/sync');
      if (res.data.last_synced_at) {
        setLastSyncedAt(res.data.last_synced_at);
      }
      refetch();
    } catch (err) {
      console.error(err);
    } finally {
      setProgress(0, '');
    }
  };

  const handleWorkflow = async () => {
    setProgress(1.0, 'Running Workflow... This may take a while.');
    const { setChatOpen, addChatMessage, updateLastMessage } = useStore.getState();
    setChatOpen(true);
    addChatMessage({ role: 'assistant', content: '⚙️ **Starting Workflow...**\n' });
    
    try {
      const res = await axios.post('http://localhost:8000/api/workflow/run');
      const { workflow_id } = res.data;
      
      const ws = new WebSocket(`ws://localhost:8000/ws/logs/${workflow_id}`);
      
      ws.onmessage = (event) => {
        const text = event.data;
        if (text.trim() === '__DONE__') {
          ws.close();
        } else {
          updateLastMessage(prev => prev + text);
        }
      };
      
      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        updateLastMessage(prev => prev + "\n\n*(WebSocket disconnected. Connection lost.)*");
        setProgress(0, '');
      };
      
      ws.onclose = () => {
        refetch();
        setProgress(0, '');
      };

    } catch (err) {
      console.error(err);
      updateLastMessage(prev => prev + "\n\n*(Failed to run workflow. Please check the backend.)*");
      setProgress(0, '');
    }
  };

  const handleRowClick = useCallback(async (emailId: string, subject: string) => {
    setPreviewOpen(true);
    setPreviewTitle(subject || '(No Subject)');
    setPreviewLoading(true);
    setPreviewData(null);
    try {
      const res = await axios.get(`http://localhost:8000/api/emails/${encodeURIComponent(emailId)}`);
      setPreviewData(res.data);
    } catch (err) {
      console.error('Failed to load email detail:', err);
      setPreviewData(null);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 h-full flex flex-col">
      <div className="flex items-center justify-between mb-8">
        <div className="flex flex-col">
          <div className="flex items-center gap-4">
            <h2 className="text-3xl font-light tracking-wide text-sky-400 flex items-center gap-3" style={{ fontFamily: 'Georgia, serif' }}>
              <InboxIcon className="text-sky-500" size={28} />
            </h2>
            <div className="flex items-center gap-3 mt-1">
              <span className="bg-sky-500/10 text-sky-400 px-3 py-1 rounded-full border border-sky-500/20 text-xs font-semibold tracking-wide">
                {data?.total ?? 0} TOTAL EMAILS
              </span>
              {lastSyncedAt && (
                <span className="text-slate-500 flex items-center gap-1.5 text-xs font-medium">
                  <Clock size={12} />
                  Synced {new Date(lastSyncedAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                </span>
              )}
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Search Bar */}
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search by subject..."
              className="bg-slate-900 border border-slate-700 text-sm rounded-lg pl-9 pr-8 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50 w-56 placeholder:text-slate-600 transition-all focus:w-72"
            />
            {searchInput && (
              <button
                onClick={clearSearch}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Account Filter */}
          <div className="relative">
            <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select 
              value={accountFilter}
              onChange={(e) => { setAccountFilter(e.target.value); setPage(1); }}
              className="bg-slate-900 border border-slate-700 text-sm rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50 appearance-none cursor-pointer max-w-[200px] truncate"
            >
              <option value="ALL">All Accounts</option>
              {gmailAccountsData && gmailAccountsData.map((acc: string) => (
                <option key={acc} value={acc}>{acc === 'legacy' ? 'Legacy Account' : acc}</option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="relative">
            <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select 
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="bg-slate-900 border border-slate-700 text-sm rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50 appearance-none cursor-pointer"
            >
              <option value="ALL">All</option>
              <option value="PENDING">Pending</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>

          <div className="flex flex-col items-end justify-center">
            <button 
              onClick={handleSync}
              disabled={!isCvUploaded || isLoading}
              className={cn(
                "flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-slate-700 w-full justify-center",
                (!isCvUploaded) && "opacity-50 cursor-not-allowed hover:bg-slate-800"
              )}
              title={!isCvUploaded ? "Please upload your resume in Settings first." : "Sync & Refresh"}
            >
              <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
              Sync &amp; Refresh
            </button>
          </div>
          
          <button 
            onClick={handleWorkflow}
            disabled={!isCvUploaded}
            className={cn(
              "flex items-center gap-2 bg-sky-500 hover:bg-sky-400 text-slate-950 px-4 py-2 rounded-lg text-sm font-bold transition-colors shadow-lg shadow-sky-500/20",
              (!isCvUploaded) && "opacity-50 cursor-not-allowed hover:bg-sky-500 shadow-none text-slate-400"
            )}
            title={!isCvUploaded ? "Please upload your resume in Settings first." : "Run Workflow"}
          >
            <Play size={16} fill="currentColor" />
            Run Workflow
          </button>

          {!isCvUploaded && (
            <div className="text-[11px] font-semibold text-rose-400 max-w-[150px] text-right">
              ⚠️ Upload resume in Settings to enable Gmail Sync
            </div>
          )}
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl flex-1 flex flex-col overflow-hidden relative">
        {selectedEmails.size > 0 && (
          <div className="absolute top-0 left-0 right-0 z-20 bg-sky-900/90 backdrop-blur-md border-b border-sky-500/30 px-6 py-3 flex items-center justify-between shadow-lg shadow-sky-900/20">
            <span className="text-sm font-semibold text-sky-50">
              {selectedEmails.size} {selectedEmails.size === 1 ? 'conversation' : 'conversations'} selected
            </span>
            <div className="flex gap-3">
              <button onClick={() => handleBulkAction('read')} className="text-xs px-3 py-1.5 rounded bg-slate-800/50 hover:bg-slate-800 text-sky-100 transition-colors border border-sky-500/30">
                Mark as Read
              </button>
              <button onClick={() => handleBulkAction('archive')} className="text-xs px-3 py-1.5 rounded bg-slate-800/50 hover:bg-slate-800 text-sky-100 transition-colors border border-sky-500/30">
                Archive
              </button>
              <button onClick={() => handleBulkAction('delete')} className="text-xs px-3 py-1.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 transition-colors border border-rose-500/30">
                Delete
              </button>
            </div>
          </div>
        )}
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500"></div>
          </div>
        ) : error ? (
          <div className="flex-1 flex items-center justify-center text-rose-400">Failed to load emails</div>
        ) : (
          <>
            <div className="flex-1 overflow-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-800/50 text-slate-400 font-medium sticky top-0 backdrop-blur-md">
                  <tr>
                    <th className="px-4 py-4 font-medium w-12 text-center">
                      <input 
                        type="checkbox" 
                        onChange={toggleSelectAll} 
                        checked={data?.emails?.length > 0 && selectedEmails.size === data?.emails?.length}
                        className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-sky-500 focus:ring-sky-500/50 cursor-pointer"
                      />
                    </th>
                    <th className="px-6 py-4 font-medium">Date</th>
                    <th className="px-6 py-4 font-medium">Sender</th>
                    <th className="px-6 py-4 font-medium">Subject</th>
                    <th className="px-6 py-4 font-medium">Matched Skills</th>
                    <th className="px-6 py-4 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {data?.emails?.map((row: any, i: number) => (
                    <tr 
                      key={i} 
                      className={`hover:bg-slate-800/30 transition-colors cursor-pointer group ${selectedEmails.has(row.id) ? 'bg-sky-900/20' : ''}`}
                      onClick={() => handleRowClick(row.id, row.subject)}
                    >
                      <td className="px-4 py-4 text-center">
                        <input 
                          type="checkbox" 
                          checked={selectedEmails.has(row.id)}
                          onChange={(e) => toggleSelectEmail(row.id, e)}
                          onClick={(e) => e.stopPropagation()}
                          className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-sky-500 focus:ring-sky-500/50 cursor-pointer"
                        />
                      </td>
                      <td className="px-6 py-4 text-slate-400 whitespace-nowrap group-hover:text-slate-300">
                        {new Date(row.date).toLocaleString(undefined, {
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                        })}
                      </td>
                      <td className="px-6 py-4 text-slate-300 max-w-[200px] truncate">
                        <div className="flex items-center gap-2">
                          <span className="truncate">{row.sender || 'Unknown'}</span>
                          {row.thread_count > 1 && (
                            <span className="inline-flex shrink-0 items-center px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700" title={`${row.thread_count} messages in this conversation`}>
                              {row.thread_count}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-slate-200 max-w-[400px] font-medium transition-colors">
                        <div className="flex items-center gap-2">
                          <span className="truncate group-hover:text-sky-400">{row.subject || '(No Subject)'}</span>
                          {row.attachments_metadata && row.attachments_metadata.length > 5 && (
                            <span title="Has Attachments" className="text-slate-400">
                              <Paperclip size={14} />
                            </span>
                          )}
                          {row.labels && typeof row.labels === 'string' && row.labels.includes('"suspicious"') && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 shrink-0 uppercase">
                              Suspicious
                            </span>
                          )}
                          {row.labels && typeof row.labels === 'string' && row.labels.includes('"spam"') && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30 shrink-0 uppercase">
                              Spam
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1 max-w-[200px]">
                          {(() => {
                            try {
                              const skills = typeof row.matched_skills === 'string' ? JSON.parse(row.matched_skills) : row.matched_skills;
                              if (!skills || !Array.isArray(skills) || skills.length === 0) return <span className="text-slate-600 text-xs">—</span>;
                              return (
                                <>
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
                                </>
                              );
                            } catch (e) {
                              return <span className="text-slate-600 text-xs">—</span>;
                            }
                          })()}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <StatusDropdown
                          emailId={row.id}
                          currentStatus={row.status}
                          onStatusChange={handleStatusChange}
                        />
                      </td>
                    </tr>
                  ))}
                  {(!data || !data.emails || data.emails.length === 0) && (
                    <tr>
                      <td colSpan={4} className="px-6 py-24 text-center text-slate-500">
                        <InboxIcon size={48} className="mx-auto mb-4 opacity-20" />
                        <p>
                          {searchQuery 
                            ? `No emails found matching "${searchQuery}".`
                            : 'No emails found matching the current filter.'
                          }
                        </p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            
            <div className="bg-slate-800/50 border-t border-slate-800 p-4 flex items-center justify-between">
              <span className="text-sm text-slate-400">
                Showing page {page} of {totalPages || 1}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-2 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft size={18} />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="p-2 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Preview Modal */}
      <PreviewModal
        isOpen={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title={previewTitle}
        type="email"
        data={previewData}
        isLoading={previewLoading}
      />
    </div>
  );
}
