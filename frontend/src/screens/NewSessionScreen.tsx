import React, { useEffect, useRef, useState } from 'react';
import { Upload, Check, ArrowRight, Loader2, AlertCircle, ClipboardPaste } from 'lucide-react';
import { ScreenType } from '../types';
import { runSegmentApi } from '../services/api';

interface NewSessionProps {
  onDocumentReady: (jobId: string) => void;
  onNavigate: (screen: ScreenType) => void;
}

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi' },
  { value: 'devanagari', label: 'Devanagari' },
  { value: 'ur', label: 'Urdu' },
  { value: 'pa', label: 'Punjabi' },
  { value: 'bn', label: 'Bengali' },
  { value: 'mr', label: 'Marathi' },
  { value: 'gu', label: 'Gujarati' },
  { value: 'kn', label: 'Kannada' },
  { value: 'ta', label: 'Tamil' },
  { value: 'te', label: 'Telugu' },
];

const DOC_TYPES = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'jamabandi', label: 'Jamabandi' },
  { value: 'khatauni', label: 'Khatauni' },
  { value: 'khasra', label: 'Khasra' },
  { value: 'mutation', label: 'Mutation record' },
  { value: 'sale_deed', label: 'Sale deed' },
  { value: 'other', label: 'Other' },
];

const SAMPLES = [
  { file: 'sample_test_subject_1.png', title: 'Jamabandi Form 12', subtitle: 'Devanagari · Tabular ledger' },
  { file: 'stamp_paper_urdu.png', title: 'Urdu Stamp Paper Deed', subtitle: '1892 · Medallion + margin' },
];

