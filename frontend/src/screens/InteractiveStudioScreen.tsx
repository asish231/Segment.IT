import React, { useState } from 'react';
import { 
  Sparkles, 
  Send, 
  Plus, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  CheckCircle2, 
  AlertTriangle, 
  Edit3, 
  RefreshCw, 
  Save, 
  ArrowRight,
  Eye,
  Layers,
  FileCode,
  SlidersHorizontal
} from 'lucide-react';
import { BenchmarkSession, ExtractedField, ScreenType } from '../types';

interface InteractiveStudioProps {
  session: BenchmarkSession;
  onNavigate: (screen: ScreenType) => void;
  onUpdateField: (fieldId: string, newValue: string) => void;
}

export const InteractiveStudioScreen: React.FC<InteractiveStudioProps> = ({
  session,
  onNavigate,
  onUpdateField,
}) => {
  const [activeTab, setActiveTab] = useState<'doc' | 'form' | 'compare' | 'json'>('doc');
  const [zoomLevel, setZoomLevel] = useState(100);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [selectedFieldId, setSelectedFieldId] = useState<string>('f3');
  const [editingFieldId, setEditingFieldId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  
  // Interactive assistant chat state
  const [composerText, setComposerText] = useState('');
  const [chatMessages, setChatMessages] = useState<Array<{
    sender: 'user' | 'ai';
    text?: string;
    toolCall?: {
      title: string;
      badge: string;
      events: Array<{ icon: 'check' | 'warn'; text: string }>;
    };
  }>>([
    {
      sender: 'user',
      text: 'Extract this land record using the saved Khata schema.'
    },
    {
      sender: 'ai',
      text: 'I’ll inspect orientation, segment the document and compare both OCR engines before structuring the result.'
    },
    {
      sender: 'ai',
      toolCall: {
        title: '✦ Processing document',
        badge: '7.8s',
        events: [
          { icon: 'check', text: 'Orientation corrected · 0° Deskewed' },
          { icon: 'check', text: '18 regions and 31 lines segmented' },
          { icon: 'check', text: 'PaddleOCR completed' },
          { icon: 'check', text: 'TrOCR completed' },
          { icon: 'warn', text: '2 OCR disagreements detected' },
          { icon: 'check', text: 'JSON schema populated and validated' }
        ]
      }
    },
    {
      sender: 'ai',
      text: 'I extracted 15 fields. 14 match the ground truth. The Khasra number needs review because the OCR engines disagree.'
    },
    {
      sender: 'user',
      text: 'The highlighted value is 128/4. Use that and validate again.'
    },
    {
      sender: 'ai',
      toolCall: {
        title: '↻ Applying correction',
        badge: 'Complete',
        events: [
          { icon: 'check', text: 'khasra_number: 123/4 → 128/4' },
          { icon: 'check', text: 'Validation rerun · no blocking errors' }
        ]
      }
    }
  ]);

  const handleSendMessage = () => {
    if (!composerText.trim()) return;
    const userText = composerText.trim();
    setComposerText('');

    const newMsgs = [...chatMessages, { sender: 'user' as const, text: userText }];
    setChatMessages(newMsgs);

    setTimeout(() => {
      // Simulate intelligent assistant response
      let aiReply = `Acknowledged. I've re-checked "${userText}". All bounding box coordinates remain mathematically linked to the image matrix.`;
      if (userText.toLowerCase().includes('khasra') || userText.includes('128')) {
        aiReply = `Field 'khasra_number' is confirmed as 128/4. Line confidence updated to 98.4%. Pipeline is ready to finalize.`;
      }
      setChatMessages(prev => [
        ...prev,
        {
          sender: 'ai',
          text: aiReply
        }
      ]);
    }, 600);
  };

  const handleStartEdit = (field: ExtractedField) => {
    setEditingFieldId(field.id);
    setEditValue(field.extractedValue);
  };

  const handleSaveEdit = (fieldId: string) => {
    onUpdateField(fieldId, editValue);
    setEditingFieldId(null);
  };

  const fields = session.fields && session.fields.length > 0 ? session.fields : [
    {
      id: 'f1',
      name: 'Owner name',
      expectedValue: 'Ashish Kumar Sharma',
      extractedValue: 'Ashish Kumar Sharma',
      confidence: 0.96,
      status: 'correct' as const,
      sourceLine: 'Source line 02',
    },
    {
      id: 'f2',
      name: 'Khata number',
      expectedValue: '112',
      extractedValue: '112',
      confidence: 0.94,
      status: 'correct' as const,
      sourceLine: 'Source line 01',
    },
    {
      id: 'f3',
      name: 'Khasra number',
      expectedValue: '128/4',
      extractedValue: '128/4',
      confidence: 0.61,
      status: 'conflict' as const,
      paddleValue: '128/4',
      trocrValue: '123/4',
      sourceLine: 'Source line 04 · Column 3',
    },
    {
      id: 'f4',
      name: 'Area',
      expectedValue: '0.82 hectare',
      extractedValue: '0.82 hectare',
      confidence: 0.89,
      status: 'correct' as const,
      sourceLine: 'Source line 05',
    },
    {
      id: 'f5',
      name: 'Village',
      expectedValue: 'Rampur',
      extractedValue: 'Rampur',
      confidence: 0.92,
      status: 'correct' as const,
      sourceLine: 'Header line 02',
    }
  ];

  return (
    <div className="space-y-4 max-w-7xl mx-auto pb-10">
      {/* Studio Header matching workspace.png */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E8E2D9] pb-4">
        <div>
          <div className="text-xs uppercase tracking-widest font-bold text-[#E05A47]">
            Interactive studio
          </div>
          <h1 className="font-serif text-2xl sm:text-3xl text-[#2B2320] font-normal tracking-tight mt-0.5">
            {session.title || 'Legacy Khasra Form · Test 06'}
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full bg-[#FEF1EC] text-[#E05A47] border border-[#FADCD5]">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>1 field needs review</span>
          </span>
          <button
            onClick={() => onNavigate('results')}
            className="h-9 px-4 rounded-xl bg-[#205E8C] hover:bg-[#18486B] text-white text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <span>Finalize result</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Workspace 3-Column Shell matching workspace.png */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 h-[calc(100vh-210px)] min-h-[640px]">
        {/* Left Column (4 cols): BhoomiAI Assistant Chat */}
        <div className="lg:col-span-4 bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl flex flex-col justify-between overflow-hidden shadow-2xs">
          {/* Assistant Header */}
          <div className="p-4 border-b border-[#E8E2D9] bg-[#FAFAF8] flex items-center justify-between">
            <div>
              <div className="text-xs font-bold text-[#2B2320] flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#E05A47]" />
                <span>BhoomiAI Assistant</span>
              </div>
              <div className="text-[10px] text-[#756C65]">
                Transparent processing session
              </div>
            </div>
            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#2C5E43] bg-[#EAF4ED] px-2 py-0.5 rounded-full border border-[#D0E6D7]">
              ● Live
            </span>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3.5 text-xs">
            {chatMessages.map((msg, idx) => (
              <div key={idx} className="space-y-2">
                {msg.sender === 'user' && (
                  <div className="flex justify-end">
                    <div className="bg-[#2B2320] text-[#FBF9F5] p-3 rounded-2xl rounded-tr-xs max-w-[85%] leading-relaxed">
                      {msg.text}
                    </div>
                  </div>
                )}

                {msg.sender === 'ai' && msg.text && (
                  <div className="flex justify-start">
                    <div className="bg-[#F8F5EE] border border-[#E8E2D9] text-[#2B2320] p-3 rounded-2xl rounded-tl-xs max-w-[90%] leading-relaxed">
                      {msg.text}
                    </div>
                  </div>
                )}

                {msg.toolCall && (
                  <div className="bg-[#F0F6F8] border border-[#CFE2EA] rounded-xl p-3 space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-bold text-[#1F364D]">
                      <span>{msg.toolCall.title}</span>
                      <span className="text-[10px] bg-white px-2 py-0.5 rounded-full border border-[#CFE2EA]">
                        {msg.toolCall.badge}
                      </span>
                    </div>
                    <div className="space-y-1 pt-1 border-t border-[#DFEBF0]">
                      {msg.toolCall.events.map((ev, eIdx) => (
                        <div key={eIdx} className="flex items-center gap-2 text-[11px] text-[#526B7E]">
                          <span className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[9px] ${
                            ev.icon === 'check' 
                              ? 'bg-[#EAF4ED] text-[#2C5E43]' 
                              : 'bg-[#FEF1EC] text-[#E05A47]'
                          }`}>
                            {ev.icon === 'check' ? '✓' : '!'}
                          </span>
                          <span>{ev.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Composer */}
          <div className="p-3 border-t border-[#E8E2D9] bg-[#FFFFFF]">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={composerText}
                onChange={(e) => setComposerText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Ask BhoomiAI to inspect, correct or explain a field..."
                className="flex-1 h-10 px-3.5 rounded-xl border border-[#E8E2D9] bg-[#FDFCF9] text-xs text-[#2B2320] focus:outline-none focus:ring-1 focus:ring-[#2B2320]"
              />
              <button
                onClick={handleSendMessage}
                className="h-10 w-10 rounded-xl bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] flex items-center justify-center transition-all cursor-pointer shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Right Stage (8 cols): Split into Document Viewer & Extracted Form */}
        <div className="lg:col-span-8 bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl flex flex-col justify-between overflow-hidden shadow-2xs">
          {/* Worktop Bar matching workspace.png */}
          <div className="p-3 border-b border-[#E8E2D9] bg-[#FAFAF8] flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setActiveTab('doc')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'doc'
                    ? 'bg-[#2B2320] text-[#FBF9F5]'
                    : 'text-[#756C65] hover:bg-[#F5F1E9]'
                }`}
              >
                Document & Fields
              </button>
              <button
                onClick={() => setActiveTab('compare')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'compare'
                    ? 'bg-[#2B2320] text-[#FBF9F5]'
                    : 'text-[#756C65] hover:bg-[#F5F1E9]'
                }`}
              >
                Dual OCR Comparison
              </button>
              <button
                onClick={() => setActiveTab('json')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'json'
                    ? 'bg-[#2B2320] text-[#FBF9F5]'
                    : 'text-[#756C65] hover:bg-[#F5F1E9]'
                }`}
              >
                JSON Schema
              </button>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-[#756C65] bg-[#F5F1E9] px-2.5 py-1 rounded-md border border-[#E8E2D9]">
                Page 1 of 1
              </span>
            </div>
          </div>

          {/* Tab Content */}
          <div className="flex-1 grid grid-cols-1 md:grid-cols-12 overflow-hidden bg-[#F8F5EE]">
            {/* Document Panel (7 cols in doc mode) */}
            <div className={`${activeTab === 'doc' ? 'md:col-span-7' : 'hidden'} border-r border-[#E8E2D9] flex flex-col h-full overflow-hidden bg-[#EAE5DD]/50`}>
              {/* Document Canvas Controls */}
              <div className="h-10 px-4 border-b border-[#E8E2D9] bg-white/80 backdrop-blur-xs flex items-center justify-between text-xs text-[#756C65]">
                <span className="font-semibold text-[#2B2320]">Original record</span>
                <div className="flex items-center gap-2">
                  <button 
                    onClick={() => setZoomLevel(prev => Math.max(60, prev - 10))}
                    className="p-1 hover:text-[#2B2320]"
                    title="Zoom out"
                  >
                    <ZoomOut className="w-3.5 h-3.5" />
                  </button>
                  <span className="font-mono text-[11px]">{zoomLevel}%</span>
                  <button 
                    onClick={() => setZoomLevel(prev => Math.min(180, prev + 10))}
                    className="p-1 hover:text-[#2B2320]"
                    title="Zoom in"
                  >
                    <ZoomIn className="w-3.5 h-3.5" />
                  </button>
                  <button 
                    onClick={() => setShowBoundingBoxes(!showBoundingBoxes)}
                    className={`ml-2 px-2 py-0.5 rounded text-[10px] font-semibold border ${
                      showBoundingBoxes ? 'bg-[#2B2320] text-white border-[#2B2320]' : 'bg-white border-[#E8E2D9]'
                    }`}
                  >
                    ⌗ Bounding Boxes
                  </button>
                </div>
              </div>

              {/* Document Canvas Display */}
              <div className="flex-1 p-6 overflow-auto flex items-center justify-center">
                <div 
                  className="bg-white rounded-lg shadow-md border border-[#D5CDC2] p-6 relative transition-transform duration-200"
                  style={{ 
                    width: `${zoomLevel * 3.8}px`,
                    minHeight: `${zoomLevel * 4.8}px`,
                  }}
                >
                  {/* Parchment simulated header */}
                  <div className="text-center pb-4 border-b border-[#D5CDC2]">
                    <div className="font-serif text-base font-bold text-[#2B2320]">
                      भूमि अभिलेख / LAND RECORD
                    </div>
                    <div className="text-[10px] text-[#756C65] mt-0.5">
                      जनपद: गौतम बुद्ध नगर · तहसील: दादरी · ग्राम: रामपुर
                    </div>
                  </div>

                  {/* Lines of the historical document */}
                  <div className="mt-4 space-y-3 font-serif text-[11px] text-[#3D352F]">
                    <div className="flex justify-between border-b border-[#EFECE6] pb-1">
                      <span>खाता संख्या / Khata No.</span>
                      <span className="font-mono font-bold">112</span>
                    </div>

                    <div className="flex justify-between border-b border-[#EFECE6] pb-1">
                      <span>खातेदार का नाम / Owner</span>
                      <span className="font-bold">Ashish Kumar Sharma</span>
                    </div>

                    <div className="flex justify-between border-b border-[#EFECE6] pb-1">
                      <span>पिता / अभिभावक</span>
                      <span>Rajesh Sharma</span>
                    </div>

                    {/* Highlighted conflict line matching workspace.png */}
                    <div className="relative flex justify-between border-b border-[#EFECE6] pb-1 bg-[#FEF1EC]/60 px-1 rounded">
                      <span>खसरा संख्या / Khasra No.</span>
                      <span className="font-mono font-bold text-[#E05A47]">128/4</span>

                      {showBoundingBoxes && (
                        <>
                          <div className="absolute inset-0 border-2 border-[#E05A47] rounded pointer-events-none animate-pulse" />
                          <div className="absolute -top-3 right-2 bg-[#E05A47] text-white text-[9px] font-bold px-1.5 py-0.5 rounded shadow-xs">
                            OCR disagreement
                          </div>
                        </>
                      )}
                    </div>

                    <div className="flex justify-between border-b border-[#EFECE6] pb-1">
                      <span>क्षेत्रफल / Area</span>
                      <span className="font-mono">0.82 hectare</span>
                    </div>

                    <div className="flex justify-between border-b border-[#EFECE6] pb-1">
                      <span>भूमि प्रकार / Land Class</span>
                      <span>Agricultural / कृषि</span>
                    </div>

                    <div className="flex justify-between border-b border-[#EFECE6] pb-1">
                      <span>वर्ष / Fasli Year</span>
                      <span className="font-mono">1431 (2024)</span>
                    </div>

                    <div className="flex justify-between border-b border-[#EFECE6] pb-1">
                      <span>टिप्पणी / Notes</span>
                      <span>Verified registry copy</span>
                    </div>
                  </div>

                  {/* Stamp Duty / Medallion Simulation */}
                  <div className="mt-6 p-2 rounded border border-dashed border-[#C89D55] text-center bg-[#FDFBF7]">
                    <div className="text-[9px] font-bold uppercase tracking-widest text-[#C89D55]">
                      Tier-0 Stamp Crop · Verified
                    </div>
                    <div className="text-[10px] text-[#756C65]">
                      Imperial Emblem & Fiscal Watermark Neutralized
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Extracted Fields Column (5 cols in doc mode) */}
            <div className={`${activeTab === 'doc' ? 'md:col-span-5' : 'hidden'} bg-[#FFFFFF] flex flex-col h-full overflow-hidden`}>
              <div className="h-10 px-4 border-b border-[#E8E2D9] bg-white flex items-center justify-between text-xs">
                <span className="font-semibold text-[#2B2320]">Extracted fields</span>
                <span className="text-[11px] font-bold text-[#2C5E43] bg-[#EAF4ED] px-2 py-0.5 rounded-full border border-[#D0E6D7]">
                  14 / 15 correct
                </span>
              </div>

              <div className="flex-1 p-4 overflow-y-auto space-y-4">
                {/* Pipeline Accuracy Banner matching workspace.png */}
                <div className="p-3 rounded-xl bg-[#EAF4ED] border border-[#D0E6D7] flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-[#2C5E43]">
                      Pipeline accuracy
                    </div>
                    <div className="text-[10px] text-[#756C65]">
                      After one human verification
                    </div>
                  </div>
                  <div className="font-mono text-xl font-bold text-[#2C5E43]">
                    96.7%
                  </div>
                </div>

                {/* Field Rows */}
                <div className="space-y-3 divide-y divide-[#F0ECE6]">
                  {fields.map((f) => (
                    <div 
                      key={f.id} 
                      onClick={() => setSelectedFieldId(f.id)}
                      className={`pt-3 cursor-pointer rounded-lg p-1.5 transition-colors ${
                        selectedFieldId === f.id ? 'bg-[#FDFBF7] ring-1 ring-[#D5CDC2]' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-bold text-[#2B2320]">
                          {f.name}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          f.status === 'conflict'
                            ? 'bg-[#FEF1EC] text-[#E05A47]'
                            : 'bg-[#EAF4ED] text-[#2C5E43]'
                        }`}>
                          {f.status === 'conflict' ? '! conflict' : `✓ ${(f.confidence * 100).toFixed(0)}%`}
                        </span>
                      </div>

                      {editingFieldId === f.id ? (
                        <div className="flex items-center gap-2 mt-1">
                          <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="flex-1 h-8 px-2.5 rounded-lg border border-[#2B2320] bg-white text-xs font-mono"
                          />
                          <button
                            onClick={() => handleSaveEdit(f.id)}
                            className="px-2.5 h-8 rounded-lg bg-[#2B2320] text-white text-xs font-semibold"
                          >
                            Save
                          </button>
                        </div>
                      ) : (
                        <div className={`p-2 rounded-lg border text-xs font-mono flex items-center justify-between ${
                          f.status === 'conflict'
                            ? 'border-[#FADCD5] bg-[#FEF1EC]/40 text-[#2B2320]'
                            : 'border-[#E8E2D9] bg-[#FDFCF9] text-[#2B2320]'
                        }`}>
                          <span>{f.extractedValue}</span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleStartEdit(f);
                            }}
                            className="text-[#756C65] hover:text-[#2B2320]"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}

                      {f.status === 'conflict' && (
                        <div className="text-[10px] text-[#756C65] mt-1.5 flex items-center gap-1.5">
                          <span>PaddleOCR: 128/4</span>
                          <span>·</span>
                          <span>TrOCR: 123/4</span>
                          <span>·</span>
                          <span>Line 04</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Compare Tab Full Mode */}
            {activeTab === 'compare' && (
              <div className="md:col-span-12 p-6 bg-white overflow-y-auto space-y-6">
                <div>
                  <h3 className="font-serif text-xl font-medium text-[#2B2320]">
                    Dual-Engine Agreement Analysis
                  </h3>
                  <p className="text-xs text-[#756C65]">
                    Character-level comparison between PaddleOCR (East Asian/Indic Layout) and TrOCR (Vision Transformer).
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl border border-[#D5E5F6] bg-[#F4F9FD]">
                    <div className="text-xs font-bold text-[#205E8C] mb-1">PaddleOCR V4</div>
                    <div className="text-sm font-semibold text-[#2B2320]">86.7% Raw Precision</div>
                    <p className="text-xs text-[#526B7E] mt-1">
                      Excels at Devanagari headline (Shirorekha) tracking and tabular cell boundary preservation.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl border border-[#E9DDF8] bg-[#FAF6FD]">
                    <div className="text-xs font-bold text-[#7357B3] mb-1">TrOCR Transformer</div>
                    <div className="text-sm font-semibold text-[#2B2320]">80.0% Raw Precision</div>
                    <p className="text-xs text-[#526B7E] mt-1">
                      Excels at damaged Urdu ligatures and faint handwritten ink strokes.
                    </p>
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-[#D0E6D7] bg-[#EAF4ED]">
                  <div className="text-xs font-bold text-[#2C5E43] mb-1">BhoomiAI Hybrid Adjudicator</div>
                  <div className="text-sm font-semibold text-[#2B2320]">94.2% Defensible Precision</div>
                  <p className="text-xs text-[#3D5647] mt-1">
                    Combines normalized bounding box overlap with schema-constrained dictionary resolution.
                  </p>
                </div>
              </div>
            )}

            {/* JSON Schema Tab Full Mode */}
            {activeTab === 'json' && (
              <div className="md:col-span-12 p-6 bg-white overflow-y-auto">
                <div className="mb-4">
                  <h3 className="font-serif text-xl font-medium text-[#2B2320]">
                    Structured Output Payload (GeoJSON/Defensible JSON)
                  </h3>
                  <p className="text-xs text-[#756C65]">
                    Normalized coordinates and confidence provenance linked to each field.
                  </p>
                </div>
                <pre className="font-mono text-xs bg-[#1E293B] text-[#93C5FD] p-5 rounded-xl overflow-x-auto leading-relaxed border border-[#334155]">
                  <code>{JSON.stringify(fields, null, 2)}</code>
                </pre>
              </div>
            )}
          </div>

          {/* Action Bar matching workspace.png */}
          <div className="h-14 px-6 border-t border-[#E8E2D9] bg-[#FFFFFF] flex items-center justify-end gap-3">
            <button
              onClick={() => onNavigate('new')}
              className="px-3.5 py-2 rounded-lg border border-[#E8E2D9] bg-white hover:bg-[#F5F1E9] text-xs font-semibold text-[#2B2320] transition-colors"
            >
              Reprocess
            </button>
            <button
              onClick={() => alert('Draft session state saved to local storage.')}
              className="px-3.5 py-2 rounded-lg border border-[#E8E2D9] bg-white hover:bg-[#F5F1E9] text-xs font-semibold text-[#2B2320] transition-colors"
            >
              Save draft
            </button>
            <button
              onClick={() => onNavigate('results')}
              className="px-4 py-2 rounded-lg bg-[#205E8C] hover:bg-[#18486B] text-white text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <span>Finalize result →</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
