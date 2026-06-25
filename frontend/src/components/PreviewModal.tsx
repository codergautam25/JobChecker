"use client";

import { useEffect, useRef, useState } from 'react';
import { X, Mail, Briefcase, User, FileText, Sparkles, ExternalLink, Clock, Camera, Paperclip, ChevronUp, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

type PreviewModalProps = {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  type: 'email' | 'approval';
  data: any;
  isLoading?: boolean;
};

export function PreviewModal({ isOpen, onClose, title, type, data, isLoading }: PreviewModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 sm:p-6 md:p-8"
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200" />

      {/* Modal */}
      <div className="relative w-full max-w-3xl max-h-[90vh] bg-[#0f172a] border border-slate-700/80 rounded-2xl shadow-2xl shadow-black/50 flex flex-col animate-in fade-in zoom-in-95 slide-in-from-bottom-4 duration-300 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/60 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className={cn(
              "p-2 rounded-lg shrink-0",
              type === 'email' ? "bg-sky-500/10" : "bg-indigo-500/10"
            )}>
              {type === 'email' 
                ? <Mail size={18} className="text-sky-400" /> 
                : <Briefcase size={18} className="text-indigo-400" />}
            </div>
            <h3 className="text-lg font-semibold text-slate-100 truncate">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors shrink-0"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 custom-scrollbar">
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-sky-500" />
            </div>
          ) : data ? (
            type === 'email' ? <EmailPreview data={data} /> : <ApprovalPreview data={data} />
          ) : (
            <p className="text-slate-500 text-center py-16">No data available.</p>
          )}
        </div>
      </div>
    </div>
  );
}


/* ─── Email Preview ────────────────────────────────── */

function EmailPreview({ data }: { data: any }) {
  const hasThread = data.thread_messages && data.thread_messages.length > 0;

  return (
    <div className="space-y-6">
      {hasThread && (
        <div className="space-y-4">
          <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Previous Messages ({data.thread_messages.length})</h4>
          {data.thread_messages.map((msg: any) => (
            <div key={msg.id} className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 opacity-70 hover:opacity-100 transition-opacity">
              <div className="flex items-center justify-between mb-3 border-b border-slate-800/50 pb-2">
                <div className="flex flex-col">
                  <span className="font-semibold text-slate-300 text-sm">{msg.sender}</span>
                  <span className="text-[10px] text-slate-500 uppercase tracking-wide">{formatDate(msg.date)}</span>
                </div>
              </div>
              <div className="bg-white rounded-lg overflow-hidden border border-slate-700/30">
                {msg.body_html ? (
                   <iframe
                     srcDoc={injectLightMode(msg.body_html)}
                     className="w-full border-none rounded-lg"
                     style={{ height: '200px' }}
                     sandbox="allow-same-origin"
                     title={`Email from ${msg.sender}`}
                   />
                ) : (
                   <pre className="text-xs text-slate-800 whitespace-pre-wrap font-mono p-4 max-h-40 overflow-y-auto">{msg.body_text}</pre>
                )}
              </div>
            </div>
          ))}
          <div className="flex items-center gap-4 py-4">
            <div className="h-px bg-slate-800 flex-1"></div>
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider shrink-0">Latest Message</h4>
            <div className="h-px bg-slate-800 flex-1"></div>
          </div>
        </div>
      )}

      {/* Meta Info */}
      <InfoCard title="Email Details" icon={<Mail size={16} className="text-sky-400" />}>
        <InfoGrid>
          <InfoItem label="From" value={data.sender || '—'} />
          <InfoItem label="To" value={data.recipient || '—'} />
          <InfoItem label="Date" value={formatDate(data.date)} />
          <InfoItem label="Status">
            <StatusBadge status={data.status} />
          </InfoItem>
        </InfoGrid>
      </InfoCard>

      {/* AI Classification */}
      {(data.category || data.classification_confidence != null) && (
        <InfoCard title="AI Classification" icon={<Sparkles size={16} className="text-purple-400" />}>
          <InfoGrid>
            <InfoItem label="Category">
              <span className="px-2.5 py-1 rounded text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                {data.category || '—'}
              </span>
            </InfoItem>
            <InfoItem label="Confidence">
              <span className="px-2.5 py-1 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {data.classification_confidence != null 
                  ? `${(data.classification_confidence * 100).toFixed(0)}%` 
                  : '—'}
              </span>
            </InfoItem>
          </InfoGrid>
          {data.classification_reasoning && (
            <div className="mt-4 pt-4 border-t border-slate-700/50">
              <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-2">Reasoning</p>
              <p className="text-sm text-slate-300 leading-relaxed italic bg-slate-800/40 rounded-lg px-4 py-3 border-l-2 border-indigo-500/40">
                {data.classification_reasoning}
              </p>
            </div>
          )}
          <MatchedSkillsDisplay matched_skills={data.matched_skills} />
        </InfoCard>
      )}

      {/* Email Body */}
      <InfoCard title="Email Content" icon={<FileText size={16} className="text-emerald-400" />} defaultOpen={true}>
        {data.body_html ? (
          <div className="bg-white rounded-lg overflow-hidden mt-1">
            <iframe
              srcDoc={injectLightMode(data.body_html)}
              className="w-full border-none rounded-lg"
              style={{ height: '400px' }}
              sandbox="allow-same-origin"
              title="Email content"
            />
          </div>
        ) : data.body_text ? (
          <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono bg-slate-800/50 rounded-lg p-4 mt-1 max-h-80 overflow-y-auto leading-relaxed">
            {data.body_text}
          </pre>
        ) : (
          <p className="text-slate-500 italic text-sm">No body content available.</p>
        )}
      </InfoCard>

      {/* Attachment Context */}
      {data.attachment_extracted_text && (
        <InfoCard title="Attachment Context" icon={<Paperclip size={16} className="text-amber-400" />}>
          <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-4 mt-1">
            <p className="text-[10px] text-amber-500/80 uppercase tracking-wider font-bold mb-3 flex items-center gap-2">
              <Sparkles size={12} />
              Extracted via Workflow
            </p>
            <pre className="text-sm text-amber-100/90 whitespace-pre-wrap font-mono max-h-80 overflow-y-auto leading-relaxed custom-scrollbar">
              {data.attachment_extracted_text}
            </pre>
          </div>
        </InfoCard>
      )}
    </div>
  );
}


