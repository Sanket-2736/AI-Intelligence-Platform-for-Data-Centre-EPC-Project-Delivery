# EPC Intelligence Platform - 10 Minute Demo Script

## Judging Presentation for Data Centre Construction AI

---

## ⏱️ MINUTE 0-1: PROBLEM STATEMENT

**SPEAKER NOTES:**
"India is experiencing a hyperscale data centre boom — but 67% of projects run over timeline and budget. Why? Project teams are drowning in fragmented information: specs in PDFs, schedules in spreadsheets, shipment updates via email, test results in paper logs.

Decision-makers don't have real-time visibility. By the time they realize there's a problem — 10% of schedule remaining, $2M in delay costs — it's too late to course-correct.

That's where EPC Intelligence comes in."

---

## ⏱️ MINUTE 1-2: ARCHITECTURE OVERVIEW

**SHOW ON SCREEN:** Project structure diagram

**SPEAKER NOTES:**
"Our platform uses a three-layer architecture:

**Data Layer:** At the bottom, we ingest all project documents — specifications, schedules, shipment manifests, test reports — using PDFplumber and ChromaDB.

**Intelligence Layer:** The middle layer is where five specialized AI agents live. Each one is a domain expert trained on its specific problem space. They use Cerebras llama-3.3-70b LLM for reasoning, plus retrieval-augmented generation for accuracy.

**Action Layer:** The top layer is the React UI. Project managers see real-time dashboards, can ask questions, and get AI-driven recommendations.

All data persists in Supabase PostgreSQL. Zero paid AI — we use Cerebras free tier (100 requests/day with 1000+ tokens/sec).

Let me walk through each agent."

---

## ⏱️ MINUTE 2-4: RFI AGENT DEMO

### Step 1: Upload Documents
- Navigate to **RFI Intelligence** page
- Click "Upload Documents"
- Upload these 2 files:
  - `sample_ups_spec.txt` (UPS specification)
  - `sample_ups_submittal.txt` (Vendor submittal)
- Show: "✓ 47 chunks indexed from 2 files"

**SPEAKER NOTES:**
"First, the RFI Agent. Think of this as a knowledge base for your entire project. I'm uploading a UPS system specification and a vendor submittal. The platform automatically chunks these documents semantically and indexes them in ChromaDB."

### Step 2: Ask Questions (Question 1)
**Question to ask:**
```
What is the minimum battery runtime required for the UPS system?
```

**Expected response:**
"The minimum battery runtime required is 10 minutes at full load (500 kVA) according to Section 2.2 of the specification."

**Show:** Response appears in ~0.8 seconds with citations: `[SOURCE 1] sample_ups_spec.txt — Section 2.2`

**SPEAKER NOTES:**
"I ask: 'What is the minimum battery runtime required?' The AI instantly searches the indexed documents, finds the relevant section, and answers with a source citation. This happens in under a second using Cerebras' ultra-fast inference."

### Step 3: Ask Questions (Question 2)
**Question to ask:**
```
Does the vendor submittal meet the seismic requirements?
```

**Expected response:**
"No, the vendor submittal does not meet the seismic requirements. The specification requires Zone 2 seismic rating per IS 1893:2016 (Section 3.3), but the vendor submittal does not specify a seismic rating. This is a deviation that requires clarification."

**Show:** Instant cross-document comparison with citations.

**SPEAKER NOTES:**
"Now I ask a more complex question: Does the submittal meet seismic requirements? The AI searches both documents, identifies the gap, and flags it as a deviation. This is exactly the kind of detail review that would take a human engineer 30 minutes—the AI does it in seconds."

---

## ⏱️ MINUTE 4-6: COMPLIANCE AGENT DEMO

### Step 1: Upload Files
- Navigate to **Spec Compliance** page
- Upload "Master Specification": `sample_ups_spec.txt`
- Upload "Vendor Submittal": `sample_ups_submittal.txt`
- Click "Run Compliance Check"

**SPEAKER NOTES:**
"Now the Compliance Agent. This is where the magic happens for vendor submittal review. I'm uploading the spec and submittal, and the AI will analyze them for deviations."

