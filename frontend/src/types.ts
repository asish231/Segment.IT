export type ScreenType = 
  | 'landing' 
  | 'login' 
  | 'dashboard' 
  | 'new' 
  | 'workspace' 
  | 'results' 
  | 'api';

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
  label?: string;
  confidence?: number;
}

export interface ExtractedField {
  id: string;
  name: string;
  hindiName?: string;
  expectedValue: string;
  extractedValue: string;
  confidence: number;
  status: 'correct' | 'conflict' | 'corrected' | 'flagged';
  paddleValue?: string;
  trocrValue?: string;
  sourceLine?: string;
  bbox?: BoundingBox;
}

export interface BenchmarkSession {
  id: string;
  title: string;
  documentType: 'PDF' | 'IMG';
  script: string;
  totalFields: number;
  accuracy: number;
  status: 'complete' | 'review' | 'running';
  processingTime: string;
  correctionsCount: number;
  date: string;
  thumbnailUrl?: string;
  fields: ExtractedField[];
}

export interface BackendSegmentResponse {
  message?: string;
  session_id?: string;
  status?: string;
  cuts_count?: number;
  stamps_count?: number;
  tables_count?: number;
  cuts?: Array<{
    id?: number | string;
    bbox?: number[];
    text?: string;
    confidence?: number;
    engine?: string;
  }>;
  stamp_crops?: string[];
  tables?: Array<{
    id?: number | string;
    bbox?: number[];
    rows?: number;
    cols?: number;
  }>;
  text?: string;
  full_text?: string;
  ocr_results?: Array<{
    text: string;
    confidence: number;
    bbox: number[];
  }>;
}
