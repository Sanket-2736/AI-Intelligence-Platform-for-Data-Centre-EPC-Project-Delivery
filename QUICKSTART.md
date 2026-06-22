# Quick Start Guide

Get EPC Intelligence Platform running in 5 minutes.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- Environment variables (see `.env.example` files)

---

## 1️⃣ Backend Setup (5 min)

```bash
# Navigate to backend
cd epc-intelligence/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Copy environment template
cp .env.example .env

# Edit .env with your keys
# CEREBRAS_API_KEY=<your-key>
# SUPABASE_URL=<your-url>
# SUPABASE_ANON_KEY=<your-key>

# Install dependencies
pip install -r requirements.txt

# Run smoke tests to verify setup
python test_smoke.py

# Start backend
uvicorn main:app --reload

# API running at http://localhost:8000
# Docs at http://localhost:8000/docs
```

---

## 2️⃣ Frontend Setup (3 min)

```bash
# Navigate to frontend (new terminal)
cd epc-intelligence/frontend

# Copy environment template
cp .env.example .env.local

# Install dependencies
npm install

# Start development server
npm run dev

# App running at http://localhost:3000
```

---

## 3️⃣ Generate Sample Data (2 min)

```bash
# Navigate to sample data
cd epc-intelligence/sample_data

# Generate all demo files
python generate_samples.py

# Files created:
# - sample_schedule.xlsx
# - sample_shipments.csv
# - sample_ups_spec.txt
# - sample_ups_submittal.txt
```

---

## 4️⃣ Run Demo Walkthrough (10 min)

Follow the demo script:
```bash
cat ../DEMO_WALKTHROUGH.md
```

**Quick demo flow:**
1. RFI Agent: Upload spec + submittal, ask questions (0:00-2:00)
2. Compliance Agent: Check compliance, show deviations (2:00-4:00)
3. Schedule Agent: Upload schedule, show risk analysis (4:00-6:00)
4. Supply Chain: Show shipment map and alerts (6:00-7:00)
5. Commissioning: Generate test procedure, download PDF (7:00-8:00)
6. Dashboard: Show KPIs and summary (8:00-10:00)

---

## 🚨 Common Issues

### "CEREBRAS_API_KEY is required"

```bash
# In backend .env file, add:
CEREBRAS_API_KEY=sk-...your-key...

# Or set as environment variable:
export CEREBRAS_API_KEY=sk-...
```

### "Cannot connect to Supabase"

```bash
# Verify credentials in backend .env:
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJxxxx

# Test connection:
cd backend
python -c "from db.supabase_client import get_supabase_manager; print(get_supabase_manager().test_connection())"
```

### "ChromaDB error: No such file or directory"

```bash
# ChromaDB will auto-create directory, but if issue persists:
mkdir -p backend/chroma_data
```

### "CORS error when calling API from frontend"

```bash
# Check backend is running:
curl http://localhost:8000/health

# Verify CORS in main.py is set to "*" for dev
# In production, restrict to specific domain
```

### "Port 8000 or 3000 already in use"

```bash
# Find and kill process using port
lsof -i :8000  # Find process on 8000
kill -9 <PID>

# Or use different port:
uvicorn main:app --port 8001
npm run dev -- --port 3001
```

---

## 📂 Project Structure

```
epc-intelligence/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Configuration + logging
│   ├── requirements.txt          # Python dependencies
│   ├── test_smoke.py            # Smoke tests
│   ├── Dockerfile               # Container definition
│   ├── render.yaml              # Render deployment config
│   ├── agents/                  # Five AI agents
│   ├── db/                      # Database layer (Supabase + ChromaDB)
│   ├── ingestion/               # PDF/Excel parsers
│   └── utils/                   # Cerebras LLM client, chunker
│
├── frontend/
│   ├── index.html               # HTML entry
│   ├── package.json             # Node dependencies
│   ├── vercel.json              # Vercel deployment config
│   ├── vite.config.js           # Build config
│   └── src/
│       ├── App.jsx              # Main router
│       ├── api/
│       │   └── client.js        # API client configuration
│       ├── components/          # Shared components
│       │   ├── FileUpload.jsx
│       │   ├── KPICard.jsx
│       │   ├── StatusBadge.jsx
│       │   └── ...
│       └── pages/               # Page components
│           ├── Dashboard.jsx
│           ├── RFIAgent.jsx
│           ├── ComplianceAgent.jsx
│           ├── ScheduleAgent.jsx
│           ├── SupplyChainMap.jsx
│           └── CommissioningAgent.jsx
│
├── sample_data/
│   └── generate_samples.py      # Demo data generator
│
└── Documentation
    ├── README.md                # Project overview
    ├── DEMO_WALKTHROUGH.md      # Demo script
    ├── DEPLOYMENT.md            # Production deployment
    ├── PRODUCTION_READINESS.md  # Readiness checklist
    └── QUICKSTART.md            # This file
```

