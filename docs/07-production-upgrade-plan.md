# Production Upgrade Plan — PS 26018 (Land Record Digitization & Validation)

Status as of 2026-09-17, branch `feature/table-first-pipeline`.

Servers running locally: FastAPI `api:app` on :8000, Vite on :5173 (proxies `/segment`, `/jobs`).

---

## A. What is fake right now

### A1. Data and sessions
| # | Where | What is fake |
|---|---|---|
| 1 | `frontend/src/services/api.ts` `INITIAL_SESSIONS` | All 4 dashboard sessions, fields, bboxes, confidences, Paddle/TrOCR "conflict" values are hardcoded |
| 2 | `App.tsx` `handleStartSession` | Reads `customResult.ocr_results`, which the backend never returns, so **every upload falls back to the hardcoded UP Khata fields** |
| 3 | `App.tsx` `handleStartSession` | `accuracy: 94.2`, `processingTime: '8.4s'`, `date: 'Today'`, `totalFields: 15` are constants; script is guessed from the filename (`includes('urdu')`) |
| 4 | `App.tsx` `handleUpdateField` | An edit sets confidence to `0.98` and session accuracy to `96.7`. Nothing is saved |
| 5 | `App.tsx` | Sessions exist only in React state and are lost on refresh |
| 6 | `NewSessionScreen.tsx` `handleRunBenchmark` | If the backend call fails, the error is swallowed and the studio opens with sample data anyway |
| 7 | `NewSessionScreen.tsx` | Schema is a hardcoded string and is ignored (`_schema`); "benchmark / extract" and "blank / describe" toggles do nothing |
| 8 | `NewSessionScreen.tsx` | Accepts `.pdf`, but the backend only decodes images (`cv2.imdecode`), so PDFs fail |
| 9 | `services/api.ts` `runSegmentApi` | Always sends `llm_refine=false` and never sends `ocr_lang` (backend default `en`), so Hindi and Urdu run with the English model |

### A2. Studio / Workspace
| # | Where | What is fake |
|---|---|---|
| 10 | `InteractiveStudioScreen.tsx` chat | Seeded conversation ("123/4 → 128/4") plus a `setTimeout` reply generated from keywords. No LLM call |
| 11 | Studio header | `96.7%` and `94.2% Defensible Precision` are hardcoded |
| 12 | Studio bbox overlay | Uses the hardcoded percentage bboxes, not `polygon_on_source` from the backend |
| 13 | Studio | The line crops (`/jobs/{id}/lines/{n}`), `document.md`, `.docx`, `.txt`, and `page_reassembled.png` are **never shown** |

### A3. Results
| # | Where | What is fake |
|---|---|---|
| 14 | `ResultsScreen.tsx` | `final_accuracy: 94.2`, `passed_benchmark: true`, SHA hash, and `verified_by: 'Asish Sharma (Lead)'` are constants |
| 15 | `ResultsScreen.tsx` report | The whole Markdown report (15 fields, 14 matches, 1.2s latency, audit rows) is a static string |
| 16 | `ResultsScreen.tsx` | Accuracy ring and bars use a hardcoded 94.2 |
| 17 | Results | The real `land_record.json` → `validation.checks` / `review_reasons` never appear |

### A4. Dashboard
| # | Where | What is fake |
|---|---|---|
| 18 | `DashboardScreen.tsx` | Date "Sunday, 14 September 2026", "24" documents, "94.2%", "03" pending, "12 fields unresolved" are all hardcoded |
| 19 | Dashboard pipeline panel | The step ticks and the "microservices on port 8000" copy are static |
| 20 | Dashboard | No state-wise or district-wise progress, no error statistics (both required by the PS) |

### A5. Auth / API / health
| # | Where | What is fake |
|---|---|---|
| 21 | `LoginScreen.tsx` | Any email and password log in ("Any password accepted"); the password field is prefilled |
| 22 | `App.tsx` | `isAuthenticated` starts as `true`. "Demo workspace" skips login |
| 23 | `Navigation.tsx` | Avatar, user, and role are static; logout only flips local state |
| 24 | `ApiPlaygroundScreen.tsx` | API keys `bhm_live_9421fa8392af` / `bhm_live_83921af7b4c92e` are made up; the backend has no auth at all |
| 25 | `services/api.ts` `checkBackendHealth` | Pings `/docs`, which Vite doesn't proxy, so it gets `index.html` with a 200. **The "online" indicator is always green** even when the API is down. It should call `/health` (proxied) |
| 26 | Backend | No users, roles, audit trail, database, or persistent storage. Jobs live in `$TMPDIR/linecut-jobs` |

---

## B. The real output format vs. what the UI expects