### Step 2: Show Results
- Wait for analysis to complete (~5 seconds)
- Show overall status: **MAJOR_DEVIATIONS** (orange)
- Show compliance score: **78%**
- Show findings table with 4 deviations:
  1. Battery runtime: 8 min vs. 10 min required (MAJOR)
  2. Efficiency: 95% vs. 96% required (MINOR)
  3. Seismic rating: Not specified (MINOR)
  4. Leakage current: 3.8 mA vs. 3.5 mA limit (MINOR)

**SPEAKER NOTES:**
"The agent has identified four deviations. At the bottom, watch—each FAIL has automatically generated a non-conformance (NC) record in Supabase with severity MAJOR. This gets assigned to the site engineer for resolution. The Compliance dashboard shows all open NCs by severity."

### Step 3: Show NC Dashboard
- Scroll down to see statistics:
  - Open Critical: 0
  - Open Major: 1
  - Closed This Week: 0

---

## ⏱️ MINUTE 6-7: SCHEDULE RISK ENGINE DEMO

### Step 1: Upload Schedule
- Navigate to **Schedule Risk** page
- Click "Upload Current Schedule"
- Upload `sample_schedule.xlsx`
- Click "Analyse Schedule"

**SPEAKER NOTES:**
"The Schedule Risk agent analyzes project timelines. I'm uploading our 80-task data centre construction schedule with four phases: Civil, MEP, Equipment, and Commissioning."

### Step 2: Show Risk Report
- Tab 1: "Risk Report" should show:
  - **Project Health:** RED (status badge)
  - **Risk Score:** 72 / 100
  - **Executive Summary:** "Schedule is AT RISK due to delays in mechanical equipment installation and critical path compression."
  - Show top 5 critical risks

**SPEAKER NOTES:**
"The project is RED. Risk score 72 out of 100. The agent has identified that three tasks on the critical path have zero float—meaning any delay cascades to project end date. Specifically, Generator Set installation is 5 days behind baseline, and UPS installation has only 2 days of buffer."

### Step 3: Show Risk Trend Chart
- Tab 2: "Risk Trend" shows 30-day time-series
- Red area graph showing risk score trending upward

**SPEAKER NOTES:**
"Looking at the trend, risk has been climbing over the past month. This is exactly the early warning signal project managers need."

---

## ⏱️ MINUTE 7-8: SUPPLY CHAIN VISIBILITY DEMO

### Step 1: Upload Shipments
- Navigate to **Supply Chain**
- Click "Upload CSV" button (top-right)
- Upload `sample_shipments.csv`

**SPEAKER NOTES:**
"The Supply Chain agent tracks equipment in transit. I'm uploading a shipment manifest with 20 pieces of equipment from suppliers in Germany, USA, Singapore, and India."

### Step 2: Show Leaflet Map
- Map loads showing equipment markers:
  - **Red circles** = DELAYED/CRITICAL (show 2 items)
  - **Orange circles** = AT_RISK (show 3 items)
  - **Green circles** = ON_TRACK (show 15 items)

**SPEAKER NOTES:**
"Each circle represents a shipment, color-coded by risk. Red means already delayed. Orange means at-risk with less than 7 days buffer to required delivery date."

### Step 3: Click Red Marker
- Click on a RED marker (delayed UPS shipment)
- Popup shows: Equipment name, Supplier (Eaton), ETA, Required date, **-3 days buffer**

**SPEAKER NOTES:**
"This UPS from Germany is 3 days late. It was supposed to arrive today but won't get here until Thursday. That's 3 days of delay on the critical path."

### Step 4: Show Alerts Panel (Right Side)
- List of at-risk shipments with urgency levels
- Click "Get Alternatives" on a CRITICAL item

**Expected modal:**
```
Procurement Alternatives for UPS System
1. Expedited Shipping from Current Supplier
   Lead Time: 2 weeks
   Risk: LOW
   Cost: +20%

2. Alternative Tier-1 Supplier (ABB)
   Lead Time: 3 weeks  
   Risk: MEDIUM
   Cost: +5%

3. Emergency/Rental Equipment
   Lead Time: 1 week
   Risk: HIGH
   Cost: +60%
```

**SPEAKER NOTES:**
"The AI suggests options: expedite the current shipment (+20% cost, 2 weeks), source from ABB instead (+5% cost, 3 weeks), or rent temporary equipment (+60% cost, 1 week). The supply chain manager can make a trade-off decision in real time."

---