/* ─── Approval Preview ─────────────────────────────── */

export function MatchedSkillsDisplay({ matched_skills }: { matched_skills: string | string[] | null | undefined }) {
  if (!matched_skills) return null;
  let skills: string[] = [];
  try {
    skills = typeof matched_skills === 'string' ? JSON.parse(matched_skills) : matched_skills;
  } catch (e) {
    return null;
  }
  if (!Array.isArray(skills) || skills.length === 0) return null;
  return (
    <div className="mt-4 pt-4 border-t border-slate-700/50">
      <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-2">Matched Skills</p>
      <div className="flex flex-wrap gap-1.5">
        {skills.map((skill: string, idx: number) => (
          <span key={idx} className="px-2 py-1 rounded-md text-[11px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 whitespace-nowrap">
            {skill}
          </span>
        ))}
      </div>
    </div>
  );
}

function ApprovalPreview({ data }: { data: any }) {
  const hasDraft = data.draft && data.draft.body;

  return (
    <>
      {/* Status Banner */}
      <div className={cn(
        "rounded-xl px-5 py-3 text-sm font-medium flex items-center gap-2",
        data.status === 'APPROVED' 
          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
          : data.status === 'REJECTED'
          ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
          : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
      )}>
        <Clock size={16} />
        <span>Status: <strong>{data.status}</strong></span>
        <span className="ml-auto text-xs font-mono opacity-60">{data.id?.substring(0, 8)}...</span>
      </div>

      {/* Matched Skills */}
      <MatchedSkillsDisplay matched_skills={data.matched_skills} />

      {/* Screenshot Proof */}
      {data.has_screenshot && data.screenshot_url && (
        <InfoCard title="Application Proof — Screenshot" icon={<Camera size={16} className="text-emerald-400" />}>
          <div className="relative rounded-lg overflow-hidden border border-slate-700/50 bg-slate-950">
            <a 
              href={`http://localhost:8000${data.screenshot_url}`}
              target="_blank"
              rel="noopener noreferrer"
              className="block group/img"
            >
              <img
                src={`http://localhost:8000${data.screenshot_url}`}
                alt="Application screenshot proof"
                className="w-full max-h-[500px] object-contain transition-transform duration-300 group-hover/img:scale-[1.02]"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-black/0 group-hover/img:bg-black/20 transition-colors duration-200 flex items-center justify-center">
                <span className="opacity-0 group-hover/img:opacity-100 transition-opacity duration-200 text-white text-sm font-medium bg-black/60 px-4 py-2 rounded-lg backdrop-blur-sm">
                  Click to view full size
                </span>
              </div>
            </a>
          </div>
          <p className="text-xs text-slate-500 mt-3 text-center italic">
            Captured after the agent completed the application process.
          </p>
        </InfoCard>
      )}

      {/* Draft Email Content */}
      {hasDraft && (
        <InfoCard title="Draft Professional Reply" icon={<Mail size={16} className="text-indigo-400" />} defaultOpen={true}>
          <InfoGrid>
            <InfoItem label="To" value={data.draft.to || data.email_sender || '—'} />
            <InfoItem label="Subject" value={data.draft.subject || data.email_subject || '—'} />
          </InfoGrid>
          <div className="mt-4 pt-4 border-t border-slate-700/50">
            <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-2">Email Body</p>
            <pre className="text-sm text-slate-200 whitespace-pre-wrap font-mono bg-slate-900/80 rounded-lg p-4 max-h-64 overflow-y-auto leading-relaxed border border-slate-700/40">
              {data.draft.body}
            </pre>
          </div>
        </InfoCard>
      )}

      {/* Pending notice if no draft */}
      {!hasDraft && (
        <div className="bg-blue-950/40 border-l-4 border-blue-500 rounded-r-lg px-5 py-3 text-blue-300 text-sm">
          <strong>Draft Pending:</strong> This item has been pre-processed. Generate a reply via the chatbot.
        </div>
      )}

      {/* Suggested Attachments */}
      {(data.suggested_resume || data.suggested_cover_letter) && (
        <InfoCard title="Suggested Attachments" icon={<FileText size={16} className="text-sky-400" />}>
          <InfoGrid>
            <InfoItem label="Resume">
              <span className="px-2 py-1 rounded text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
                {data.suggested_resume || 'None'}
              </span>
            </InfoItem>
            <InfoItem label="Cover Letter">
              <span className="px-2 py-1 rounded text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
                {data.suggested_cover_letter || 'None'}
              </span>
            </InfoItem>
          </InfoGrid>
        </InfoCard>
      )}

      {/* Generation Reasoning */}
      {data.generation_reasoning && (
        <InfoCard title="Generation Insights" icon={<Sparkles size={16} className="text-purple-400" />}>
          <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-2">How This Draft Was Generated</p>
          <p className="text-sm text-slate-300 leading-relaxed italic bg-slate-800/40 rounded-lg px-4 py-3 border-l-2 border-purple-500/40">
            {data.generation_reasoning}
          </p>
        </InfoCard>
      )}

      {/* AI Classification (for undrafted items) */}
      {!hasDraft && data.classification && (
        <InfoCard title="AI Classification" icon={<Sparkles size={16} className="text-purple-400" />}>
          <InfoGrid>
            <InfoItem label="Category">
              <span className="px-2.5 py-1 rounded text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                {data.classification?.category || '—'}
              </span>
            </InfoItem>
            <InfoItem label="Confidence">
              <span className="px-2.5 py-1 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {data.classification?.confidence != null 
                  ? `${(data.classification.confidence * 100).toFixed(0)}%`
                  : '—'}
              </span>
            </InfoItem>
          </InfoGrid>
          {data.classification?.reasoning && (
            <div className="mt-4 pt-4 border-t border-slate-700/50">
              <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-2">Reasoning</p>
              <p className="text-sm text-slate-300 leading-relaxed italic bg-slate-800/40 rounded-lg px-4 py-3 border-l-2 border-indigo-500/40">
                {data.classification.reasoning}
              </p>
            </div>
          )}
        </InfoCard>
      )}

      {/* Job Info */}
      {data.job_info && (
        <InfoCard title="Job Context" icon={<Briefcase size={16} className="text-sky-400" />}>
          <InfoGrid>
            <InfoItem label="Role" value={data.job_info.role || '—'} />
            <InfoItem label="Company" value={data.job_info.company || '—'} />
            <InfoItem label="Location" value={data.job_info.location || '—'} />
            <InfoItem label="Salary" value={data.job_info.salary_range || '—'} />
          </InfoGrid>
          {data.job_info.job_description && (
            <div className="mt-4 pt-4 border-t border-slate-700/50">
              <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-2">Description</p>
              <p className="text-sm text-slate-300 leading-relaxed">{data.job_info.job_description}</p>
            </div>
          )}
        </InfoCard>
      )}

      {/* Recruiter Info */}
      {data.recruiter_info && (
        <InfoCard title="Recruiter Contact" icon={<User size={16} className="text-emerald-400" />}>
          <InfoGrid>
            <InfoItem label="Name" value={data.recruiter_info.name || '—'} />
            <InfoItem label="Title" value={[data.recruiter_info.title, data.recruiter_info.company].filter(Boolean).join(', ') || '—'} />
            <InfoItem label="Email" value={data.recruiter_info.email || '—'} />
            <InfoItem label="Phone" value={data.recruiter_info.phone || '—'} />
          </InfoGrid>
        </InfoCard>
      )}

      {/* Apply URL */}
      {data.apply_url && (
        <InfoCard title="Application Link" icon={<ExternalLink size={16} className="text-sky-400" />}>
          <a
            href={data.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sky-400 hover:text-sky-300 text-sm font-medium transition-colors underline underline-offset-2"
          >
            <ExternalLink size={14} />
            {data.apply_url.length > 60 ? data.apply_url.substring(0, 60) + '...' : data.apply_url}
          </a>
        </InfoCard>
      )}

      {/* Original Email */}
      {data.email_body && (
        <InfoCard title="Original Email" icon={<Mail size={16} className="text-slate-400" />}>
          <InfoGrid>
            <InfoItem label="From" value={data.email_body.sender || data.email_sender || '—'} />
            <InfoItem label="Subject" value={data.email_body.subject || data.email_subject || '—'} />
            <InfoItem label="Date" value={formatDate(data.email_body.date)} />
          </InfoGrid>
          {(data.email_body.body_html || data.email_body.body_text) && (
            <div className="mt-4 pt-4 border-t border-slate-700/50">
              <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-2">Content</p>
              {data.email_body.body_html ? (
                <div className="bg-white rounded-lg overflow-hidden">
                  <iframe
                    srcDoc={injectLightMode(data.email_body.body_html)}
                    className="w-full border-none rounded-lg"
                    style={{ height: '300px' }}
                    sandbox="allow-same-origin"
                    title="Original email content"
                  />
                </div>
              ) : (
                <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono bg-slate-800/50 rounded-lg p-4 max-h-60 overflow-y-auto leading-relaxed">
                  {data.email_body.body_text}
                </pre>
              )}
            </div>
          )}
        </InfoCard>
      )}
    </>
  );
}


