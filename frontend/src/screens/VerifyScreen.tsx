import React, { useEffect, useMemo, useState } from 'react';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { Check, X, AlertCircle, HelpCircle, Loader2, Download, Copy, ArrowRight } from 'lucide-react';
import { AuthUser, JobDetail, ScreenType } from '../types';
import { getJob, jobFileUrl, rejectJob, verifyJob } from '../services/api';
import { DynamicDataView } from '../components/DynamicDataView';

interface VerifyProps {
  jobId: string | null;
  user: AuthUser | null;
  onNavigate: (screen: ScreenType) => void;
}

export const VerifyScreen: React.FC<VerifyProps> = ({ jobId, user, onNavigate }) => {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!jobId) { setLoading(false); setError('No document selected yet.'); return; }
    setLoading(true);
    getJob(jobId)
      .then(setJob)
      .catch((err) => setError(err.message || 'Could not load this document'))
      .finally(() => setLoading(false));
  }, [jobId]);

  const markdownHtml = useMemo(() => {
    if (!job?.markdown) return '';
    return DOMPurify.sanitize(marked.parse(job.markdown, { async: false }) as string);
  }, [job?.markdown]);

  const canReview = user && (user.role === 'admin' || user.role === 'supervisor');

  const doVerify = async () => {
    if (!jobId) return;
    setActing(true);
    try {
      const updated = await verifyJob(jobId);
      setJob((j) => (j ? { ...j, ...updated } as JobDetail : j));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActing(false);
    }
  };

  const doReject = async () => {
    if (!jobId) return;
    setActing(true);
    try {
      const updated = await rejectJob(jobId, rejectReason);
      setJob((j) => (j ? { ...j, ...updated } as JobDetail : j));
      setShowReject(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActing(false);
    }
  };

  const copyJson = () => {
    if (!job) return;
    navigator.clipboard.writeText(JSON.stringify(job.land_record, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 text-[#756C65] gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading…
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="max-w-lg mx-auto mt-24 text-center space-y-4">
        <AlertCircle className="w-8 h-8 text-[#E05A47] mx-auto" />
        <p className="text-sm text-[#756C65]">{error}</p>
        <button onClick={() => onNavigate('new')} className="h-10 px-5 rounded-xl bg-[#2B2320] text-[#FBF9F5] text-xs font-semibold inline-flex items-center gap-2">
          Upload a document <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  if (!job) return null;
  const v = job.validation;
  const classification = job.land_record?.classification;

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-14">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E8E2D9] pb-6">
        <div>
          <h1 className="font-serif text-3xl text-[#2B2320] font-normal tracking-tight">{job.source_filename}</h1>
          <p className="text-sm text-[#756C65] mt-1">Digitized document, ready for review.</p>
        </div>
        <div className="flex items-center gap-2">
          <a href={jobFileUrl(job.documents.markdown)} className="h-9 px-3 rounded-lg border border-[#E8E2D9] text-xs font-semibold text-[#2B2320] flex items-center gap-1.5"><Download className="w-3.5 h-3.5" />MD</a>
          <a href={jobFileUrl(job.documents.docx)} className="h-9 px-3 rounded-lg border border-[#E8E2D9] text-xs font-semibold text-[#2B2320] flex items-center gap-1.5"><Download className="w-3.5 h-3.5" />DOCX</a>
          <a href={jobFileUrl(job.documents.text)} className="h-9 px-3 rounded-lg border border-[#E8E2D9] text-xs font-semibold text-[#2B2320] flex items-center gap-1.5"><Download className="w-3.5 h-3.5" />TXT</a>
        </div>
      </div>

      <ClassificationBanner classification={classification} avgConfidence={job.avg_confidence} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Document viewer */}
        <div className="lg:col-span-2 bg-white border border-[#E8E2D9] rounded-2xl overflow-hidden">
          <div className="px-5 py-3 border-b border-[#E8E2D9] bg-[#FBF9F5] text-xs font-semibold text-[#2B2320]">Digitized document</div>
          <div className="p-8 max-h-[720px] overflow-auto bg-white">
            <div
              className="prose prose-sm max-w-none mx-auto [&_table]:text-xs [&_table]:border-collapse [&_td]:border [&_td]:border-[#E8E2D9] [&_td]:p-1.5 [&_th]:border [&_th]:border-[#E8E2D9] [&_th]:p-1.5 [&_th]:bg-[#FBF9F5]"
              style={{ maxWidth: 640 }}
              dangerouslySetInnerHTML={{ __html: markdownHtml }}
            />
          </div>
        </div>

        <div className="space-y-4">
          {/* Extracted data — generative, walks whatever Mercury returned */}
          {classification?.is_land_record !== false && (
            <div className="bg-white border border-[#E8E2D9] rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-[#E8E2D9] bg-[#FBF9F5]">
                <h3 className="text-sm font-semibold text-[#2B2320]">Extracted data</h3>
                <div className="flex items-center gap-1">
                  <button onClick={copyJson} title="Copy JSON" className="p-1.5 rounded-lg text-[#5A524C] hover:bg-[#F0ECE6]">
                    {copied ? <Check className="w-3.5 h-3.5 text-[#2C5E43]" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                  <a href={jobFileUrl(job.documents.land_record)} title="Download JSON" className="p-1.5 rounded-lg text-[#5A524C] hover:bg-[#F0ECE6]">
                    <Download className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
              <div className="p-4 max-h-80 overflow-auto">
                <DynamicDataView data={job.land_record as unknown as Record<string, unknown>} />
              </div>
            </div>
          )}

          <div className="bg-white border border-[#E8E2D9] rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-[#2B2320]">Validation</h3>
              <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${v?.validation_passed ? 'text-[#2C5E43] bg-[#EAF4ED] border-[#D0E6D7]' : 'text-[#C89D55] bg-[#FDF3E7] border-[#F6E1C7]'}`}>
                {v?.rules_passed ?? 0}/{v?.total_rules_checked ?? 0} passed
              </span>
            </div>
            <div className="space-y-2">
              {v?.checks?.map((c, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  {c.status === 'passed' ? <Check className="w-3.5 h-3.5 text-[#2C5E43] mt-0.5 shrink-0" /> : <AlertCircle className="w-3.5 h-3.5 text-[#E05A47] mt-0.5 shrink-0" />}
                  <span className="text-[#5A524C]">{c.message}</span>
                </div>
              ))}
              {!v?.checks?.length && <p className="text-xs text-[#A89F97] italic">No validation checks recorded</p>}
            </div>
          </div>

          <div className="bg-white border border-[#E8E2D9] rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-[#2B2320]">Review decision</h3>
            {job.status === 'verified' && (
              <div className="flex items-center gap-2 text-sm text-[#2C5E43] font-semibold"><Check className="w-4 h-4" /> Verified</div>
            )}
            {job.status === 'rejected' && (
              <div className="flex items-center gap-2 text-sm text-[#E05A47] font-semibold"><X className="w-4 h-4" /> Rejected</div>
            )}
            {job.status !== 'verified' && job.status !== 'rejected' && (
              canReview ? (
                <div className="space-y-2">
                  <button onClick={doVerify} disabled={acting} className="w-full h-10 rounded-xl bg-[#2C5E43] text-white text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60">
                    {acting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Approve
                  </button>
                  {!showReject ? (
                    <button onClick={() => setShowReject(true)} className="w-full h-10 rounded-xl border border-[#E8E2D9] text-sm font-semibold text-[#2B2320]">
                      Reject
                    </button>
                  ) : (
                    <div className="space-y-2 pt-1">
                      <textarea
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="Reason for rejection"
                        className="w-full h-20 p-2 rounded-lg border border-[#E8E2D9] text-xs"
                      />
                      <button onClick={doReject} disabled={acting} className="w-full h-9 rounded-xl bg-[#E05A47] text-white text-xs font-semibold">
                        Confirm rejection
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-xs text-[#A89F97]">Only a supervisor or admin can verify or reject a document.</p>
              )
            )}
            {error && <p className="text-xs text-[#E05A47]">{error}</p>}
          </div>
        </div>
      </div>
    </div>
  );
};

const ClassificationBanner: React.FC<{
  classification?: { is_land_record: boolean | null; confidence: number; reasoning: string };
  avgConfidence: number;
}> = ({ classification, avgConfidence }) => {
  const ocrLine = `OCR completed at ${(avgConfidence * 100).toFixed(1)}% average confidence.`;

  if (!classification || classification.is_land_record === null || classification.is_land_record === undefined) {
    return (
      <div className="flex items-start gap-3 p-4 rounded-xl bg-[#FBF9F5] border border-[#E8E2D9]">
        <HelpCircle className="w-4 h-4 text-[#A89F97] mt-0.5 shrink-0" />
        <div className="text-sm">
          <span className="font-semibold text-[#2B2320]">Not classified.</span>{' '}
          <span className="text-[#756C65]">{ocrLine} Enable LLM refinement on upload to get a land-record verdict.</span>
        </div>
      </div>
    );
  }

  if (classification.is_land_record) {
    return (
      <div className="flex items-start gap-3 p-4 rounded-xl bg-[#EAF4ED] border border-[#D0E6D7]">
        <Check className="w-4 h-4 text-[#2C5E43] mt-0.5 shrink-0" />
        <div className="text-sm">
          <span className="font-semibold text-[#2B2320]">
            Identified as a land record — {(classification.confidence * 100).toFixed(0)}% confidence.
          </span>{' '}
          <span className="text-[#5A524C]">{classification.reasoning}</span>
          <div className="text-xs text-[#756C65] mt-1">{ocrLine}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 p-4 rounded-xl bg-[#FEF1EC] border border-[#FADCD5]">
      <AlertCircle className="w-4 h-4 text-[#E05A47] mt-0.5 shrink-0" />
      <div className="text-sm">
        <span className="font-semibold text-[#2B2320]">
          Not identified as a land record — {(classification.confidence * 100).toFixed(0)}% confidence.
        </span>{' '}
        <span className="text-[#5A524C]">{classification.reasoning}</span>
        <div className="text-xs text-[#756C65] mt-1">
          {ocrLine} The digitized text is still available above and via the downloads below.
        </div>
      </div>
    </div>
  );
};
