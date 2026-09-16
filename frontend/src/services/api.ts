import { BackendSegmentResponse, BenchmarkSession } from '../types';

export const API_BASE_URL = window.location.origin;

export async function runSegmentApi(
  file: File,
  ocr: boolean = true,
  extractTables: boolean = true
): Promise<BackendSegmentResponse> {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('ocr', String(ocr));
  formData.append('extract_tables', String(extractTables));
  formData.append('llm_refine', 'false'); // fast response in UI

  const response = await fetch('/segment', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Backend error (${response.status}): ${errorText}`);
  }

  return await response.json();
}

export async function checkBackendHealth(): Promise<{ online: boolean; latency: number }> {
  const start = performance.now();
  try {
    const res = await fetch('/docs', { method: 'HEAD', cache: 'no-cache' });
    const latency = Math.round(performance.now() - start);
    return { online: res.status === 200 || res.status === 304, latency };
  } catch {
    return { online: false, latency: 0 };
  }
}

export const INITIAL_SESSIONS: BenchmarkSession[] = [
  {
    id: 'bhm_sess_07',
    title: 'UP Khata Record · Test 07',
    documentType: 'PDF',
    script: 'Hindi (Devanagari)',
    totalFields: 15,
    accuracy: 96.7,
    status: 'complete',
    processingTime: '7.8s',
    correctionsCount: 2,
    date: '14 Sep 2026',
    thumbnailUrl: '/samples/sample_test_subject_1.png',
    fields: [
      {
        id: 'f1',
        name: 'Owner name',
        hindiName: 'खातेदार का नाम',
        expectedValue: 'Ashish Kumar Sharma',
        extractedValue: 'Ashish Kumar Sharma',
        confidence: 0.96,
        status: 'correct',
        sourceLine: 'Source line 02',
        bbox: { x: 22, y: 38, w: 45, h: 4 }
      },
      {
        id: 'f2',
        name: 'Khata number',
        hindiName: 'खाता संख्या',
        expectedValue: '112',
        extractedValue: '112',
        confidence: 0.94,
        status: 'correct',
        sourceLine: 'Source line 01',
        bbox: { x: 22, y: 32, w: 25, h: 4 }
      },
      {
        id: 'f3',
        name: 'Khasra number',
        hindiName: 'खसरा संख्या',
        expectedValue: '128/4',
        extractedValue: '128/4',
        confidence: 0.61,
        status: 'conflict',
        paddleValue: '128/4',
        trocrValue: '123/4',
        sourceLine: 'Source line 04 · Column 3',
        bbox: { x: 22, y: 44, w: 35, h: 4 }
      },
      {
        id: 'f4',
        name: 'Area',
        hindiName: 'क्षेत्रफल',
        expectedValue: '0.82 hectare',
        extractedValue: '0.82 hectare',
        confidence: 0.89,
        status: 'correct',
        sourceLine: 'Source line 05',
        bbox: { x: 22, y: 50, w: 30, h: 4 }
      },
      {
        id: 'f5',
        name: 'Village',
        hindiName: 'ग्राम',
        expectedValue: 'Rampur',
        extractedValue: 'Rampur',
        confidence: 0.92,
        status: 'correct',
        sourceLine: 'Header line 02',
        bbox: { x: 55, y: 24, w: 20, h: 4 }
      },
      {
        id: 'f6',
        name: 'Tehsil',
        hindiName: 'तहसील',
        expectedValue: 'Dadri',
        extractedValue: 'Dadri',
        confidence: 0.95,
        status: 'correct',
        sourceLine: 'Header line 02',
        bbox: { x: 35, y: 24, w: 18, h: 4 }
      },
      {
        id: 'f7',
        name: 'District',
        hindiName: 'जनपद',
        expectedValue: 'Gautam Buddha Nagar',
        extractedValue: 'Gautam Buddha Nagar',
        confidence: 0.98,
        status: 'correct',
        sourceLine: 'Header line 02',
        bbox: { x: 10, y: 24, w: 24, h: 4 }
      }
    ]
  },
  {
    id: 'bhm_sess_06',
    title: 'Urdu Stamp Paper Deed · 1892',
    documentType: 'IMG',
    script: 'Urdu (Nastaliq)',
    totalFields: 18,
    accuracy: 92.4,
    status: 'complete',
    processingTime: '8.4s',
    correctionsCount: 1,
    date: '13 Sep 2026',
    thumbnailUrl: '/samples/stamp_paper_urdu.png',
    fields: [
      {
        id: 'u1',
        name: 'Stamp Value',
        hindiName: 'मूल्य / Stamp Duty',
        expectedValue: 'Two Annas / Two Rupees Eight Annas',
        extractedValue: 'Two Annas / Two Rupees Eight Annas',
        confidence: 0.97,
        status: 'correct',
        sourceLine: 'Tier-0 Medallion OCR',
        bbox: { x: 30, y: 5, w: 40, h: 18 }
      },
      {
        id: 'u2',
        name: 'Registration Office',
        hindiName: 'دفتر رجسٹری',
        expectedValue: 'Court of Sub-Registrar Lahore',
        extractedValue: 'Court of Sub-Registrar Lahore',
        confidence: 0.88,
        status: 'correct',
        sourceLine: 'Header Line 1',
        bbox: { x: 20, y: 25, w: 60, h: 5 }
      },
      {
        id: 'u3',
        name: 'First Party (Vendor)',
        hindiName: 'طرف اول',
        expectedValue: 'Sheikh Muhammad Din',
        extractedValue: 'Sheikh Muhammad Din',
        confidence: 0.91,
        status: 'correct',
        sourceLine: 'Margin Annotation Line 3',
        bbox: { x: 15, y: 35, w: 45, h: 6 }
      },
      {
        id: 'u4',
        name: 'Second Party (Vendee)',
        hindiName: 'طرف دوم',
        expectedValue: 'Munshi Ram Lal',
        extractedValue: 'Munshi Ram Lal',
        confidence: 0.93,
        status: 'correct',
        sourceLine: 'Body Line 6',
        bbox: { x: 15, y: 44, w: 40, h: 6 }
      }
    ]
  },
  {
    id: 'bhm_sess_05',
    title: 'Village Jamabandi Register · 1965',
    documentType: 'PDF',
    script: 'Devanagari',
    totalFields: 22,
    accuracy: 88.5,
    status: 'review',
    processingTime: '9.2s',
    correctionsCount: 3,
    date: '12 Sep 2026',
    thumbnailUrl: '/samples/sample_test_subject_1.png',
    fields: []
  },
  {
    id: 'bhm_sess_04',
    title: 'Bhoomi Form 16 · Test 04',
    documentType: 'IMG',
    script: 'English / Kannada',
    totalFields: 12,
    accuracy: 100.0,
    status: 'complete',
    processingTime: '5.1s',
    correctionsCount: 0,
    date: '11 Sep 2026',
    thumbnailUrl: '/samples/sample_test_subject_1.png',
    fields: []
  }
];

export function downloadFile(filename: string, content: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