export const NewSessionScreen: React.FC<NewSessionProps> = ({ onDocumentReady, onNavigate }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedSample, setSelectedSample] = useState<string>(SAMPLES[0].file);
  const [lang, setLang] = useState('en');
  const [docType, setDocType] = useState('auto');
  const [state, setState] = useState('');
  const [district, setDistrict] = useState('');
  const [tehsil, setTehsil] = useState('');
  const [extractTables, setExtractTables] = useState(true);
  const [llmRefine, setLlmRefine] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [justPasted, setJustPasted] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const applyFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError(`"${file.name}" isn't an image — drop or paste a PNG, JPG, or TIFF page.`);
      return;
    }
    setSelectedFile(file);
    setError(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) applyFile(e.target.files[0]);
  };

  const handleSelectSample = (sampleFile: string) => {
    setSelectedSample(sampleFile);
    setSelectedFile(null);
    setError(null);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) applyFile(file);
  };

  // Paste an image from the clipboard anywhere on this screen — a screenshot, or a
  // copied file from Finder/Explorer — without needing to save it to disk first.
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          const file = item.getAsFile();
          if (file) {
            applyFile(file);
            setJustPasted(true);
            setTimeout(() => setJustPasted(false), 2000);
          }
          e.preventDefault();
          return;
        }
      }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, []);

  const handleProcess = async () => {
    setIsProcessing(true);
    setError(null);
    try {
      let fileToUpload: File | null = selectedFile;
      if (!fileToUpload) {
        const resp = await fetch(`/samples/${selectedSample}`);
        if (!resp.ok) throw new Error('could not load the sample file');
        const blob = await resp.blob();
        fileToUpload = new File([blob], selectedSample, { type: blob.type || 'image/png' });
      }

      const result = await runSegmentApi(fileToUpload, {
        lang, docType, state, district, tehsil, extractTables, llmRefine,
      });

      if (!result.job_id) throw new Error('the backend did not return a job id');
      onDocumentReady(result.job_id);
      onNavigate('workspace');
    } catch (err: any) {
      setError(err.message || 'Processing failed');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto pb-28">
      <div className="border-b border-[#E8E2D9] pb-6 mb-6">
        <h1 className="font-serif text-3xl sm:text-4xl text-[#2B2320] font-normal tracking-tight">
          New document
        </h1>
        <p className="text-sm text-[#756C65] mt-1">Upload a scanned record to digitize and validate.</p>
      </div>

      {error && (
        <div className="flex items-start gap-2.5 p-4 rounded-xl bg-[#FEF1EC] border border-[#FADCD5] text-sm text-[#8A3A2C] mb-6">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-6 shadow-2xs space-y-4">
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all group ${
                isDragging ? 'border-[#2B2320] bg-[#F0ECE6]' : 'border-[#D5CDC2] hover:border-[#2B2320] bg-[#FDFCF9]'
              }`}
            >
              <input type="file" ref={fileInputRef} onChange={handleFileChange} accept="image/*" className="hidden" />
              <div className="w-12 h-12 rounded-xl bg-[#EBF3FB] text-[#205E8C] flex items-center justify-center mx-auto mb-3">
                <Upload className="w-6 h-6" />
              </div>
              <div className="font-semibold text-sm text-[#2B2320]">
                {selectedFile ? selectedFile.name : isDragging ? 'Drop it here' : 'Drag a scanned page here, paste, or browse'}
              </div>
              <p className="text-xs text-[#756C65] mt-1 mb-3">PNG, JPG or TIFF · up to 40 MB</p>
              <button type="button" className="px-4 py-1.5 rounded-lg border border-[#E8E2D9] bg-white text-xs font-semibold text-[#2B2320] hover:bg-[#F5F1E9] transition-colors">
                Choose file
              </button>
              {justPasted && (
                <div className="flex items-center justify-center gap-1.5 text-[11px] font-semibold text-[#2C5E43] mt-3">
                  <ClipboardPaste className="w-3.5 h-3.5" /> Pasted from clipboard
                </div>
              )}
            </div>

            <div>
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#A89F97] mb-2">
                Or use a sample
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {SAMPLES.map((s) => (
                  <button
                    key={s.file}
                    type="button"
                    onClick={() => handleSelectSample(s.file)}
                    className={`p-2.5 rounded-xl border text-left text-xs transition-all flex items-center justify-between ${
                      !selectedFile && selectedSample === s.file
                        ? 'border-[#2B2320] bg-[#F5F1E9] font-bold'
                        : 'border-[#E8E2D9] bg-white hover:bg-[#FBF9F5]'
                    }`}
                  >
                    <div>
                      <div className="font-semibold text-[#2B2320]">{s.title}</div>
                      <div className="text-[10px] text-[#756C65]">{s.subtitle}</div>
                    </div>
                    {!selectedFile && selectedSample === s.file && <Check className="w-4 h-4 text-[#2B2320]" />}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-[#FBF9F5] border border-[#E8E2D9] flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#EBF3FB] text-[#205E8C] flex items-center justify-center font-bold text-xs shrink-0">
                IMG
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-[#2B2320] truncate">
                  {selectedFile ? selectedFile.name : selectedSample}
                </div>
                <div className="text-[10px] text-[#756C65]">
                  {selectedFile ? `${(selectedFile.size / 1024).toFixed(0)} KB` : 'Sample document'}
                </div>
              </div>
            </div>
          </div>

          <div className="bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-6 shadow-2xs space-y-3">
            <h3 className="font-serif text-lg font-medium text-[#2B2320]">Processing</h3>
            <label className="flex items-center gap-2.5 cursor-pointer text-xs font-semibold text-[#2B2320]">
              <input type="checkbox" checked={extractTables} onChange={(e) => setExtractTables(e.target.checked)} className="rounded w-4 h-4" />
              <span>Detect tables and stamps, compile the DoLR/DILRMP schema</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer text-xs font-semibold text-[#2B2320]">
              <input type="checkbox" checked={llmRefine} onChange={(e) => setLlmRefine(e.target.checked)} className="rounded w-4 h-4" />
              <span>LLM refinement (higher accuracy, slower)</span>
            </label>
          </div>
        </div>

        <div className="lg:col-span-5 bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-6 shadow-2xs space-y-4">
          <h3 className="font-serif text-lg font-medium text-[#2B2320]">Document details</h3>

          <Field label="Language">
            <select value={lang} onChange={(e) => setLang(e.target.value)} className={selectClass}>
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </Field>

          <Field label="Document type">
            <select value={docType} onChange={(e) => setDocType(e.target.value)} className={selectClass}>
              {DOC_TYPES.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </Field>

          <Field label="State">
            <input value={state} onChange={(e) => setState(e.target.value)} placeholder="e.g. Himachal Pradesh" className={inputClass} />
          </Field>

          <Field label="District">
            <input value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="e.g. Solan" className={inputClass} />
          </Field>

          <Field label="Tehsil">
            <input value={tehsil} onChange={(e) => setTehsil(e.target.value)} placeholder="e.g. Kandaghat" className={inputClass} />
          </Field>
        </div>
      </div>

      {/* Sticky submit bar — always visible so it's never mistaken for "nothing happens after upload" */}
      <div className="sticky bottom-4 mt-8 p-4 rounded-2xl bg-[#FBF9F5]/95 backdrop-blur border border-[#E8E2D9] shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="text-xs text-[#756C65]">
          {isProcessing ? (
            <span className="flex items-center gap-2 font-semibold text-[#2B2320]">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Uploading and running OCR — this can take 15–60 seconds depending on the page.
            </span>
          ) : (
            <span>
              Ready to process <strong className="text-[#2B2320]">{selectedFile ? selectedFile.name : selectedSample}</strong>.
            </span>
          )}
        </div>
        <button
          onClick={handleProcess}
          disabled={isProcessing}
          className="h-11 px-6 rounded-xl bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] text-sm font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 shrink-0"
        >
          {isProcessing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Processing…</span>
            </>
          ) : (
            <>
              <span>Process document</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
};

const selectClass = 'w-full h-10 px-3 rounded-lg border border-[#E8E2D9] bg-white text-sm text-[#2B2320] focus:outline-none focus:ring-2 focus:ring-[#2B2320]';
const inputClass = 'w-full h-10 px-3 rounded-lg border border-[#E8E2D9] bg-white text-sm text-[#2B2320] focus:outline-none focus:ring-2 focus:ring-[#2B2320]';

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div>
    <label className="block text-xs font-semibold text-[#2B2320] mb-1.5">{label}</label>
    {children}
  </div>
);
