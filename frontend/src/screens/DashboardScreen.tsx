import React, { useEffect, useState } from 'react';
import { PlusCircle, ChevronRight, Loader2, AlertCircle } from 'lucide-react';
import { DashboardStats, JobSummary, ScreenType } from '../types';
import { getStats, listJobs } from '../services/api';

interface DashboardScreenProps {
  onOpenJob: (jobId: string) => void;
  onNavigate: (screen: ScreenType) => void;
}

export const DashboardScreen: React.FC<DashboardScreenProps> = ({ onOpenJob, onNavigate }) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([getStats(), listJobs({ limit: 20 })])
      .then(([s, j]) => { setStats(s); setJobs(j.jobs); })
      .catch((err) => setError(err.message || 'Could not load the dashboard'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E8E2D9] pb-6">
        <div>
          <h1 className="font-serif text-3xl sm:text-4xl text-[#2B2320] font-normal tracking-tight">Overview</h1>
          <p className="text-sm text-[#756C65] mt-1">Documents processed, pending review, and validation status.</p>
        </div>
        <button
          onClick={() => onNavigate('new')}
          className="h-10 px-4 rounded-xl bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] text-xs font-semibold flex items-center gap-2"
        >
          <PlusCircle className="w-4 h-4" />
          <span>New document</span>
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2.5 p-4 rounded-xl bg-[#FEF1EC] border border-[#FADCD5] text-sm text-[#8A3A2C]">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40 text-[#756C65] gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="Documents processed" value={String(stats?.total_documents ?? 0)} />
            <MetricCard label="Avg. extraction confidence" value={`${((stats?.avg_extraction_confidence ?? 0) * 100).toFixed(1)}%`} />
            <MetricCard label="Pending verification" value={String(stats?.pending_review ?? 0)} />
            <MetricCard label="Verified" value={String(stats?.verified ?? 0)} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BreakdownCard title="State-wise progress" data={stats?.state_wise || {}} />
            <BreakdownCard title="District-wise progress" data={stats?.district_wise || {}} />
          </div>

          <div className="bg-white border border-[#E8E2D9] rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#E8E2D9] bg-[#FBF9F5] text-sm font-semibold text-[#2B2320]">
              Recent documents
            </div>
            {jobs.length === 0 ? (
              <div className="p-10 text-center text-sm text-[#A89F97]">
                No documents yet.{' '}
                <button onClick={() => onNavigate('new')} className="text-[#2B2320] font-semibold underline underline-offset-2">
                  Upload one
                </button>
              </div>
            ) : (
              <div className="divide-y divide-[#F0ECE6]">
                {jobs.map((job) => (
                  <button
                    key={job.id}
                    onClick={() => onOpenJob(job.id)}
                    className="w-full flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-[#FBF9F5] transition-colors text-left"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-[#2B2320] truncate">{job.source_filename}</div>
                      <div className="text-xs text-[#756C65] mt-0.5">
                        {job.district || job.state || '—'} · {job.lines_found} lines · {new Date(job.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <StatusPill status={job.status} />
                      <ChevronRight className="w-4 h-4 text-[#A89F97]" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

const MetricCard: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="bg-white border border-[#E8E2D9] rounded-2xl p-5">
    <div className="text-xs font-medium text-[#756C65]">{label}</div>
    <div className="font-serif text-3xl font-semibold text-[#2B2320] mt-2">{value}</div>
  </div>
);

const BreakdownCard: React.FC<{ title: string; data: Record<string, number> }> = ({ title, data }) => {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="bg-white border border-[#E8E2D9] rounded-2xl p-5">
      <h3 className="text-sm font-semibold text-[#2B2320] mb-3">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-xs text-[#A89F97] italic">No data yet</p>
      ) : (
        <div className="space-y-2.5">
          {entries.map(([name, count]) => (
            <div key={name} className="flex items-center gap-3">
              <div className="w-28 shrink-0 text-xs text-[#5A524C] truncate">{name}</div>
              <div className="flex-1 h-2 rounded-full bg-[#F0ECE6] overflow-hidden">
                <div className="h-full bg-[#2B2320]" style={{ width: `${(count / max) * 100}%` }} />
              </div>
              <div className="w-6 text-right text-xs font-semibold text-[#2B2320]">{count}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const STATUS_LABELS: Record<string, string> = {
  processing: 'Processing', complete: 'Complete', needs_review: 'Needs review',
  verified: 'Verified', rejected: 'Rejected', failed: 'Failed',
};
const STATUS_STYLES: Record<string, string> = {
  processing: 'text-[#205E8C] bg-[#EBF3FB] border-[#D5E5F6]',
  complete: 'text-[#2C5E43] bg-[#EAF4ED] border-[#D0E6D7]',
  needs_review: 'text-[#C89D55] bg-[#FDF3E7] border-[#F6E1C7]',
  verified: 'text-[#2C5E43] bg-[#EAF4ED] border-[#D0E6D7]',
  rejected: 'text-[#E05A47] bg-[#FEF1EC] border-[#FADCD5]',
  failed: 'text-[#E05A47] bg-[#FEF1EC] border-[#FADCD5]',
};

const StatusPill: React.FC<{ status: string }> = ({ status }) => (
  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${STATUS_STYLES[status] || ''}`}>
    {STATUS_LABELS[status] || status}
  </span>
);