**Backend `/segment` actually returns** (see `output/sample_test/.../manifest.json`):

```
job_id, source, layout, deskew_deg, lines_found, seconds
lines[]: index, file, file_raw, url, url_raw, polygon_on_source, spine_on_source,
         angle_deg, curvature_px, confidence{curved, off_axis_deg, review},
         text, confidence_ocr, dual_ocr{paddle, trocr, status, similarity, corrections}
tables[]: bbox, cells, markdown
stamps[]: bbox, crop
markdown, document_text
documents{markdown, docx, text, latent, land_record}
land_record{schema_version, metadata{state,district,tehsil,village,year,survey_no},
            plots[], owners[], mutations[], validation{...}}
validation{validation_passed, rules_passed/failed/skipped, checks[], review_required, review_reasons[]}
llm_refinement{model,status,error}, ocr_error, table_error
```

**Frontend `BackendSegmentResponse` (`types.ts`) expects:** `session_id`, `cuts[]`, `ocr_results[]`, `cuts_count`, `stamp_crops`, `full_text`. **None of these exist.**

The UI is built around a *field list* (`ExtractedField`), but the product is a *reconstructed document* (segments → md/docx/txt) **plus** a land-record schema. The data model needs to be rebuilt:

```
Job        { id, status, source, lang, created_at, timings, owner, … }
Segment    { index, kind: line|table|stamp, polygon, crop_url, text, confidence,
             paddle, trocr, status, edited_text, edited_by }
Document   { markdown, txt_url, docx_url, version }
LandRecord { metadata, plots, owners, mutations, per-field confidence + source segment }
Validation { checks[], review_reasons[] }
```

---

## C. Product / UX upgrade (Studio)

Target flow: **Upload → Processing → Studio → Verify → Digitised document → Export / Push**

### C1. Upload
- [ ] Drag-and-drop for image, PDF (multi-page), and TIFF, plus batch upload
- [ ] Language picker (Hindi, Urdu, Punjabi, Marathi, Bengali, Tamil, Kannada, English, Auto)
- [ ] Document type picker (Jamabandi, Khatauni, Khasra, Mutation, Sale Deed, Other / Auto)
- [ ] State / district / tehsil pre-tag (drives dashboards)
- [ ] No schema textarea; the LLM derives the schema

### C2. Processing
- [ ] Async job with a progress stream (SSE or WebSocket) showing stages: deskew, tables and stamps, lines, OCR, LLM, validation
- [ ] Real errors surfaced, no silent fallback

### C3. Studio layout (Lovable / Emergent style)
```
┌──────────── top bar: file · lang · status · Verify ─────────────┐
│ Left: original page           │ Right: preview tabs              │
│  - segment overlays (polygons)│  [Document] [Markdown] [Text]     │
│  - click → highlight both ways│  [DOCX] [Segments]                │
│  - zoom / pan / page nav      │  - inline edit of any segment     │
│                               │  - low-confidence underline       │
├───────────────────────────────┴──────────────────────────────────┤
│ Bottom drawer (resizable): Extracted record │ Validation │ Chat   │
│  - LLM-derived schema as an editable form (not JSON)              │
│  - each field links to its source segment                         │
└──────────────────────────────────────────────────────────────────┘
```
- [ ] Segments tab: crop image, OCR text, Paddle vs TrOCR diff, confidence, accept / edit
- [ ] Editing a segment updates md, txt, and docx (regenerated server-side, versioned)
- [ ] Confidence scoring per segment and per field, with a filter for "needs review"
- [ ] Keyboard review mode: next uncertain segment, accept, edit
- [ ] Chat uses the real LLM with tools (edit field, re-run validation)

### C4. Verify
- [ ] "Verify" opens a doc viewer of the digitised document (rendered DOCX / paged view), side by side with the original
- [ ] Record form view with a human-readable layout; JSON only under Export
- [ ] Approve / reject / send back, with a comment. Every action is written to the audit log

### C5. Export / integration
- [ ] Download DOCX, MD, TXT, PDF (searchable), and JSON
- [ ] "Push to LRMS / DILRMP" connector stub and GIS link (khasra → cadastral map)

### C6. Dashboard (PS requirements)
- [ ] Documents processed, extraction accuracy (from human corrections), validation status, pending verification, error stats
- [ ] State-wise / district-wise progress (table + choropleth)
- [ ] Recent jobs table from the DB

### C7. Other PS items
- [ ] Duplicate detection (image hash plus khasra/khata match)
- [ ] Cross-record validation (area totals, share totals, mutation chain)
- [ ] Learning loop: store corrections as training pairs and show a correction-rate trend
- [ ] Admin: users, roles, API keys, audit log viewer

