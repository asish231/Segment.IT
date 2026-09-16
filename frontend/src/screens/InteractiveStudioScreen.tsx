import React, { useEffect, useMemo, useRef, useState } from 'react';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import {
  ZoomIn, ZoomOut, Check, Pencil, X, Loader2, AlertCircle,
  FileText, Code, Rows3, ArrowRight, Download,
} from 'lucide-react';
import { JobDetail, LandRecord, LineSegment, ScreenType } from '../types';
import { editLandRecord, editLine, getJob, jobFileUrl } from '../services/api';

interface StudioProps {
  jobId: string | null;
  onNavigate: (screen: ScreenType) => void;
}

type PreviewTab = 'document' | 'markdown' | 'text' | 'segments';

export const InteractiveStudioScreen: React.FC<StudioProps> = ({ jobId, onNavigate }) => {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<PreviewTab>('document');
  const [zoom, setZoom] = useState(1);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const lineRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const load = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const detail = await getJob(id);
      setJob(detail);
    } catch (err: any) {
      setError(err.message || 'Could not load this document');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (jobId) load(jobId);
    else {
      setLoading(false);
      setError('No document selected yet.');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const lines = job?.latent?.lines || [];
  const tables = job?.latent?.tables || [];
  const stamps = job?.latent?.stamps || [];
  const [srcW, srcH] = job?.latent?.source_size || [1000, 1400];

  const markdownHtml = useMemo(() => {
    if (!job?.markdown) return '';
    return DOMPurify.sanitize(marked.parse(job.markdown, { async: false }) as string);
  }, [job?.markdown]);

  const selectLine = (index: number) => {
    setSelectedIndex(index);
    setTab('segments');
    requestAnimationFrame(() => {
      lineRefs.current[index]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  };

  const startEdit = (line: LineSegment) => {
    setEditingIndex(line.index);
    setEditValue(line.text || '');
  };

  const saveEdit = async (index: number) => {
    if (!jobId) return;
    setSaving(true);
    try {
      await editLine(jobId, index, editValue);
      setJob((prev) =>
        prev
          ? {
              ...prev,
              corrections_count: prev.corrections_count + 1,
              latent: prev.latent
                ? {
                    ...prev.latent,
                    lines: prev.latent.lines.map((l) =>
                      l.index === index ? { ...l, text: editValue, human_corrected: true, confidence_ocr: 1 } : l
                    ),
                  }
                : prev.latent,
            }
          : prev
      );
      // The backend regenerated document.md/.txt/.docx — refresh the rendered preview.
      if (jobId) {
        const refreshed = await getJob(jobId);
        setJob(refreshed);
      }
      setEditingIndex(null);
    } catch (err: any) {
      alert(err.message || 'Could not save the edit');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 text-[#756C65] gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading document…
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="max-w-lg mx-auto mt-24 text-center space-y-4">
        <AlertCircle className="w-8 h-8 text-[#E05A47] mx-auto" />
        <p className="text-sm text-[#756C65]">{error || 'No document selected.'}</p>
        <button
          onClick={() => onNavigate('new')}
          className="h-10 px-5 rounded-xl bg-[#2B2320] text-[#FBF9F5] text-xs font-semibold inline-flex items-center gap-2"
        >
          Upload a document <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-[1600px] mx-auto space-y-4 pb-14">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E8E2D9] pb-4">
        <div className="min-w-0">
          <h1 className="font-serif text-2xl text-[#2B2320] font-normal tracking-tight truncate">
            {job.source_filename}
          </h1>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-[#756C65]">
            <span>{job.lines_found} lines</span>
            <span>{job.tables_found} tables</span>
            <span>{job.stamps_found} stamps</span>
            <span>{(job.avg_confidence * 100).toFixed(1)}% avg. confidence</span>
            {job.corrections_count > 0 && <span>{job.corrections_count} corrections</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={job.status} />
          <button
            onClick={() => onNavigate('verify')}
            className="h-9 px-4 rounded-lg bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] text-xs font-semibold flex items-center gap-1.5"
          >
            <span>Verify</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Left: original page with segment overlay */}
        <div className="bg-white border border-[#E8E2D9] rounded-2xl overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#E8E2D9] bg-[#FBF9F5]">
            <span className="text-xs font-semibold text-[#2B2320]">Original page</span>
            <div className="flex items-center gap-1">
              <button onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))} className="p-1.5 rounded hover:bg-[#F0ECE6] text-[#5A524C]">
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs text-[#756C65] w-10 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom((z) => Math.min(3, z + 0.25))} className="p-1.5 rounded hover:bg-[#F0ECE6] text-[#5A524C]">
                <ZoomIn className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="overflow-auto flex-1 bg-[#F0ECE6]" style={{ maxHeight: 640 }}>
            <div
              className="relative mx-auto"
              style={{ width: `${zoom * 100}%`, maxWidth: 'none' }}
            >
              <img
                src={jobFileUrl(job.documents.source_image)}
                alt="Original page"
                className="w-full block select-none"
                draggable={false}
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full">
                {lines.map((line) => {
                  if (!line.polygon_on_source?.length) return null;
                  const points = line.polygon_on_source.map(([x, y]) => `${x},${y}`).join(' ');
                  const isSelected = selectedIndex === line.index;
                  const low = (line.confidence_ocr ?? 1) < 0.75;
                  return (
                    <polygon
                      key={line.index}
                      points={points}
                      onClick={() => selectLine(line.index)}
                      fill={isSelected ? 'rgba(224,90,71,0.28)' : low ? 'rgba(200,157,85,0.16)' : 'rgba(32,94,140,0.08)'}
                      stroke={isSelected ? '#E05A47' : low ? '#C89D55' : '#205E8C'}
                      strokeWidth={isSelected ? 0.4 : 0.2}
                      vectorEffect="non-scaling-stroke"
                      className="cursor-pointer"
                    />
                  );
                })}
                {tables.map((t, i) => {
                  const [tx, ty, tw, th] = t.bbox;
                  return (
                    <rect
                      key={`t${i}`}
                      x={(tx / srcW) * 100} y={(ty / srcH) * 100}
                      width={(tw / srcW) * 100} height={(th / srcH) * 100}
                      fill="rgba(44,94,67,0.06)" stroke="#2C5E43" strokeWidth={0.3}
                      strokeDasharray="1.2,1" vectorEffect="non-scaling-stroke"
                    />
                  );
                })}
                {stamps.map((s, i) => {
                  const [sx, sy, sw, sh] = s.bbox;
                  return (
                    <rect
                      key={`s${i}`}
                      x={(sx / srcW) * 100} y={(sy / srcH) * 100}
                      width={(sw / srcW) * 100} height={(sh / srcH) * 100}
                      fill="rgba(224,90,71,0.05)" stroke="#E05A47" strokeWidth={0.3}
                      strokeDasharray="1.2,1" vectorEffect="non-scaling-stroke"
                    />
                  );
                })}
              </svg>
            </div>
          </div>
        </div>

        {/* Right: preview tabs */}
        <div className="bg-white border border-[#E8E2D9] rounded-2xl overflow-hidden flex flex-col">
          <div className="flex items-center border-b border-[#E8E2D9] bg-[#FBF9F5] px-2">
            <TabButton icon={<FileText className="w-3.5 h-3.5" />} label="Document" active={tab === 'document'} onClick={() => setTab('document')} />
            <TabButton icon={<Code className="w-3.5 h-3.5" />} label="Markdown" active={tab === 'markdown'} onClick={() => setTab('markdown')} />
            <TabButton icon={<FileText className="w-3.5 h-3.5" />} label="Text" active={tab === 'text'} onClick={() => setTab('text')} />
            <TabButton icon={<Rows3 className="w-3.5 h-3.5" />} label={`Segments (${lines.length})`} active={tab === 'segments'} onClick={() => setTab('segments')} />
            <a
              href={jobFileUrl(job.documents.docx)}
              className="ml-auto flex items-center gap-1 text-xs font-semibold text-[#5A524C] hover:text-[#2B2320] px-3 py-2"
            >
              <Download className="w-3.5 h-3.5" /> DOCX
            </a>
          </div>

          <div className="overflow-auto flex-1 p-5" style={{ maxHeight: 640 }}>
            {tab === 'document' && (
              <div
                className="prose prose-sm max-w-none [&_table]:text-xs [&_table]:border-collapse [&_td]:border [&_td]:border-[#E8E2D9] [&_td]:p-1.5 [&_th]:border [&_th]:border-[#E8E2D9] [&_th]:p-1.5 [&_th]:bg-[#FBF9F5]"
                dangerouslySetInnerHTML={{ __html: markdownHtml }}
              />
            )}
            {tab === 'markdown' && (
              <pre className="text-xs font-mono whitespace-pre-wrap text-[#2B2320] leading-relaxed">{job.markdown}</pre>
            )}
            {tab === 'text' && (
              <TextTabContent jobId={job.id} />
            )}
            {tab === 'segments' && (
              <div className="space-y-2">
                {lines.map((line) => (
                  <div
                    key={line.index}
                    ref={(el) => { lineRefs.current[line.index] = el; }}
                    onClick={() => setSelectedIndex(line.index)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      selectedIndex === line.index ? 'border-[#E05A47] bg-[#FEF6F4]' : 'border-[#E8E2D9] hover:border-[#D5CDC2]'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <img
                        src={jobFileUrl(line.url)}
                        alt={`Line ${line.index}`}
                        className="h-9 shrink-0 rounded border border-[#E8E2D9] bg-white"
                        onError={(e) => { (e.target as HTMLImageElement).style.visibility = 'hidden'; }}
                      />
                      <div className="min-w-0 flex-1">
                        {editingIndex === line.index ? (
                          <div className="flex items-center gap-2">
                            <input
                              autoFocus
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              onKeyDown={(e) => e.key === 'Enter' && saveEdit(line.index)}
                              className="flex-1 h-8 px-2 rounded border border-[#2B2320] text-sm"
                            />
                            <button onClick={() => saveEdit(line.index)} disabled={saving} className="p-1.5 rounded bg-[#2C5E43] text-white">
                              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                            </button>
                            <button onClick={() => setEditingIndex(null)} className="p-1.5 rounded border border-[#E8E2D9]">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm text-[#2B2320] break-words">{line.text || <span className="italic text-[#A89F97]">empty</span>}</p>
                            <button onClick={() => startEdit(line)} className="shrink-0 p-1 text-[#A89F97] hover:text-[#2B2320]">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                        <div className="flex items-center gap-3 mt-1 text-[10px] text-[#A89F97]">
                          <span>Line {line.index}</span>
                          <ConfidenceTag value={line.confidence_ocr} corrected={line.human_corrected} />
                          {line.dual_ocr && <span>Paddle/TrOCR {line.dual_ocr.status}</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom: extracted land record + validation */}
      <RecordDrawer job={job} jobId={jobId} onJobUpdated={setJob} />
    </div>
  );
};

const TabButton: React.FC<{ icon: React.ReactNode; label: string; active: boolean; onClick: () => void }> = ({
  icon, label, active, onClick,
}) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
      active ? 'border-[#2B2320] text-[#2B2320]' : 'border-transparent text-[#A89F97] hover:text-[#5A524C]'
    }`}
  >
    {icon}
    <span>{label}</span>
  </button>
);

const ConfidenceTag: React.FC<{ value?: number; corrected?: boolean }> = ({ value, corrected }) => {
  if (corrected) return <span className="text-[#2C5E43] font-semibold">corrected</span>;
  if (value === undefined) return null;
  const pct = Math.round(value * 100);
  const cls = value < 0.75 ? 'text-[#C89D55] font-semibold' : 'text-[#A89F97]';
  return <span className={cls}>{pct}% confidence</span>;
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const labels: Record<string, string> = {
    processing: 'Processing', complete: 'Complete', needs_review: 'Needs review',
    verified: 'Verified', rejected: 'Rejected', failed: 'Failed',
  };
  const styles: Record<string, string> = {
    processing: 'text-[#205E8C] bg-[#EBF3FB] border-[#D5E5F6]',
    complete: 'text-[#2C5E43] bg-[#EAF4ED] border-[#D0E6D7]',
    needs_review: 'text-[#C89D55] bg-[#FDF3E7] border-[#F6E1C7]',
    verified: 'text-[#2C5E43] bg-[#EAF4ED] border-[#D0E6D7]',
    rejected: 'text-[#E05A47] bg-[#FEF1EC] border-[#FADCD5]',
    failed: 'text-[#E05A47] bg-[#FEF1EC] border-[#FADCD5]',
  };
  return (
    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${styles[status] || ''}`}>
      {labels[status] || status}
    </span>
  );
};

const TextTabContent: React.FC<{ jobId: string }> = ({ jobId }) => {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    fetch(jobFileUrl(`/jobs/${jobId}/document.txt`))
      .then((r) => (r.ok ? r.text() : Promise.reject()))
      .then(setText)
      .catch(() => setText('Could not load the text export.'));
  }, [jobId]);
  return <pre className="text-xs font-mono whitespace-pre-wrap text-[#2B2320] leading-relaxed">{text ?? 'Loading…'}</pre>;
};

// --- Bottom drawer: LLM-extracted land record + validation ---------------

const RecordDrawer: React.FC<{ job: JobDetail; jobId: string | null; onJobUpdated: (j: JobDetail) => void }> = ({
  job, jobId, onJobUpdated,
}) => {
  const [drawerTab, setDrawerTab] = useState<'record' | 'validation'>('record');
  const [record, setRecord] = useState<LandRecord>(job.land_record);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { setRecord(job.land_record); setDirty(false); }, [job.land_record]);

  const update = (updater: (r: LandRecord) => LandRecord) => {
    setRecord((r) => updater({ ...r }));
    setDirty(true);
  };

  const save = async () => {
    if (!jobId) return;
    setSaving(true);
    try {
      const res = await editLandRecord(jobId, record);
      onJobUpdated({ ...job, land_record: res.land_record, validation: res.validation as any });
      setDirty(false);
    } catch (err: any) {
      alert(err.message || 'Could not save the record');
    } finally {
      setSaving(false);
    }
  };

  const validation = job.validation;

  return (
    <div className="bg-white border border-[#E8E2D9] rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#E8E2D9] bg-[#FBF9F5] px-2">
        <div className="flex items-center">
          <TabButton icon={<Rows3 className="w-3.5 h-3.5" />} label="Extracted record" active={drawerTab === 'record'} onClick={() => setDrawerTab('record')} />
          <TabButton
            icon={validation?.review_required ? <AlertCircle className="w-3.5 h-3.5 text-[#C89D55]" /> : <Check className="w-3.5 h-3.5 text-[#2C5E43]" />}
            label={`Validation (${validation?.rules_passed ?? 0}/${validation?.total_rules_checked ?? 0})`}
            active={drawerTab === 'validation'}
            onClick={() => setDrawerTab('validation')}
          />
        </div>
        {drawerTab === 'record' && dirty && (
          <button
            onClick={save}
            disabled={saving}
            className="my-1.5 mr-2 h-8 px-3 rounded-lg bg-[#2B2320] text-[#FBF9F5] text-xs font-semibold flex items-center gap-1.5"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            Save changes
          </button>
        )}
      </div>

      <div className="p-5 max-h-[420px] overflow-auto">
        {drawerTab === 'record' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#A89F97]">Metadata</h4>
              <div className="grid grid-cols-2 gap-2">
                {(['state', 'district', 'tehsil', 'village', 'year', 'survey_no'] as const).map((key) => (
                  <div key={key}>
                    <label className="block text-[10px] font-semibold text-[#756C65] mb-1 capitalize">{key.replace('_', ' ')}</label>
                    <input
                      value={record.metadata?.[key] || ''}
                      onChange={(e) => update((r) => ({ ...r, metadata: { ...r.metadata, [key]: e.target.value } }))}
                      className="w-full h-8 px-2 rounded border border-[#E8E2D9] text-xs"
                    />
                  </div>
                ))}
              </div>

              <h4 className="text-xs font-bold uppercase tracking-wider text-[#A89F97] pt-2">Owners</h4>
              <div className="space-y-2">
                {record.owners?.map((o, i) => (
                  <div key={i} className="grid grid-cols-3 gap-2">
                    <input
                      value={o.name || ''}
                      placeholder="Name"
                      onChange={(e) => update((r) => {
                        const owners = [...r.owners]; owners[i] = { ...owners[i], name: e.target.value }; return { ...r, owners };
                      })}
                      className="h-8 px-2 rounded border border-[#E8E2D9] text-xs"
                    />
                    <input
                      value={o.father_or_husband_name || ''}
                      placeholder="Father/husband"
                      onChange={(e) => update((r) => {
                        const owners = [...r.owners]; owners[i] = { ...owners[i], father_or_husband_name: e.target.value }; return { ...r, owners };
                      })}
                      className="h-8 px-2 rounded border border-[#E8E2D9] text-xs"
                    />
                    <input
                      value={o.share || ''}
                      placeholder="Share"
                      onChange={(e) => update((r) => {
                        const owners = [...r.owners]; owners[i] = { ...owners[i], share: e.target.value }; return { ...r, owners };
                      })}
                      className="h-8 px-2 rounded border border-[#E8E2D9] text-xs"
                    />
                  </div>
                ))}
                {!record.owners?.length && <p className="text-xs text-[#A89F97] italic">No owners extracted</p>}
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#A89F97]">Plots</h4>
              <div className="space-y-2">
                {record.plots?.map((p, i) => (
                  <div key={i} className="grid grid-cols-3 gap-2">
                    <input
                      value={p.khasra_no || ''}
                      placeholder="Khasra no."
                      onChange={(e) => update((r) => {
                        const plots = [...r.plots]; plots[i] = { ...plots[i], khasra_no: e.target.value }; return { ...r, plots };
                      })}
                      className="h-8 px-2 rounded border border-[#E8E2D9] text-xs"
                    />
                    <input
                      value={p.area || ''}
                      placeholder="Area"
                      onChange={(e) => update((r) => {
                        const plots = [...r.plots]; plots[i] = { ...plots[i], area: e.target.value }; return { ...r, plots };
                      })}
                      className="h-8 px-2 rounded border border-[#E8E2D9] text-xs"
                    />
                    <input
                      value={p.land_classification || ''}
                      placeholder="Classification"
                      onChange={(e) => update((r) => {
                        const plots = [...r.plots]; plots[i] = { ...plots[i], land_classification: e.target.value }; return { ...r, plots };
                      })}
                      className="h-8 px-2 rounded border border-[#E8E2D9] text-xs"
                    />
                  </div>
                ))}
                {!record.plots?.length && <p className="text-xs text-[#A89F97] italic">No plots extracted</p>}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {validation?.checks?.map((c, i) => (
              <div key={i} className="flex items-start gap-2.5 p-3 rounded-lg border border-[#E8E2D9]">
                {c.status === 'passed' ? (
                  <Check className="w-4 h-4 text-[#2C5E43] mt-0.5 shrink-0" />
                ) : c.status === 'failed' ? (
                  <AlertCircle className="w-4 h-4 text-[#E05A47] mt-0.5 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-[#A89F97] mt-0.5 shrink-0" />
                )}
                <div>
                  <div className="text-xs font-semibold text-[#2B2320]">{c.rule}</div>
                  <div className="text-xs text-[#756C65]">{c.message}</div>
                </div>
              </div>
            ))}
            {!validation?.checks?.length && <p className="text-xs text-[#A89F97] italic">No validation checks recorded</p>}
          </div>
        )}
      </div>
    </div>
  );
};
