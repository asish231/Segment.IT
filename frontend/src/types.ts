// Mirrors the real FastAPI backend contract (api.py). Kept in sync by hand —
// if the backend response shape changes, update this file in the same change.

export type ScreenType =
  | 'landing'
  | 'login'
  | 'dashboard'
  | 'new'
  | 'workspace'
  | 'verify'
  | 'api';

export type UserRole = 'admin' | 'supervisor' | 'operator' | 'viewer' | 'api_client';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  state: string;
  district: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user: AuthUser;
}

// --- OCR / segmentation -----------------------------------------------

export interface OcrEngineResult {
  text?: string;
  confidence?: number;
  [key: string]: unknown;
}

export interface DualOcrResult {
  paddle: OcrEngineResult;
  trocr: OcrEngineResult;
  status: string;
  similarity: number | null;
  corrections: string[];
}

export interface LineSegment {
  index: number;
  file: string;
  file_raw?: string;
  url: string;
  url_raw?: string;
  angle_deg: number;
  curvature_px: number;
  row: number;
  text?: string;
  confidence_ocr?: number;
  dual_ocr?: DualOcrResult;
  human_corrected?: boolean;
  polygon_on_source?: number[][];
  spine_on_source?: number[][];
  png_base64?: string;
  confidence?: { curved?: boolean; off_axis_deg?: number; review?: boolean };
}

export interface TableCell {
  row?: number;
  row_idx?: number;
  col?: number;
  text: string;
  confidence?: number;
}

export interface TableData {
  bbox: [number, number, number, number];
  cells: TableCell[];
  markdown: string;
  rows?: number;
  cols?: number;
}

export interface StampData {
  bbox: [number, number, number, number];
  crop?: string;
  type?: string;
}

export interface ValidationCheck {
  rule: string;
  status: 'passed' | 'failed' | 'skipped' | 'info';
  message: string;
  [key: string]: unknown;
}

export interface Validation {
  validation_passed: boolean;
  total_rules_checked: number;
  rules_passed: number;
  rules_failed: number;
  rules_skipped: number;
  checks: ValidationCheck[];
  review_required: boolean;
  review_reasons: string[];
}

export interface LandRecordPlot {
  khasra_no: string;
  area: string;
  area_numeric?: number;
  land_classification?: string;
  crop?: string;
  [key: string]: unknown;
}

export interface LandRecordOwner {
  name: string;
  father_or_husband_name?: string;
  share?: string;
  [key: string]: unknown;
}

// Mercury's one-time "is this actually a land record" verdict — computed once during
// /segment and stored on the job; Verify displays it, it never recomputes it.
export interface DocumentClassification {
  is_land_record: boolean | null; // null = not classified (llm_refine was off, or no tables found)
  confidence: number;
  reasoning: string;
}

export interface LandRecord {
  schema_version: string;
  metadata: {
    state: string;
    district: string;
    tehsil: string;
    village: string;
    year: string;
    survey_no: string;
  };
  plots: LandRecordPlot[];
  owners: LandRecordOwner[];
  mutations: Record<string, unknown>[];
  validation?: Validation;
  classification?: DocumentClassification;
}

// Raw response from POST /segment
export interface SegmentResponse {
  job_id: string;
  source: string;
  layout: string;
  deskew_deg: number;
  lines_found: number;
  seconds: number;
  lines: LineSegment[];
  tables?: TableData[];
  stamps?: StampData[];
  markdown?: string;
  document_text?: string;
  documents?: Record<string, string>;
  land_record?: LandRecord;
  validation?: Validation;
  llm_refinement?: { model: string; status: string; error?: string | null };
  ocr_error?: string;
  table_error?: string;
  job_status?: 'complete' | 'needs_review' | 'failed';
  job_db_error?: string;
}

// --- Persisted jobs (/v1/jobs) -----------------------------------------

export type JobStatus = 'processing' | 'complete' | 'needs_review' | 'verified' | 'rejected' | 'failed';

export interface JobSummary {
  id: string;
  owner_id: string | null;
  source_filename: string;
  lang: string;
  doc_type: string;
  state: string;
  district: string;
  tehsil: string;
  status: JobStatus;
  lines_found: number;
  tables_found: number;
  stamps_found: number;
  avg_confidence: number;
  low_confidence_count: number;
  corrections_count: number;
  validation_passed: boolean;
  review_required: boolean;
  is_land_record: boolean | null;
  classification_confidence: number;
  classification_reasoning: string;
  processing_seconds: number;
  error: string;
  verified_by_id: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
  documents: {
    markdown: string;
    docx: string;
    text: string;
    latent: string;
    land_record: string;
    source_image: string;
    reassembled_image: string;
  };
}

export interface JobDetail extends JobSummary {
  land_record: LandRecord;
  validation: Validation;
  latent?: {
    job_id: string;
    source: string;
    lines_found: number;
    source_size?: [number, number];
    tables?: TableData[];
    stamps?: StampData[];
    lines: LineSegment[];
  };
  markdown?: string;
}

export interface DashboardStats {
  total_documents: number;
  by_status: Record<string, number>;
  pending_review: number;
  verified: number;
  rejected: number;
  failed: number;
  avg_extraction_confidence: number;
  state_wise: Record<string, number>;
  district_wise: Record<string, number>;
}

export interface ApiKeySummary {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked: boolean;
}
