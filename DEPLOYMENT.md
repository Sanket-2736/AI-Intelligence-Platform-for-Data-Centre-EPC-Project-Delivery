# EPC Intelligence Platform - Deployment Guide

Production-ready deployment configuration for AWS, Render, Vercel, and Docker.

---

## 🐳 Local Docker Development

### Build and Run

```bash
# Build Docker image
cd backend
docker build -t epc-intelligence-api:latest .

# Run container with environment variables
docker run \
  -p 8000:8000 \
  -e CEREBRAS_API_KEY=<your-key> \
  -e SUPABASE_URL=<your-url> \
  -e SUPABASE_ANON_KEY=<your-key> \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=INFO \
  epc-intelligence-api:latest

# Check health
curl http://localhost:8000/health
```

### Docker Compose (Optional)

```yaml
version: '3.8'

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      CEREBRAS_API_KEY: ${CEREBRAS_API_KEY}
      SUPABASE_URL: ${SUPABASE_URL}
      SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY}
      ENVIRONMENT: production
      LOG_LEVEL: INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 🚀 Render.com Deployment (Backend)

### Step 1: Prepare Repository

Ensure these files exist in your GitHub repository:
- `backend/render.yaml` — Deployment configuration
- `backend/requirements.txt` — Python dependencies
- `backend/Dockerfile` — Container definition
- `backend/.dockerignore` — Build optimization

### Step 2: Connect to Render

1. Go to [https://render.com](https://render.com)
2. Sign in with GitHub
3. Click "New +" → "Web Service"
4. Select your repository
5. Configure:
   - **Name**: `epc-intelligence-api`
   - **Root Directory**: `epc-intelligence/backend` (if monorepo)
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Step 3: Set Environment Variables

In Render dashboard, go to **Environment** and add:

```
CEREBRAS_API_KEY = <your-cerebras-key>
SUPABASE_URL = <your-supabase-url>
SUPABASE_ANON_KEY = <your-supabase-anon-key>
ENVIRONMENT = production
LOG_LEVEL = INFO
DEBUG = false
CHROMA_DB_PATH = /tmp/chroma_data
EMBEDDING_MODEL = all-MiniLM-L6-v2
MAX_CHUNK_SIZE = 1024
CHUNK_OVERLAP = 128
CEREBRAS_TIMEOUT_SECONDS = 30
DB_TIMEOUT_SECONDS = 30
```

### Step 4: Deploy

Click **Deploy** and monitor logs. API will be available at:
```
https://epc-intelligence-api.onrender.com
```

### Health Check

```bash
curl https://epc-intelligence-api.onrender.com/health
```

---

## 🎨 Vercel Deployment (Frontend)

### Step 1: Prepare Repository

Ensure these files exist:
- `frontend/vercel.json` — Deployment and routing config
- `frontend/package.json` — Dependencies and build script
- `frontend/.env.example` — Environment template

### Step 2: Connect to Vercel

1. Go to [https://vercel.com](https://vercel.com)
2. Sign in with GitHub
3. Click "Add New..." → "Project"
4. Select your repository
5. Configure:
   - **Framework**: React
   - **Root Directory**: `epc-intelligence/frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

### Step 3: Set Environment Variables

In Vercel dashboard, go to **Settings** → **Environment Variables**:

```
REACT_APP_API_URL = https://epc-intelligence-api.onrender.com
REACT_APP_APP_NAME = EPC Intelligence Platform
```

### Step 4: Deploy

Vercel will auto-deploy on every push to main. Frontend available at:
```
https://epc-intelligence.vercel.app
```

---

## 🔒 AWS Deployment (Advanced)

### Option 1: ECS (Elastic Container Service)

```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com

docker build -t epc-api:latest backend/
docker tag epc-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/epc-api:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/epc-api:latest

# Deploy task definition in ECS dashboard
# Set container image to ECR URL
# Set environment variables
# Set port 8000
# Enable auto-scaling
```

### Option 2: Lambda + API Gateway

Not recommended due to cold starts and ChromaDB persistence needs.

### Option 3: Elastic Beanstalk

```bash
# Initialize EB
eb init -p python-3.11 epc-intelligence

# Deploy
eb create production --instance-type t3.small

# Set environment variables
eb setenv \
  CEREBRAS_API_KEY=<key> \
  SUPABASE_URL=<url> \
  SUPABASE_ANON_KEY=<key>

# Monitor
eb logs
```

---

## 📊 Monitoring & Logs

### Render Console

- **Dashboard**: View memory/CPU usage, request counts
- **Logs**: Real-time streaming logs with JSON format
- **Metrics**: Response times, error rates

### CloudWatch (AWS)

```bash
# View logs
aws logs tail /ecs/epc-intelligence --follow

# Create metric
aws cloudwatch put-metric-alarm \
  --alarm-name epc-api-errors \
  --alarm-description "Alert on error rate > 1%" \
  --metric-name ErrorRate \
  --statistic Average \
  --period 60 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold
```

