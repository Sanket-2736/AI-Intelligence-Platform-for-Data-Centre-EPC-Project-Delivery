# EPC Intelligence Platform

## AI-Powered Data Centre Project Delivery System

A complete, production-grade platform for managing data centre EPC (Engineering, Procurement, Construction) projects with AI-driven intelligence across 5 specialized agent modules.

---

## 📋 System Overview

### Architecture: Data Layer → Intelligence Layer → Action Layer

**Tech Stack:**
- **Backend:** Python 3.11 + FastAPI
- **LLM:** Cerebras API (llama-3.3-70b) — 1000+ tokens/sec inference
- **Vector DB:** ChromaDB (local, persistent) for RAG
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2) — local, free
- **Database:** Supabase (PostgreSQL, free tier)
- **Frontend:** React 18 + Tailwind CSS + Recharts + Leaflet.js
- **PDF Generation:** ReportLab
- **Orchestration:** LangChain
- **Hosting:** Vercel (frontend) + Render.com (backend)

---

## 🤖 Five AI Agent Modules

### 1. **RFI Intelligence Agent** (`/api/rfi`)
**Retrieval-Augmented Generation for Project Q&A**

- Document ingestion: PDF spec, RFI, submittal, meeting minutes
- Semantic search with ChromaDB RAG
- Cerebras LLM-powered Q&A with citations
- Chat interface with message history

**Key Endpoints:**
- `POST /api/rfi/ingest/batch` — Upload documents
- `POST /api/rfi/query` — Ask questions
- `GET /api/rfi/documents` — List indexed docs
- `GET /api/rfi/history` — Chat history

**Frontend:** Two-panel layout (doc library + chat)

---

### 2. **Specification & Quality Compliance Agent** (`/api/compliance`)
**Vendor Submittal vs. Spec Deviation Analysis**

- Compare vendor submittal against master specification
- Tier III/IV certification impact analysis
- Auto-generate non-conformances (NCs) with severity
- TIA-942 / Uptime Institute standard compliance

**Key Endpoints:**
- `POST /api/compliance/check` — Analyze submittal
- `GET /api/compliance/dashboard` — NC summary
- `GET /api/compliance/ncs` — List NCs by status
- `PUT /api/compliance/nc/{id}` — Close NC

**Frontend:** Upload → Analysis → Findings → Dashboard

---

### 3. **Predictive Schedule Risk Engine** (`/api/schedule`)
**Critical Path Analysis & Delay Prediction**

- Excel schedule parsing (multiple formats)
- Float/slack analysis + critical path detection
- Risk scoring with ripple effect modeling
- Baseline comparison for schedule variance
- 30-day risk trend analysis

**Key Endpoints:**
- `POST /api/schedule/analyse` — Upload & analyze schedule
- `POST /api/schedule/compare` — Baseline comparison
- `GET /api/schedule/trend` — Risk time-series
- `GET /api/schedule/report` — Weekly report

**Frontend:** Upload → 3 tabs (Risk Report, Risk Trend, Weekly Report)

---

### 4. **Supply Chain Visibility & Risk Agent** (`/api/supply-chain`)
**Real-Time Shipment Tracking & Procurement Risk**

- CSV shipment ingestion with buffer analysis
- Automatic at-risk flagging (<7d = CRITICAL, <14d = HIGH)
- Leaflet map with color-coded markers
- Procurement alternative modeling with Cerebras
- Regional customs clearance risk assessment

**Key Endpoints:**
- `POST /api/supply-chain/upload` — CSV analysis
- `POST /api/supply-chain/shipment` — Manual entry
- `GET /api/supply-chain/map` — GeoJSON for Leaflet
- `GET /api/supply-chain/alerts` — Sorted by urgency
- `POST /api/supply-chain/alternatives` — Alternative sourcing

**Frontend:** Leaflet map (left) + Alerts panel (right)

---

### 5. **Commissioning QA Copilot** (`/api/commissioning`)
**AI-Driven Test Procedure Generation & ITP Documentation**

- RAG-based test procedure generation from TIA-942 standards
- 20+ standard test library for POWER, COOLING, IT, FIRE, SECURITY
- Real-time commissioning dashboard with pass rate tracking
- Professional A4 PDF ITP generation with ReportLab
- Auto-generate NCs for failed tests

**Key Endpoints:**
- `POST /api/commissioning/standards/ingest` — Upload standards
- `POST /api/commissioning/procedure/generate` — AI-generated test
- `GET /api/commissioning/tests/library` — Standard tests
- `POST /api/commissioning/results/log` — Log test result
- `GET /api/commissioning/itp/download` — Generate PDF
- `GET /api/commissioning/dashboard` — Test stats

**Frontend:** 3 tabs (Procedures, Log Results, ITP Report)

---

## 🎨 Frontend Architecture

### App Shell (`src/App.jsx`)
- React Router with 6 routes
- Dark theme (Tailwind): bg-gray-950 base, gray-900 sidebar
- Responsive layout: persistent sidebar (desktop), hamburger (mobile)
- Header with logo, project name, live status indicator

### Sidebar (`src/components/Sidebar.jsx`)
- Navigation with Lucide icons
- Active state highlighting (blue)
- Version badge + Cerebras branding
- Responsive mobile overlay