/* ─── Shared Sub-Components ────────────────────────── */

function InfoCard({ title, icon, children, defaultOpen = false }: { title: string; icon?: React.ReactNode; children: React.ReactNode; defaultOpen?: boolean }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden transition-all duration-200">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors group focus:outline-none"
      >
        <div className="flex items-center gap-2">
          {icon}
          <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">{title}</h4>
        </div>
        <div className="text-slate-500 group-hover:text-slate-300 transition-colors">
          {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>
      {isOpen && (
        <div className="px-5 pb-5 animate-in fade-in slide-in-from-top-1 duration-200">
          {children}
        </div>
      )}
    </div>
  );
}

function InfoGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{children}</div>
  );
}

function InfoItem({ label, value, children }: { label: string; value?: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] text-slate-500 uppercase tracking-wider font-medium">{label}</span>
      {children || <span className="text-sm text-slate-200 font-semibold">{value}</span>}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, string> = {
    APPROVED: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    PROCESSED: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    REJECTED: "bg-rose-500/10 text-rose-400 border-rose-500/20",
    PENDING: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  };
  const style = config[status] || config['PENDING'];
  return (
    <span className={cn("px-2.5 py-1 rounded text-xs font-semibold border", style)}>
      {status || 'UNKNOWN'}
    </span>
  );
}


/* ─── Helpers ──────────────────────────────────────── */

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch {
    return dateStr;
  }
}

function injectLightMode(html: string): string {
  const injection = "<meta name='color-scheme' content='light'><style>body, html { color: #000; background: #fff; }</style>";
  if (html.toLowerCase().includes('<head>')) {
    return html.replace(/<head>/i, `<head>${injection}`);
  }
  return `<head>${injection}</head>${html}`;
}
