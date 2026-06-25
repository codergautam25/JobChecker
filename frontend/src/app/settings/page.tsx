"use client";

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useState, useEffect, useRef } from 'react';
import { Save, Server, Key, User, Briefcase, Link as LinkIcon, CheckCircle2, AlertCircle, Upload, FileText, Loader2, Settings as SettingsIcon, Mail, Plus } from 'lucide-react';

export default function Settings() {
  const queryClient = useQueryClient();

  const [extractedSkills, setExtractedSkills] = useState<string[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<Record<string, boolean>>({});
  const [isSkillsModalOpen, setIsSkillsModalOpen] = useState(false);

  // Status State
  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ['settings', 'status'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/setup/status');
      return res.data;
    }
  });

  // Gmail Accounts State
  const { data: gmailAccountsData, isLoading: gmailAccountsLoading } = useQuery({
    queryKey: ['settings', 'gmailAccounts'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/settings/gmail/accounts');
      return res.data.accounts || [];
    }
  });

  const addGmailAccountMutation = useMutation({
    mutationFn: async (payload: { email: string }) => {
      const res = await axios.post('http://localhost:8000/api/settings/gmail/auth', payload);
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'gmailAccounts'] });
      setGmailEmail('');
      alert(`Successfully connected ${data.email}`);
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'Failed to authenticate Gmail account');
    }
  });

  // LinkedIn Account State
  const { data: linkedinStatusData, isLoading: linkedinStatusLoading } = useQuery({
    queryKey: ['settings', 'linkedinStatus'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/settings/linkedin/status');
      return res.data;
    }
  });

  const addLinkedinAccountMutation = useMutation({
    mutationFn: async () => {
      const res = await axios.post('http://localhost:8000/api/settings/linkedin/auth');
      return res.data;
    },
    onSuccess: (data) => {
      alert(data.message || 'A standard Chrome window has been opened. Please log in, then close the window to save your session!');
      // The browser window is now open. We could poll or just let the user refresh later.
      // But we can invalidate the query just in case it finishes quickly.
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['settings', 'linkedinStatus'] }), 30000);
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'Failed to start LinkedIn auth');
    }
  });

  const openLinkedinMutation = useMutation({
    mutationFn: async () => {
      const res = await axios.post('http://localhost:8000/api/settings/linkedin/open');
      return res.data;
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'Failed to open LinkedIn');
    }
  });

  // Settings State
  const [settings, setSettings] = useState({ api_key: '', api_base: '', model: '', poll_interval: '', cache_ttl: '' });
  const [gmailEmail, setGmailEmail] = useState('');
  const { data: settingsData, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings', 'config'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/settings');
      return res.data;
    }
  });

  // LLM Status State
  const { data: llmStatusData, isLoading: llmStatusLoading, refetch: refetchLlmStatus } = useQuery({
    queryKey: ['settings', 'llmStatus'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/settings/llm/status');
      return res.data;
    }
  });
  
  useEffect(() => {
    if (settingsData) {
      setSettings({
        api_key: settingsData.api_key || '',
        api_base: settingsData.api_base || 'https://api.openai.com/v1',
        model: settingsData.model || 'gpt-4o-mini',
        poll_interval: settingsData.poll_interval || '300',
        cache_ttl: settingsData.cache_ttl || '60'
      });
    }
  }, [settingsData]);

  const updateSettingsMutation = useMutation({
    mutationFn: async (newSettings: any) => {
      await axios.post('http://localhost:8000/api/settings', newSettings);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'config'] });
      queryClient.invalidateQueries({ queryKey: ['settings', 'status'] });
      refetchLlmStatus();
      alert("Settings saved successfully!");
    }
  });

  // CV Upload State
  const { data: cvStatus, refetch: refetchCv } = useQuery({
    queryKey: ['settings', 'cv'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/cv/status');
      return res.data.status_text;
    }
  });

  const uploadCvMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post('http://localhost:8000/api/upload/cv', formData);
      return res.data;
    },
    onSuccess: (data) => {
      refetchCv();
      queryClient.invalidateQueries({ queryKey: ['settings', 'profile'] });
      if (data.extracted_skills && data.extracted_skills.length > 0) {
        setExtractedSkills(data.extracted_skills);
        const initialSelected: Record<string, boolean> = {};
        data.extracted_skills.forEach((s: string) => {
          initialSelected[s] = true;
        });
        setSelectedSkills(initialSelected);
        setIsSkillsModalOpen(true);
      } else {
        alert(data.message || 'CV Uploaded');
      }
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'Failed to upload CV');
    }
  });

  const uploadProfileMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post('http://localhost:8000/api/upload/profile', formData);
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'profile'] });
      alert(data.message || 'Profile Parsed Successfully!');
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'Failed to upload profile');
    }
  });

  const cvInputRef = useRef<HTMLInputElement>(null);
  const profileInputRef = useRef<HTMLInputElement>(null);

  // Profile State
  const [profile, setProfile] = useState({ name: '', email: '', phone: '', linkedin_url: '', github_url: '', portfolio_url: '', skills: '', target_roles: '' });
  const { data: profileRawData, isLoading: profileLoading } = useQuery({
    queryKey: ['settings', 'profile'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/profile');
      return res.data.profile;
    }
  });

  useEffect(() => {
    if (profileRawData) {
      let parsedSkills = '';
      let parsedRoles = '';

      if (Array.isArray(profileRawData.skills)) {
        parsedSkills = profileRawData.skills.join(', ');
      } else if (typeof profileRawData.skills === 'string') {
        try {
          const parsed = JSON.parse(profileRawData.skills);
          parsedSkills = Array.isArray(parsed) ? parsed.join(', ') : profileRawData.skills;
        } catch {
          parsedSkills = profileRawData.skills;
        }
      }

      if (Array.isArray(profileRawData.target_roles)) {
        parsedRoles = profileRawData.target_roles.join(', ');
      } else if (typeof profileRawData.target_roles === 'string') {
        try {
          const parsed = JSON.parse(profileRawData.target_roles);
          parsedRoles = Array.isArray(parsed) ? parsed.join(', ') : profileRawData.target_roles;
        } catch {
          parsedRoles = profileRawData.target_roles;
        }
      }

      setProfile({
        name: profileRawData.name || '',
        email: profileRawData.email || '',
        phone: profileRawData.phone || '',
        linkedin_url: profileRawData.linkedin_url || '',
        github_url: profileRawData.github_url || '',
        portfolio_url: profileRawData.portfolio_url || '',
        skills: parsedSkills,
        target_roles: parsedRoles,
      });
    }
  }, [profileRawData]);

  const updateProfileMutation = useMutation({
    mutationFn: async (newProfile: any) => {
      await axios.post('http://localhost:8000/api/profile', newProfile);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'profile'] });
      alert("Profile saved successfully!");
    }
  });

  const handleAddSkills = () => {
    const skillsToAdd = Object.keys(selectedSkills).filter(k => selectedSkills[k]);
    if (skillsToAdd.length === 0) {
      setIsSkillsModalOpen(false);
      return;
    }
    
    let existingSkillsList: string[] = [];
    const rawSkills = profile.skills as any;
    if (typeof rawSkills === 'string') {
      existingSkillsList = rawSkills.split(',').map((s: string) => s.trim()).filter(Boolean);
    } else if (Array.isArray(rawSkills)) {
      existingSkillsList = rawSkills.map((s: any) => String(s).trim()).filter(Boolean);
    }
      
    const newSkillsList = [...existingSkillsList];
    skillsToAdd.forEach(s => {
      const normalized = s.trim().toLowerCase();
      const exists = existingSkillsList.some(ex => ex.trim().toLowerCase() === normalized);
      if (!exists) {
        newSkillsList.push(s.trim());
      }
    });
    
    const updatedSkillsStr = newSkillsList.join(', ');
    const updatedProfile = {
      ...profile,
      skills: updatedSkillsStr
    };
    
    setProfile(updatedProfile);
    setIsSkillsModalOpen(false);
    
    updateProfileMutation.mutate(updatedProfile);
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 h-full overflow-y-auto pr-2 pb-10 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
      
      <div className="mb-6">
        <h2 className="text-3xl font-light tracking-wide text-indigo-400 flex items-center gap-3" style={{ fontFamily: 'Georgia, serif' }}>
          <SettingsIcon className="text-indigo-500" />
          Settings
        </h2>
        <p className="text-sm text-slate-400 mt-1">Configure your LLM provider, background polling, UI cache TTL, and personal profile.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column */}
        <div className="lg:col-span-5 space-y-8">

        {/* API Configuration */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden shadow-xl shadow-black/20">
          <div className="px-5 py-4 border-b border-slate-800/80 bg-slate-900/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Server size={18} className="text-sky-400" />
              <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-200">API Configuration</h3>
            </div>
            {!llmStatusLoading && llmStatusData && (
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border flex items-center gap-1.5 ${
                llmStatusData.connected 
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${llmStatusData.connected ? 'bg-emerald-400' : 'bg-rose-400'}`} />
                {llmStatusData.provider}: {llmStatusData.connected ? 'Connected' : 'Disconnected'}
              </span>
            )}
          </div>
          <div className="p-5 space-y-4">
            {!llmStatusLoading && llmStatusData && (
              <div className={`p-3 rounded-lg border text-xs leading-relaxed ${
                llmStatusData.connected 
                  ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-300' 
                  : 'bg-rose-500/5 border-rose-500/20 text-rose-300'
              }`}>
                {llmStatusData.status_message}
              </div>
            )}
            {settingsLoading ? (
              <div className="animate-pulse space-y-4">
                <div className="h-10 bg-slate-800/50 rounded-lg"></div>
                <div className="h-10 bg-slate-800/50 rounded-lg"></div>
              </div>
            ) : (
              <>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">OpenAI API Key</label>
                  <input 
                    type="password" 
                    value={settings.api_key}
                    onChange={e => setSettings({...settings, api_key: e.target.value})}
                    placeholder="sk-..."
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">API Base URL</label>
                    <input 
                      type="text" 
                      value={settings.api_base}
                      onChange={e => setSettings({...settings, api_base: e.target.value})}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">Model</label>
                    <input 
                      type="text" 
                      value={settings.model}
                      onChange={e => setSettings({...settings, model: e.target.value})}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-400 uppercase tracking-wide flex items-center justify-between">
                      Background Poll Interval
                      <span className="text-[10px] lowercase opacity-60">(seconds)</span>
                    </label>
                    <input 
                      type="number" 
                      value={settings.poll_interval}
                      onChange={e => setSettings({...settings, poll_interval: e.target.value})}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-400 uppercase tracking-wide flex items-center justify-between">
                      UI Cache TTL
                      <span className="text-[10px] lowercase opacity-60">(seconds)</span>
                    </label>
                    <input 
                      type="number" 
                      value={settings.cache_ttl}
                      onChange={e => setSettings({...settings, cache_ttl: e.target.value})}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                    />
                  </div>
                </div>
                <button 
                  onClick={() => updateSettingsMutation.mutate(settings)}
                  disabled={updateSettingsMutation.isPending}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors flex items-center justify-center gap-2 mt-2"
                >
                  <Save size={16} />
                  {updateSettingsMutation.isPending ? 'Saving...' : 'Save Configuration'}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Gmail Accounts */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden shadow-lg shadow-black/20">
          <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/50 flex items-center gap-2">
            <Mail size={18} className="text-red-400" />
            <h3 className="font-semibold text-slate-200">Connected Gmail Accounts</h3>
          </div>
          <div className="p-6 space-y-4">
            <p className="text-xs text-slate-400">
              Connect your Gmail account via Google OAuth2. Enter your email address and click Connect. A local browser tab will open to authenticate the session securely.
            </p>
            <div className="text-xs text-amber-400/90 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 space-y-1">
              <strong>OAuth Client Type Troubleshooting:</strong>
              <div>• If using a <strong>Desktop App</strong> client (recommended), any port works automatically.</div>
              <div>• If using a <strong>Web App</strong> client (like yours), you must add <code>http://localhost:8080/</code> to the <strong>Authorized redirect URIs</strong> in your Google Cloud Console.</div>
            </div>
            {gmailAccountsLoading ? (
              <div className="animate-pulse space-y-2">
                <div className="h-10 bg-slate-800/50 rounded-lg"></div>
              </div>
            ) : (
              <div className="space-y-3">
                {gmailAccountsData && gmailAccountsData.length > 0 ? (
                  gmailAccountsData.map((account: string, idx: number) => (
                    <div key={idx} className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-lg px-4 py-3">
                      <CheckCircle2 size={16} className="text-emerald-500" />
                      <span className="text-sm text-slate-200 font-medium">{account === "legacy" ? "Legacy Default Account" : account}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No accounts connected yet.</p>
                )}
                
                <div className="space-y-3 pt-2 border-t border-slate-800">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">Gmail Address</label>
                    <input 
                      type="email" 
                      value={gmailEmail}
                      onChange={e => setGmailEmail(e.target.value)}
                      placeholder="you@gmail.com"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                    />
                  </div>
                  <button 
                    onClick={() => addGmailAccountMutation.mutate({ email: gmailEmail })}
                    disabled={addGmailAccountMutation.isPending || !gmailEmail}
                    className="w-full bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {addGmailAccountMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                    {addGmailAccountMutation.isPending ? 'Connecting (check browser)...' : 'Connect via Google OAuth2'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* LinkedIn Account */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden shadow-lg shadow-black/20">
          <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/50 flex items-center gap-2">
            <LinkIcon size={18} className="text-blue-500" />
            <h3 className="font-semibold text-slate-200">LinkedIn Account</h3>
          </div>
          <div className="p-6 space-y-4">
            <p className="text-xs text-slate-400">Connect your LinkedIn account so the AI agent can apply to jobs automatically without hitting a login wall.</p>
            {linkedinStatusLoading ? (
              <div className="animate-pulse space-y-2">
                <div className="h-10 bg-slate-800/50 rounded-lg"></div>
              </div>
            ) : (
              <div className="space-y-3">
                {linkedinStatusData?.status === "connected" ? (
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-lg px-4 py-3">
                      <CheckCircle2 size={16} className="text-emerald-500" />
                      <span className="text-sm text-slate-200 font-medium">
                        Connected <span className="text-slate-500 text-xs ml-2">(Last verified: {new Date(linkedinStatusData.last_connected).toLocaleDateString()})</span>
                      </span>
                    </div>
                    <button 
                      onClick={() => openLinkedinMutation.mutate()}
                      disabled={openLinkedinMutation.isPending}
                      className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {openLinkedinMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <LinkIcon size={16} />}
                      Open LinkedIn
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-lg px-4 py-3">
                    <AlertCircle size={16} className="text-amber-500" />
                    <span className="text-sm text-slate-400">Not connected</span>
                  </div>
                )}
                
                <button 
                  onClick={() => addLinkedinAccountMutation.mutate()}
                  disabled={addLinkedinAccountMutation.isPending}
                  className="w-full mt-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 px-4 py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {addLinkedinAccountMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                  Connect LinkedIn
                </button>
              </div>
            )}
          </div>
        </div>

          {/* File Uploads */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden shadow-lg shadow-black/20">
            <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/50 flex items-center gap-2">
              <Upload size={18} className="text-emerald-400" />
              <h3 className="font-semibold text-slate-200">File Uploads</h3>
            </div>
            <div className="p-6 space-y-6">
              
              {/* CV Upload */}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-slate-300">Base Resume (CV)</h4>
                <p className="text-xs text-slate-400 mb-2">Upload the PDF the agent should attach when applying to jobs.</p>
                <div className="flex items-center gap-4">
                  <input 
                    type="file" 
                    accept=".pdf" 
                    className="hidden" 
                    ref={cvInputRef}
                    onChange={(e) => {
                      if (e.target.files?.[0]) uploadCvMutation.mutate(e.target.files[0]);
                    }}
                  />
                  <button 
                    onClick={() => cvInputRef.current?.click()}
                    disabled={uploadCvMutation.isPending}
                    className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                  >
                    {uploadCvMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
                    Upload Resume
                  </button>
                  <span className="text-xs text-slate-400 truncate max-w-[200px]">{cvStatus || 'Checking...'}</span>
                </div>
              </div>

              <hr className="border-slate-800" />

              {/* Profile Dump Upload */}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-slate-300">Profile Document</h4>
                <p className="text-xs text-slate-400 mb-2">Upload a LinkedIn PDF export or raw text dump. The AI will parse this to populate your advanced profile below.</p>
                <div className="flex items-center gap-4">
                  <input 
                    type="file" 
                    accept=".pdf,.txt" 
                    className="hidden" 
                    ref={profileInputRef}
                    onChange={(e) => {
                      if (e.target.files?.[0]) uploadProfileMutation.mutate(e.target.files[0]);
                    }}
                  />
                  <button 
                    onClick={() => profileInputRef.current?.click()}
                    disabled={uploadProfileMutation.isPending}
                    className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                  >
                    {uploadProfileMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
                    Parse Profile Doc
                  </button>
                  {uploadProfileMutation.isPending && <span className="text-xs text-sky-400">Parsing via AI Workflow...</span>}
                </div>
              </div>

            </div>
          </div>

        </div>

        {/* Right Column: User Profile */}
        <div className="lg:col-span-7">
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden shadow-lg shadow-black/20 h-full flex flex-col">
            <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <User size={18} className="text-amber-400" />
                <h3 className="font-semibold text-slate-200">My Profile</h3>
              </div>
              <button 
                onClick={() => updateProfileMutation.mutate(profile)}
                disabled={updateProfileMutation.isPending}
                className="flex items-center gap-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold px-4 py-1.5 rounded-lg text-sm transition-colors disabled:opacity-50"
              >
                <Save size={16} />
                {updateProfileMutation.isPending ? 'Saving...' : 'Save Profile'}
              </button>
            </div>
            
            <div className="p-6 flex-1 space-y-6">
              <p className="text-sm text-slate-400">
                This information is injected as context for the AI Agent when drafting replies or automating applications.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Full Name</label>
                  <div className="relative">
                    <User size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input 
                      type="text" 
                      value={profile.name}
                      onChange={(e) => setProfile({...profile, name: e.target.value})}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                      placeholder="Jane Doe"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Email Address</label>
                  <input 
                    type="email" 
                    value={profile.email}
                    onChange={(e) => setProfile({...profile, email: e.target.value})}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                    placeholder="jane@example.com"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Phone Number</label>
                  <input 
                    type="text" 
                    value={profile.phone}
                    onChange={(e) => setProfile({...profile, phone: e.target.value})}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                    placeholder="+1 234 567 8900"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">LinkedIn URL</label>
                  <div className="relative">
                    <LinkIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input 
                      type="text" 
                      value={profile.linkedin_url}
                      onChange={(e) => setProfile({...profile, linkedin_url: e.target.value})}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                      placeholder="linkedin.com/in/jane"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">GitHub URL</label>
                  <div className="relative">
                    <LinkIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input 
                      type="text" 
                      value={profile.github_url}
                      onChange={(e) => setProfile({...profile, github_url: e.target.value})}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                      placeholder="github.com/jane"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Portfolio URL</label>
                  <div className="relative">
                    <LinkIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input 
                      type="text" 
                      value={profile.portfolio_url}
                      onChange={(e) => setProfile({...profile, portfolio_url: e.target.value})}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
                      placeholder="janedoe.com"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-1.5 pt-2">
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Top Skills (Comma separated)</label>
                <textarea 
                  value={profile.skills}
                  onChange={(e) => setProfile({...profile, skills: e.target.value})}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50 min-h-[60px]"
                  placeholder="Python, React, Machine Learning..."
                />
              </div>

              <div className="space-y-1.5 pt-2">
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Target Roles (Comma separated)</label>
                <div className="relative">
                  <Briefcase size={14} className="absolute left-3 top-4 text-slate-500" />
                  <textarea 
                    value={profile.target_roles}
                    onChange={(e) => setProfile({...profile, target_roles: e.target.value})}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50 min-h-[60px]"
                    placeholder="Senior Backend Engineer, Full Stack Developer..."
                  />
                </div>
              </div>

              {/* Advanced Auto-Extracted Context */}
              <div className="mt-8 pt-6 border-t border-slate-800">
                <h4 className="text-lg font-semibold text-slate-200 mb-1">Advanced AI Context</h4>
                <p className="text-xs text-slate-400 mb-6">
                  The data below was automatically extracted from your Profile Dump. The agent uses this to write highly contextual cover letters and emails.
                </p>

                {profileLoading ? (
                  <div className="animate-pulse space-y-4">
                    <div className="h-20 bg-slate-800 rounded w-full"></div>
                    <div className="h-20 bg-slate-800 rounded w-full"></div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Experience */}
                    {profileRawData?.experience?.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-slate-300 uppercase tracking-wider mb-3">Experience</h5>
                        <div className="space-y-3">
                          {profileRawData.experience.map((exp: any, idx: number) => (
                            <div key={idx} className="bg-slate-900/50 border border-slate-800 rounded-lg p-3">
                              <div className="flex justify-between items-start mb-1">
                                <span className="font-semibold text-slate-200">{exp.role}</span>
                                <span className="text-xs text-slate-500">{exp.start_date} - {exp.end_date || 'Present'}</span>
                              </div>
                              <div className="text-sm text-sky-400 mb-2">{exp.company}</div>
                              {exp.description && <p className="text-xs text-slate-400 line-clamp-2">{exp.description}</p>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Skills */}
                    {profileRawData?.skills && (
                      <div>
                        <h5 className="text-sm font-medium text-slate-300 uppercase tracking-wider mb-3">Skills</h5>
                        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                          <div className="flex flex-wrap gap-2">
                            {(Array.isArray(profileRawData.skills) ? profileRawData.skills : 
                              (typeof profileRawData.skills === 'string' && profileRawData.skills.startsWith('[') ? JSON.parse(profileRawData.skills) : [])
                            ).map((skill: string, idx: number) => (
                              <span key={idx} className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Education */}
                    {profileRawData?.education?.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-slate-300 uppercase tracking-wider mb-3">Education</h5>
                        <div className="space-y-3">
                          {profileRawData.education.map((edu: any, idx: number) => (
                            <div key={idx} className="bg-slate-900/50 border border-slate-800 rounded-lg p-3">
                              <div className="font-semibold text-slate-200">{edu.institution}</div>
                              <div className="text-sm text-slate-400">{edu.degree} {edu.field} <span className="text-slate-500">({edu.graduation_year})</span></div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Projects */}
                    {profileRawData?.projects?.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-slate-300 uppercase tracking-wider mb-3">Projects</h5>
                        <div className="space-y-3">
                          {profileRawData.projects.map((proj: any, idx: number) => (
                            <div key={idx} className="bg-slate-900/50 border border-slate-800 rounded-lg p-3">
                              <div className="font-semibold text-slate-200">{proj.name}</div>
                              {proj.description && <p className="text-xs text-slate-400 mt-1 line-clamp-2">{proj.description}</p>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              
            </div>
          </div>
        </div>

      </div>

      {isSkillsModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-[#0f172a] border border-slate-800 rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl shadow-black/80 animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/50 flex items-center justify-between">
              <h3 className="font-semibold text-slate-200 text-lg">Pick Skills to Add</h3>
              <button 
                onClick={() => setIsSkillsModalOpen(false)}
                className="text-slate-400 hover:text-slate-200 text-lg"
              >
                ✕
              </button>
            </div>
            <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
              <p className="text-xs text-slate-400">
                The following skills were successfully extracted from your uploaded resume. Choose which ones to add to your profile:
              </p>
              <div className="flex justify-between items-center pb-2 border-b border-slate-800/50">
                <button 
                  onClick={() => {
                    const allChecked = Object.values(selectedSkills).every(v => v);
                    const next: Record<string, boolean> = {};
                    extractedSkills.forEach(s => {
                      next[s] = !allChecked;
                    });
                    setSelectedSkills(next);
                  }}
                  className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
                >
                  {Object.values(selectedSkills).every(v => v) ? "Deselect All" : "Select All"}
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3 pt-2">
                {extractedSkills.map((skill, idx) => (
                  <label 
                    key={idx} 
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg border cursor-pointer select-none transition-all ${
                      selectedSkills[skill] 
                        ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-200' 
                        : 'bg-slate-900/50 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <input 
                      type="checkbox" 
                      checked={!!selectedSkills[skill]} 
                      onChange={() => {
                        setSelectedSkills({
                          ...selectedSkills,
                          [skill]: !selectedSkills[skill]
                        });
                      }}
                      className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500/50 bg-slate-900"
                    />
                    <span className="text-sm font-medium truncate" title={skill}>{skill}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="px-6 py-4 bg-slate-900/30 border-t border-slate-800/80 flex items-center justify-end gap-3">
              <button 
                onClick={() => setIsSkillsModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleAddSkills}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-1.5"
              >
                Add Selected Skills
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
