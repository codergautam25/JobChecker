"use client";

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useState, useEffect } from 'react';
import { Play, Square, ExternalLink, Briefcase, Eye, Loader2, Database, Radar } from 'lucide-react';
import { MatchedSkillsDisplay } from '@/components/PreviewModal';
import { SkillGapChart } from '@/components/SkillGapChart';

export default function LinkedInIntel() {
  const queryClient = useQueryClient();

  // State for Auto-Scroll
  const { data: scrollStatusData } = useQuery({
    queryKey: ['intel', 'autoscrollStatus'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/intel/autoscroll/status');
      return res.data;
    },
    refetchInterval: 2000 // Poll every 2s to keep UI in sync
  });

  const toggleScrollMutation = useMutation({
    mutationFn: async () => {
      const res = await axios.post('http://localhost:8000/api/intel/autoscroll/toggle');
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['intel', 'autoscrollStatus'] });
    }
  });

  // State for Intel Posts
  const { data: postsData, isLoading: postsLoading } = useQuery({
    queryKey: ['intel', 'posts'],
    queryFn: async () => {
      const res = await axios.get('http://localhost:8000/api/intel/posts?limit=100');
      return (res.data.posts || []) as any[];
    },
    refetchInterval: 3000 // Auto-refresh posts every 3 seconds
  });

  const posts = (postsData as any[]) || [];

  const launchIntelMutation = useMutation({
    mutationFn: async (target: string = 'feed') => {
      const res = await axios.post(`http://localhost:8000/api/intel/start?target=${target}`);
      return res.data;
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'Failed to start Intel browser');
    }
  });

  const purgePostsMutation = useMutation({
    mutationFn: async () => {
      const res = await axios.post('http://localhost:8000/api/intel/posts/purge');
      return res.data;
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ['intel', 'posts'] });
      alert(data.message || 'Purged posts older than 7 days successfully');
    },
    onError: (err: any) => {
      alert(err.response?.data?.error || 'Failed to purge older posts');
    }
  });

  const [selectedPost, setSelectedPost] = useState<any>(null);
  const [filter, setFilter] = useState<'all' | 'hiring' | 'standard'>('all');
  const [activeTab, setActiveTab] = useState<'feed' | 'jobs'>('feed');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 15;

  const isAutoScrolling = scrollStatusData?.status === 'active';

  // Filter the posts based on activeTab and the selected category filter state
  const filteredPosts = posts.filter((post: any) => {
    // 1. Filter by active tab
    const isJobPost = post.id && post.id.startsWith('linkedin_job_');
    if (activeTab === 'feed' && isJobPost) return false;
    if (activeTab === 'jobs' && !isJobPost) return false;

    // 2. Filter by category
    if (filter === 'hiring') return post.is_job_opportunity === 1;
    if (filter === 'standard') return post.is_job_opportunity !== 1;
    return true; // 'all'
  });
  
  const totalPages = Math.ceil(filteredPosts.length / itemsPerPage) || 1;
  const paginatedPosts = filteredPosts.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  const handleFilterChange = (newFilter: 'all' | 'hiring' | 'standard') => {
    setFilter(newFilter);
    setCurrentPage(1); // Reset to first page when changing filters
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 h-full flex flex-col overflow-hidden pr-2 pb-10">
      
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="text-3xl font-light tracking-wide text-indigo-400 flex items-center gap-3" style={{ fontFamily: 'Georgia, serif' }}>
            <Radar className="text-indigo-500" />
            LinkedIn Intel
          </h2>
          <p className="text-sm text-slate-400 mt-1">Passively monitor your LinkedIn feed for job opportunities and connections.</p>
        </div>

        <div className="flex items-center gap-3">
          <button 
            onClick={() => toggleScrollMutation.mutate()}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              isAutoScrolling 
                ? 'bg-rose-500/20 text-rose-400 border border-rose-500/50 hover:bg-rose-500/30' 
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-500/30'
            }`}
          >
            {isAutoScrolling ? <Square size={16} /> : <Play size={16} />}
            {isAutoScrolling ? 'Stop Auto-Scroll' : 'Start Auto-Scroll'}
          </button>
          
          <button 
            onClick={() => purgePostsMutation.mutate()}
            disabled={purgePostsMutation.isPending}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {purgePostsMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
            {activeTab === 'feed' ? 'Purge Older Posts' : 'Purge Older Jobs'}
          </button>

          <button 
            onClick={() => launchIntelMutation.mutate(activeTab)}
            disabled={launchIntelMutation.isPending}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {launchIntelMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ExternalLink size={16} />}
            {activeTab === 'feed' ? 'Launch Feed Scraper' : 'Launch Jobs Scraper'}
          </button>
        </div>
      </div>

      <div className="mb-6">
        <SkillGapChart />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 mb-6">
        <button
          onClick={() => { setActiveTab('feed'); setCurrentPage(1); setSelectedPost(null); }}
          className={`px-6 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'feed'
              ? 'border-indigo-500 text-indigo-400 font-semibold bg-indigo-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/20'
          }`}
        >
          Feed Scraper
        </button>
        <button
          onClick={() => { setActiveTab('jobs'); setCurrentPage(1); setSelectedPost(null); }}
          className={`px-6 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'jobs'
              ? 'border-indigo-500 text-indigo-400 font-semibold bg-indigo-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/20'
          }`}
        >
          Jobs Scraper
        </button>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">
        
        {/* Left/Top Panel: Table */}
        <div className="lg:col-span-8 bg-[#0f172a] border border-slate-800 rounded-xl shadow-xl shadow-black/20 flex flex-col h-full max-h-[calc(100vh-180px)]">
          <div className="px-5 py-4 border-b border-slate-800/80 bg-slate-900/50 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Database size={18} className="text-sky-400" />
                <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-200">
                  {activeTab === 'feed' ? 'Scraped Posts' : 'Scraped Jobs'}
                </h3>
              </div>
              
              <div className="flex bg-slate-800/50 rounded-lg p-1 border border-slate-700/50">
                <button 
                  onClick={() => handleFilterChange('all')}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${filter === 'all' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-300'}`}
                >
                  All
                </button>
                <button 
                  onClick={() => handleFilterChange('hiring')}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${filter === 'hiring' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-slate-300'}`}
                >
                  Hiring
                </button>
                <button 
                  onClick={() => handleFilterChange('standard')}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${filter === 'standard' ? 'bg-slate-600 text-white shadow' : 'text-slate-400 hover:text-slate-300'}`}
                >
                  Standard
                </button>
              </div>
            </div>
            
            <span className="text-xs font-medium bg-slate-800 text-slate-300 px-2 py-1 rounded-full">
              {filteredPosts.length} / {posts.filter((p: any) => activeTab === 'feed' ? !p.id?.startsWith('linkedin_job_') : p.id?.startsWith('linkedin_job_')).length || 0}
            </span>
          </div>
          
          <div className="flex-1 overflow-y-auto p-0 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {postsLoading && !posts.length ? (
              <div className="p-8 flex justify-center text-slate-500">
                <Loader2 size={24} className="animate-spin" />
              </div>
            ) : filteredPosts.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                {activeTab === 'feed' 
                  ? 'No posts scraped yet. Launch the Feed Scraper and start scrolling your LinkedIn feed!' 
                  : 'No jobs scraped yet. Launch the Jobs Scraper and search for jobs on LinkedIn!'}
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead className="bg-slate-900/80 sticky top-0 z-10">
                  <tr>
                    <th className="px-4 py-3 text-xs font-semibold text-slate-400 border-b border-slate-800 w-1/4">
                      {activeTab === 'feed' ? 'Author' : 'Company'}
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold text-slate-400 border-b border-slate-800 w-1/2">
                      {activeTab === 'feed' ? 'Snippet' : 'Title & Description'}
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold text-slate-400 border-b border-slate-800 w-1/4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {paginatedPosts.map((post: any) => (
                    <tr 
                      key={post.id} 
                      onClick={() => setSelectedPost(post)}
                      className={`hover:bg-slate-800/30 cursor-pointer transition-colors ${selectedPost?.id === post.id ? 'bg-indigo-900/20' : ''}`}
                    >
                      <td className="px-4 py-3 text-sm text-slate-300 truncate max-w-[150px]">
                        {post.author}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-400 truncate max-w-[400px]">
                        {post.text_content}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex items-center gap-2">
                          {post.is_job_opportunity ? (
                            <span className="inline-flex items-center gap-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">
                              <Briefcase size={10} /> {activeTab === 'feed' ? 'Hiring' : 'Job Listing'}
                            </span>
                          ) : (
                            <span className="text-slate-600 text-[11px] font-medium uppercase tracking-wider">Standard</span>
                          )}
                          {(() => {
                            let count = 0;
                            if (post.matched_skills) {
                              try { count = typeof post.matched_skills === 'string' ? JSON.parse(post.matched_skills).length : post.matched_skills.length; } catch (e) {}
                            }
                            if (count > 0) {
                              return (
                                <span className="inline-flex items-center gap-1 bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider" title={`${count} skills matched`}>
                                  <Radar size={10} /> {count}
                                </span>
                              );
                            }
                            return null;
                          })()}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          
          {/* Pagination Controls */}
          {filteredPosts.length > 0 && (
            <div className="px-5 py-3 border-t border-slate-800/80 bg-slate-900/50 flex items-center justify-between">
              <span className="text-xs text-slate-400">
                Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredPosts.length)} of {filteredPosts.length} items
              </span>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  className="px-3 py-1 bg-slate-800 text-slate-300 rounded text-xs font-medium disabled:opacity-50 hover:bg-slate-700 transition-colors"
                >
                  Previous
                </button>
                <span className="text-xs text-slate-400 font-medium">Page {currentPage} of {totalPages}</span>
                <button 
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1 bg-slate-800 text-slate-300 rounded text-xs font-medium disabled:opacity-50 hover:bg-slate-700 transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right/Bottom Panel: Preview */}
        <div className="lg:col-span-4 bg-[#0f172a] border border-slate-800 rounded-xl shadow-xl shadow-black/20 flex flex-col h-full max-h-[calc(100vh-180px)]">
          <div className="px-4 py-3 border-b border-slate-800/80 bg-slate-900/50 flex items-center gap-2">
            <Eye size={16} className="text-amber-400" />
            <h3 className="font-semibold text-xs uppercase tracking-wider text-slate-200">
              {activeTab === 'feed' ? 'Post Preview' : 'Job Preview'}
            </h3>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {selectedPost ? (
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-slate-200">{selectedPost.author}</h4>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] text-slate-500">{new Date(selectedPost.created_at).toLocaleString()}</span>
                    <a href={selectedPost.url} target="_blank" rel="noreferrer" className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                      View on LinkedIn <ExternalLink size={10} />
                    </a>
                  </div>
                </div>

                {selectedPost.is_job_opportunity === 1 && (
                  <div className="bg-emerald-500/10 border border-emerald-500/20 rounded p-2 flex items-center gap-2">
                    <Briefcase className="text-emerald-400" size={12} />
                    <h5 className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
                      {activeTab === 'feed' ? 'Potential Job Opportunity' : 'Job Posting'}
                    </h5>
                  </div>
                )}

                <MatchedSkillsDisplay matched_skills={selectedPost.matched_skills} />

                <div className="bg-slate-900/30 border border-slate-800/50 rounded-lg p-3">
                  <p className="text-[13px] text-slate-300 whitespace-pre-wrap leading-relaxed">
                    {selectedPost.text_content}
                  </p>
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-2">
                <Eye size={24} className="opacity-20" />
                <p className="text-xs">
                  Select {activeTab === 'feed' ? 'a post' : 'a job'} to view details
                </p>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