### Pages (5 Complete Agent UIs)
1. **Dashboard** — KPI cards (2x3) + charts + recent activity
2. **RFI Agent** — Two-panel chat with document library
3. **Compliance Agent** — Upload → Analysis → Findings → Dashboard
4. **Schedule Agent** — Upload → 3 tabs (Report, Trend, Weekly)
5. **Supply Chain** — Leaflet map + alerts panel
6. **Commissioning** — 3 tabs (Procedures, Log Results, ITP)

### Shared Components
- `KPICard.jsx` — Reusable metric cards with trend indicators
- `StatusBadge.jsx` — Color-coded status labels
- `LoadingSpinner.jsx` — Animated spinners with messages
- `FileUpload.jsx` — Drag-drop file upload

### API Client (`src/api/client.js`)
Axios instance with:
- Base URL from `REACT_APP_API_URL` env var
- Request/response interceptors
- Named API groups for each agent
- Error handling with console.error

---

## 🗄️ Database Schema (Supabase PostgreSQL)

### Tables
- **non_conformances** — NC records with severity, clause references, status
- **schedule_risks** — Schedule risk findings with mitigation options
- **shipments** — Procurement items with buffer_days, status, location
- **commissioning_records** — Test results with acceptance criteria
- **rfi_log** — Q&A history with citations
- **dashboard_summary** — Aggregated KPI cache

---

## 🔐 Environment Variables

**Backend** (`.env`):
```
CEREBRAS_API_KEY=<key>
SUPABASE_URL=<url>
SUPABASE_ANON_KEY=<key>
ENVIRONMENT=production
DEBUG=False
MAX_CHUNK_SIZE=500
CHUNK_OVERLAP=100
```

**Frontend** (`.env.local`):
```
REACT_APP_API_URL=http://localhost:8000
```

---

## 🚀 Deployment

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Production
- **Backend:** Deploy to Render.com (FastAPI on Python 3.11 runtime)
- **Frontend:** Deploy to Vercel (React SPA)
- **Database:** Supabase PostgreSQL (free tier auto-scales)
- **Vector DB:** ChromaDB persists locally on backend

---

## ⚡ Key Features

✅ **100% Production-Ready Code**
- Full type hints (Python + TypeScript)
- Comprehensive error handling
- Logging throughout
- Module docstrings

✅ **Zero-Cost AI**
- Cerebras free tier (100 requests/day, generous daily limit)
- ChromaDB local (no external dependencies)
- Sentence-transformers CPU embedding
- Supabase free tier PostgreSQL

✅ **Fast Inference**
- Cerebras llama-3.3-70b: 1000+ tokens/sec
- ChromaDB local RAG: <100ms query
- Cached embedding model

✅ **Professional UX**
- Dark theme consistent across all pages
- Responsive layout (mobile + desktop)
- Real-time loading states
- Interactive charts (Recharts)
- Map visualization (Leaflet)

✅ **Fully Documented**
- Module docstrings for every file
- API documentation via FastAPI /docs
- README with architecture overview
- Type hints on all functions

---

## 📚 Project Documentation Files

- **MASTER PROJECT CONTEXT** — Complete system requirements
- **IMPLEMENTATION_CHECKLIST.md** — Feature completion status
- **DATA_INGESTION_SUMMARY.md** — Ingestion layer overview
- **Agent-specific guides:**
  - `backend/agents/RFI_AGENT_GUIDE.md`
  - `backend/db/DATABASE_LAYER.md`
  - `backend/ingestion/INGESTION_LAYER.md`
  - `backend/ingestion/QUICK_REFERENCE.md`

---

## 🔄 Data Flow Example

### RFI Query Workflow
1. User uploads PDF to frontend
2. FileUpload triggers `rfiApi.ingestBatch()`
3. Backend PDF parser extracts text
4. Chunker splits into 500-char overlapping segments
5. ChromaDB ingests with metadata
6. User asks question
7. ChromaDB semantic search (top-4 chunks)
8. Cerebras LLM generates answer + citations
9. Frontend displays with source links

### Compliance Check Workflow
1. User uploads Spec + Submittal PDFs
2. PDF parser extracts text from both
3. Cerebras compares against Spec using `COMMISSIONING_SYSTEM_PROMPT`
4. LLM returns structured JSON with findings
5. Each FAIL finding → Auto-generates NC
6. NCs stored in Supabase
7. Frontend displays findings table + severity breakdown

---

## 🛠️ Development Notes

### Adding New Features
1. Create backend endpoint in agent module
2. Add Pydantic model for request/response
3. Implement Supabase/ChromaDB operations
4. Create React page component
5. Add API client function
6. Wire up UI with loading/error states

### Performance Optimization
- ChromaDB queries cached in memory
- Cerebras calls throttled (100/day free tier)
- Frontend lazy-loads charts with React.lazy
- Backend caches non_conformances summary

### Testing
- Backend: pytest with fixtures
- Frontend: Jest + React Testing Library
- E2E: Playwright for critical user flows

---

## 📞 Support

For issues or questions:
1. Check module docstrings (all files have module-level docs)
2. Review /docs endpoint for API schema
3. Check console.error in browser DevTools
4. Review Cerebras API usage in settings

---

**Built with ⚡ Cerebras & 🧠 ChromaDB — AI-Powered Engineering**