### Structured Logging

All logs are JSON-formatted and include:
- `timestamp`: ISO 8601 datetime
- `level`: ERROR, WARNING, INFO, DEBUG
- `logger`: Module name
- `message`: Log message
- `agent`: Agent name (if applicable)
- `duration_ms`: Response time (if applicable)
- `success`: Success/failure (if applicable)

Example log:
```json
{
  "timestamp": "2026-06-22T15:30:45.123456",
  "level": "INFO",
  "logger": "backend.agents.rfi_agent",
  "message": "Query returned 4 results",
  "agent": "rfi",
  "duration_ms": 523.4
}
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions (Automatic Deployment)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy EPC Intelligence

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Render
        run: |
          curl -X POST https://api.render.com/deploy/srv-${{ secrets.RENDER_SERVICE_ID }}?key=${{ secrets.RENDER_DEPLOY_KEY }}

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Vercel
        run: |
          npx vercel --prod \
            --token ${{ secrets.VERCEL_TOKEN }}
```

---

## 🧪 Pre-Deployment Checklist

### Backend
- [ ] Run `python test_smoke.py` — all tests pass
- [ ] Check `python -m pytest tests/` — unit tests pass
- [ ] Verify `.env.example` has all required variables
- [ ] Update `render.yaml` with correct environment variables
- [ ] Verify `Dockerfile` builds locally: `docker build -t test .`
- [ ] Test health endpoint: `curl http://localhost:8000/health`

### Frontend
- [ ] Run `npm run build` — no errors
- [ ] Check `npm run lint` — no linting errors
- [ ] Update `.env.example` with production API URL
- [ ] Test production build locally: `npm run preview`
- [ ] Verify `vercel.json` routing is correct

### Database
- [ ] Verify Supabase connection with `test_smoke.py`
- [ ] Backup production database
- [ ] Run migrations if any

### API Integration
- [ ] Verify all agent endpoints respond: `curl http://localhost:8000/docs`
- [ ] Test critical workflows end-to-end:
  - RFI: Upload → Query → Verify response
  - Compliance: Upload spec + submittal → Check deviations
  - Schedule: Upload Excel → Check risk score
  - Supply Chain: Upload CSV → Check map data
  - Commissioning: Generate procedure → Download PDF

---

## 📈 Scaling Configuration

### Render (Manual)

```bash
# Increase plan to standard/pro
# In dashboard: Settings → Instance Type
# Select: Pro (2x RAM, 2x vCPU)

# Enable auto-scaling
# Settings → Scaling
# Min instances: 1
# Max instances: 3
# Scale based on CPU > 70%
```

### Vercel (Automatic)

Vercel automatically scales frontend based on:
- Traffic volume
- Edge function execution time
- Serverless function duration

No manual configuration needed.

---

## 🔐 Security Checklist

- [ ] API keys stored in environment variables (never in code)
- [ ] CORS restricted to known domains in production:
  ```python
  allow_origins=["https://epc-intelligence.vercel.app"]
  ```
- [ ] Debug mode disabled: `DEBUG=false`
- [ ] HTTPS enforced (automatic on Render/Vercel)
- [ ] Rate limiting configured (see `utils/cerebras_client.py`)
- [ ] Database credentials never logged
- [ ] Supabase Row Level Security (RLS) enabled
- [ ] API authentication considered for future

---

## 🚨 Troubleshooting

### "Failed to connect to Cerebras"

1. Verify API key is valid: `curl -H "Authorization: Bearer $CEREBRAS_API_KEY" https://api.cerebras.ai/v1/models`
2. Check rate limiting: API defaults to 100 requests/day
3. Verify timeout: Check `CEREBRAS_TIMEOUT_SECONDS` is set

### "ChromaDB data lost after restart"

- On Render: Use persistent disk or mount volume
- On Docker: Mount volume: `docker run -v chroma_data:/app/chroma_data`
- On Vercel: Frontend doesn't persist data (API handles this)

### "High memory usage"

- Reduce `MAX_CHUNK_SIZE` from 1024 to 512
- Reduce `MAX_CONTEXT_TOKENS` from 4096 to 2048
- Enable ChromaDB compaction: `chroma compact_collections()`

### "Slow API responses"

- Check Cerebras usage stats: `GET /health` returns `avg_response_time_ms`
- If > 2000ms, likely rate-limited
- Scale to larger Render instance

---

## 📞 Support & Resources

- **Render Documentation**: https://render.com/docs
- **Vercel Documentation**: https://vercel.com/docs
- **Cerebras API**: https://www.cerebras.net/api-docs
- **Supabase Documentation**: https://supabase.com/docs
- **Docker Documentation**: https://docs.docker.com

---

**Last Updated**: 2026-06-22
**Version**: 1.0.0