### C8. Visual clean-up
- [ ] Remove **all** green / neon / pulsing status dots and pills (`Navigation.tsx:142`, `LoginScreen.tsx:68-76`, `LandingPage.tsx:114`, `bg-[#EAF4ED]` badges, `animate-pulse` overlay)
- [ ] Remove explanatory / marketing copy inside the app ("Any password accepted", "Active microservices on port 8000", "Defensible Precision", "Keep this key secure…", pipeline explainer, landing feature essays)
- [ ] Remove "Demo workspace" / "SIH 2026" / "benchmark" wording and confetti
- [ ] Minimal, modern, neutral palette; status via text or icon only
- [ ] Real router (`react-router`) instead of hash switching; route guards

---

## D. Platform / backend

### D1. Auth and sessions
- [ ] Users table, argon2 password hashing, and login / logout / refresh
- [ ] JWT access token (short-lived) + httpOnly refresh cookie; session table with revoke
- [ ] RBAC roles: `admin`, `supervisor` (approve), `operator` (upload/edit), `viewer`, `api_client`
- [ ] Scope by state/district per user
- [ ] API keys (hashed, prefixed, revocable) for the `/v1` API
- [ ] Rate limiting and CORS lock-down

### D2. Database (PostgreSQL)
- [ ] SQLAlchemy 2 + Alembic migrations
- [ ] Tables: `users`, `sessions`, `api_keys`, `jobs`, `pages`, `segments`, `segment_edits`, `documents` (versioned), `land_records`, `record_fields`, `validations`, `audit_log` (append-only), `corrections_dataset`
- [ ] Optional PostGIS for plots / cadastral geometry

### D3. Storage
- [ ] Object storage: MinIO locally, S3 on AWS (originals, crops, md/docx/txt, reassembled page)
- [ ] Pre-signed URLs; nothing served from `$TMPDIR`
- [ ] SHA-256 per file for integrity and duplicate detection

### D4. Processing architecture
- [ ] `/segment` is synchronous (about 28s per page). Move it to a worker queue (Celery or RQ + Redis)
- [ ] `POST /v1/jobs` → `GET /v1/jobs/{id}` + `/events` (SSE)
- [ ] PDF → pages (PyMuPDF)
- [ ] `PATCH /v1/jobs/{id}/segments/{n}` → regenerate documents
- [ ] `POST /v1/jobs/{id}/verify`, `/approve`, `/reject`
- [ ] `GET /v1/stats` for dashboards
- [ ] Versioned `/v1`, OpenAPI, structured errors
- [ ] Load models once per worker; GPU worker option

### D5. Config / hygiene
- [ ] `requirements.txt` / `pyproject.toml` (none exists now)
- [ ] Settings via env (pydantic-settings); the LLM key is already read from env
- [ ] Structured logging, `/health` and `/ready`, Prometheus metrics
- [ ] Tests: API contract tests, frontend type generation from OpenAPI (`openapi-typescript`) so the type drift in B can't happen again

---

## E. Docker Compose, CI/CD, AWS

### E1. Compose (`docker-compose.yml`)
- [ ] `api` (FastAPI, uvicorn/gunicorn)
- [ ] `worker` (OCR + LLM, same image, different command)
- [ ] `web` (Vite build served by nginx, reverse proxy to `api`)
- [ ] `postgres` (16, volume, healthcheck)
- [ ] `redis`
- [ ] `minio` + bucket init
- [ ] `docker-compose.override.yml` for dev hot reload
- [ ] `.env.example`

### E2. CI (GitHub Actions)
- [ ] On PR: ruff + pytest (Python); oxlint + `tsc` + build (frontend); docker build; Trivy scan
- [ ] Cache pip, npm, and Docker layers

### E3. CD → AWS
- [ ] On merge to `main`: build and push images to ECR (OIDC role, no static keys)
- [ ] Deploy to ECS Fargate (api, web) plus EC2/GPU capacity for `worker`, *or* a single EC2 running Compose as the simpler first step
- [ ] RDS PostgreSQL, ElastiCache Redis, S3, ALB + ACM TLS, Secrets Manager, CloudWatch logs
- [ ] Run Alembic migrations as a one-off task before rollout
- [ ] Staging → production with manual approval
- [ ] IaC with Terraform (or CDK) in `infra/`

---

## F. Suggested order
1. Fix the contract: real types, drop `INITIAL_SESSIONS`, fix the health check, send `ocr_lang`, and surface errors
2. Build the Studio: document preview tabs, segment overlay and edit, bottom record drawer, Verify doc viewer
3. UI clean-up (C8)
4. Postgres + auth + storage + job queue
5. Real dashboards, audit, and RBAC
6. Compose → CI → AWS CD