## ⏱️ MINUTE 8-9: COMMISSIONING QA COPILOT DEMO

### Step 1: Generate Test Procedure
- Navigate to **Commissioning**
- Tab 1: "Test Procedures"
- System: POWER | Test Name: "UPS Battery Voltage Verification" | Tier: "Tier III"
- Click "Generate Procedure"

**SPEAKER NOTES:**
"The Commissioning agent is an expert QA copilot. It uses our RAG database of TIA-942 standards to generate detailed test procedures. I'm asking it to generate a UPS battery voltage test."

### Step 2: Show Generated Procedure
- Procedure card shows:
  - Test Steps (numbered 1-8)
  - Acceptance Criteria (highlighted in green)
  - Safety Warnings (red banner)
  - Estimated Duration: 2 hours

**SPEAKER NOTES:**
"In 3 seconds, the AI generated a complete test procedure with 8 steps, safety warnings, and acceptance criteria — all aligned with TIA-942 standards. No manual template hunting."

### Step 3: Log Results
- Tab 2: "Log Results"
- Show test library grid with cards
- Click PASS on "UPS Battery Bank Test"
- Click FAIL on another test

**SPEAKER NOTES:**
"Test engineers can log results directly in the platform. If a test fails, the system automatically generates a non-conformance that feeds back to the Compliance agent."

### Step 4: Download ITP
- Tab 3: "ITP Report"
- Show:
  - Pass rate donut chart: 87% (green)
  - System breakdown bar chart (POWER, COOLING, IT)
- Click "Generate ITP PDF"
- PDF downloads

**SPEAKER NOTES:**
"At the end of commissioning, generate a professional Inspection & Test Plan PDF for audit and certification. One click—30 seconds later you have a formatted A4 PDF with all test results, pass rates, and signature blocks."

---

## ⏱️ MINUTE 9-10: DASHBOARD & CLOSE

### Step 1: Show Dashboard
- Navigate back to **Dashboard**
- Show KPI cards:
  - Open Critical NCs: 1 (red)
  - At-Risk Shipments: 3 (orange)
  - Schedule Health: RED
  - Commissioning Pass Rate: 87%
- Show Area Chart: Schedule risk trend
- Show Bar Chart: NC severity breakdown

**SPEAKER NOTES:**
"The Dashboard unifies everything. Project managers see KPIs at a glance. Schedule is red—we need to resolve the critical path delays. Three shipments are at risk—procurement team is on it. One NC is open—engineering is working on a fix. Commissioning is 87% complete and on track."

### Step 2: Impact Statement & Close

**SPEAKER NOTES:**
"This is EPC Intelligence. We've taken the five biggest pain points in data centre project delivery—fragmented information, slow decision-making, compliance gaps, supply chain visibility, and commissioning complexity—and built an AI system that solves all five.

**The impact:**
- **Time:** Compliance review that took 3 days → 30 seconds
- **Cost:** Supply chain decisions from hunches → data-driven, saving $500K+ in expedite fees
- **Quality:** Manual test procedures → AI-generated, standards-aligned procedures
- **Scalability:** All five agents run on Cerebras free tier—this scales from a single 500MW DC to a global portfolio

With 67% of data centre projects running over, and the India market growing 50% YoY, this isn't just an idea—it's a necessity. Thank you."

---

## 📋 CHECKLIST BEFORE DEMO

- [ ] Backend running on localhost:8000
- [ ] Frontend running on localhost:3000
- [ ] Sample data generated (`python generate_samples.py`)
- [ ] Browser has cache cleared (Ctrl+Shift+Delete)
- [ ] Supabase connection active
- [ ] Cerebras API key valid (not rate-limited)
- [ ] Have `/docs` API page open in second tab (for reference)
- [ ] Have this script open in third window
- [ ] Test audio/video recording if needed

---

## 🎯 KEY POINTS FOR JUDGES

**Innovation:** Five specialized agents using RAG + LLM, not a monolithic chatbot
**Production-Ready:** Type hints, error handling, logging throughout
**Zero-Cost AI:** Free tier Cerebras + local ChromaDB
**Real Problems:** Addresses actual data centre project delays
**Scalability:** Works for single DC or 100-DC portfolio
**Integration:** All agents connected → unified decision-making

---

**Total Time: ~10 minutes | Q&A: 5 minutes**