---

## 🎯 Key Endpoints

### Health & Status
```bash
GET /health                      # Service health check
GET /api/dashboard/summary       # Dashboard KPIs
```

### RFI Intelligence
```bash
POST /api/rfi/ingest/batch      # Upload documents
POST /api/rfi/query             # Ask questions
GET /api/rfi/documents          # List indexed docs
GET /api/rfi/history            # Chat history
```

### Compliance
```bash
POST /api/compliance/check      # Analyze submittal
GET /api/compliance/dashboard   # NC summary
GET /api/compliance/ncs         # List NCs
```

### Schedule Risk
```bash
POST /api/schedule/analyse      # Analyze schedule
GET /api/schedule/trend         # Risk time-series
GET /api/schedule/report        # Weekly report
```

### Supply Chain
```bash
POST /api/supply-chain/upload   # Upload shipments
GET /api/supply-chain/map       # GeoJSON markers
GET /api/supply-chain/alerts    # At-risk items
POST /api/supply-chain/alternatives  # Get alternatives
```

### Commissioning
```bash
POST /api/commissioning/procedure/generate  # Generate test
GET /api/commissioning/tests/library        # Test library
POST /api/commissioning/results/log         # Log result
GET /api/commissioning/itp/download         # Download PDF
```

---

## 🔗 URLs

When running locally:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Supabase**: https://app.supabase.com

When deployed:
- **Frontend**: https://epc-intelligence.vercel.app
- **Backend API**: https://epc-intelligence-api.onrender.com
- **API Docs**: https://epc-intelligence-api.onrender.com/docs

---

## 📊 Monitoring

### Backend Logs
```bash
# Real-time logs (development)
uvicorn main:app --reload

# Structured logs (JSON format)
# Check for agent calls, errors, timing

# Health endpoint
curl http://localhost:8000/health | jq .
```

### Frontend Console
```javascript
// Open browser DevTools (F12)
// Console tab shows:
// - API request/response logging
// - Component lifecycle events
// - Any errors or warnings
```

---

## 🆘 Getting Help

1. **Check logs**
   - Backend: Console output or `backend/app.log`
   - Frontend: Browser DevTools console (F12)

2. **Run smoke tests**
   ```bash
   cd backend
   python test_smoke.py
   ```

3. **Verify environment**
   ```bash
   # Backend
   python -c "import config; print('✓ Config loaded')"
   
   # Frontend
   npm list react react-router-dom
   ```

4. **Check dependencies**
   ```bash
   # Backend
   pip list | grep -E "fastapi|cerebras|supabase|chromadb"
   
   # Frontend
   npm list
   ```

5. **Read documentation**
   - Architecture: `README.md`
   - Deployment: `DEPLOYMENT.md`
   - Production: `PRODUCTION_READINESS.md`

---

## ⏱️ Time Estimates

- Setup: 5 min
- Generate data: 2 min
- Run demo: 10 min
- Deploy backend: 15 min
- Deploy frontend: 10 min
- **Total time to demo**: ~15-20 min

---

## ✅ Success Checklist

- [ ] Backend running: `curl http://localhost:8000/health` returns 200
- [ ] Frontend running: http://localhost:3000 loads
- [ ] Sample data generated: 4 files in `sample_data/`
- [ ] Smoke tests pass: `python test_smoke.py`
- [ ] All agent pages accessible and responsive
- [ ] Demo walkthrough completed successfully
- [ ] No errors in console (Backend or Frontend)

---

**Last Updated**: 2026-06-22  
**Platform Version**: 1.0.0 (Production Ready)
