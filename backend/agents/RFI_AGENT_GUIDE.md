# RFI Intelligence Agent - Complete Guide

## Overview

The RFI Intelligence Agent is Agent 5 of the EPC Intelligence Platform. It handles Request For Information (RFI) processing using Retrieval-Augmented Generation (RAG) with semantic search and the Cerebras LLM.

**Key Value:**
- Ingests project documents (specs, drawings, meeting minutes, RFIs)
- Answers technical questions with citations and high accuracy
- Tracks RFI history for reference and learning
- Searches similar past RFIs to accelerate decision-making

---

## Architecture

```
Project Documents
│
├─ Specifications (PDF)
├─ Drawings (PDF)
├─ Meeting Minutes (PDF)
├─ Submittal Documents (PDF)
├─ Prior RFIs (PDF/text)
└─ Change Orders (PDF)
│
↓ Extract & Chunk
│
ChromaDB (Vector Store)
│
├─ COLLECTION_PROJECT_DOCS
│  └─ Semantic embeddings of all documents
│  └─ ~2000-5000 chunks typical project
│
↓ Query & Retrieve
│
┌─────────────────────────────────┐
│  User RFI Question              │
│  "What are cooling requirements?"│
└─────────────────────────────────┘
│
↓ Semantic Search (6 top results)
↓ + Similar Past RFI Search (3 similar)
│
┌─────────────────────────────────┐
│  Build RAG Context              │
│  [SOURCE 1: Spec Section 3.2.1] │
│  [SOURCE 2: Drawing E-101]      │
│  [SOURCE 3: Prior RFI #45]      │
└─────────────────────────────────┘
│
↓ Cerebras LLM (llama-3.3-70b)
│
┌─────────────────────────────────┐
│  Answer with Citations          │
│  "According to Spec Section     │
│   3.2.1 [SOURCE 1], cooling     │
│   requirements are..."          │
└─────────────────────────────────┘
│
↓ Log to Database
│
Supabase (rfi_log table)
```

---

## Core Functions

### 1. ingest_project_document()

Ingest a single document into the RAG system.

```python
from agents.rfi_agent import ingest_project_document

result = ingest_project_document(
    file_path='/path/to/spec.pdf',
    filename='HVAC_Specification_2026.pdf',
    doc_type='spec',
    date='2026-01-01',
    revision='v2.1'
)

print(f"Ingested {result['chunks_ingested']} chunks from {result['pages_processed']} pages")
```

**Document Types:**
- `spec` - Specification documents (e.g., HVAC spec, electrical spec)
- `rfi` - Previous RFI requests and responses
- `submittal` - Vendor submittal documents
- `meeting_minutes` - Project meeting notes
- `change_order` - Change orders and addenda
- `drawing` - Engineering drawings (scanned or PDF)
- `standard` - Industry standards (TIA-942, IEC 61439, etc.)

**How It Works:**
1. Extracts text from PDF using PyMuPDF (with OCR fallback for scanned PDFs)
2. Extracts all tables using pdfplumber
3. Creates chunks using sliding window (1024 chars, 128 char overlap)
4. Preserves metadata: doc_type, filename, date, revision, source_collection
5. Creates summary chunk (first 500 + last 200 chars) for quick retrieval
6. Stores all chunks in ChromaDB with semantic embeddings

**Output:**
```python
{
    'filename': 'HVAC_Specification_2026.pdf',
    'doc_type': 'spec',
    'chunks_ingested': 45,
    'pages_processed': 25,
    'tables_found': 3,
    'success': True,
    'error': None
}
```

### 2. ingest_multiple_documents()

Batch ingest multiple documents at once.

```python
from agents.rfi_agent import ingest_multiple_documents

files = [
    {
        'path': '/tmp/spec.pdf',
        'filename': 'HVAC_Specification.pdf',
        'doc_type': 'spec',
        'date': '2026-01-01',
        'revision': 'v2'
    },
    {
        'path': '/tmp/drawing.pdf',
        'filename': 'Electrical_Drawing_E-101.pdf',
        'doc_type': 'drawing',
        'date': '2026-01-15',
        'revision': 'v1'
    }
]

result = ingest_multiple_documents(files)

print(f"Ingested {len(files) - len(result['failed_files'])} files")
print(f"Total chunks: {result['total_chunks']}")
print(f"Failed: {result['failed_files']}")
```

**Output:**
```python
{
    'total_files': 2,
    'total_chunks': 127,
    'failed_files': [],
    'duration_seconds': 15.3,
    'success': True
}
```

### 3. answer_question()

Answer an RFI question using RAG with Cerebras LLM.

```python
from agents.rfi_agent import answer_question

result = answer_question(
    question="What are the cooling system requirements and acceptance criteria?",
    doc_type_filter='spec'  # Optional: filter to specs only
)

print(f"Answer: {result['answer']}")
print(f"Sources: {result['sources_retrieved']}")
print(f"Confidence: {result['answer_confidence']}")
print(f"Processing time: {result['processing_time_ms']}ms")
```

**How It Works:**
1. Query ChromaDB for 6 most relevant documents (with optional doc_type filter)
2. Search for similar past RFIs (similarity search)
3. Build context string with [SOURCE N] citations
4. Call Cerebras LLM with system prompt + context + question
5. LLM generates answer with inline citations
6. Log to Supabase rfi_log table
7. Calculate confidence based on:
   - Number of sources retrieved (≥5 = better)
   - Relevance score of top result (>0.7 = HIGH, >0.5 = MEDIUM, else LOW)

**Output:**
```python
{
    'question': "What are the cooling requirements?",
    'answer': "According to Specification Section 3.2.1 [SOURCE 1], ...",
    'citations': [
        {
            'filename': 'HVAC_Specification.pdf',
            'doc_type': 'spec',
            'relevance_score': 0.89,
            'date': '2026-01-01',
            'revision': 'v2'
        },
        {...}
    ],
    'similar_past_rfis': [
        {
            'question': 'Prior RFI about cooling',
            'answer': 'Previous answer...',
            'date': '2025-12-15'
        }
    ],
    'sources_retrieved': 6,
    'processing_time_ms': 2340,
    'answer_confidence': 'HIGH',
    'success': True
}
```

### 4. get_document_list()

Get list of all ingested documents.

```python
from agents.rfi_agent import get_document_list

docs = get_document_list()

for doc in docs:
    print(f"{doc['filename']} ({doc['doc_type']}): {doc['chunks_count']} chunks")
```

### 5. clear_project_documents()

Clear all project documents and reset the RAG system.

```python
from agents.rfi_agent import clear_project_documents

result = clear_project_documents()

if result['success']:
    print("Project cleared - ready for fresh start")
```

---

## FastAPI Endpoints

### POST /api/rfi/ingest/single

Ingest a single document via HTTP.

```bash
curl -X POST http://localhost:8000/api/rfi/ingest/single \
  -F "file=@spec.pdf" \
  -F "doc_type=spec" \
  -F "date=2026-01-01" \
  -F "revision=v2"
```

**Response:**
```json
{
    "filename": "spec.pdf",
    "doc_type": "spec",
    "chunks_ingested": 45,
    "pages_processed": 25,
    "tables_found": 3,
    "success": true
}
```

### POST /api/rfi/ingest/batch

Batch ingest multiple documents.

```bash
curl -X POST http://localhost:8000/api/rfi/ingest/batch \
  -F "files=@spec.pdf" \
  -F "files=@drawing.pdf" \
  -F "doc_types=spec" \
  -F "doc_types=drawing" \
  -F "dates=2026-01-01" \
  -F "dates=2026-01-15"
```

**Response:**
```json
{
    "total_files": 2,
    "total_chunks": 127,
    "failed_files": [],
    "duration_seconds": 15.3,
    "success": true
}
```

### POST /api/rfi/query

Answer an RFI question.

```bash
curl -X POST http://localhost:8000/api/rfi/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the cooling requirements?",
    "doc_type_filter": "spec"
  }'
```

**Response:**
```json
{
    "question": "What are the cooling requirements?",
    "answer": "According to Specification Section 3.2.1 [SOURCE 1], the cooling system must maintain temperature between 18-27°C... See prior RFI #45 for similar requirements.",
    "citations": [
        {
            "filename": "HVAC_Specification.pdf",
            "doc_type": "spec",
            "relevance_score": 0.89,
            "date": "2026-01-01",
            "revision": "v2"
        }
    ],
    "similar_past_rfis": [
        {
            "question": "Prior cooling RFI",
            "answer": "Previous answer...",
            "date": "2025-12-15"
        }
    ],
    "sources_retrieved": 6,
    "processing_time_ms": 2340,
    "answer_confidence": "HIGH",
    "success": true
}
```

### GET /api/rfi/documents

List all ingested documents.

```bash
curl http://localhost:8000/api/rfi/documents
```

### GET /api/rfi/history

Get recent RFI history (last 20 by default).

```bash
curl http://localhost:8000/api/rfi/history?limit=10
```

### DELETE /api/rfi/reset

Clear all project documents (caution!).

```bash
curl -X DELETE http://localhost:8000/api/rfi/reset
```

---

## Usage Workflow

### Example: Complete Project Setup

```python
from agents.rfi_agent import (
    ingest_project_document,
    ingest_multiple_documents,
    answer_question
)

# Step 1: Ingest core specification documents
spec_files = [
    {
        'path': '/docs/HVAC_Spec.pdf',
        'filename': 'HVAC_Specification_v2.1.pdf',
        'doc_type': 'spec',
        'date': '2026-01-01',
        'revision': 'v2.1'
    },
    {
        'path': '/docs/Electrical_Spec.pdf',
        'filename': 'Electrical_Specification_v1.5.pdf',
        'doc_type': 'spec',
        'date': '2025-12-15',
        'revision': 'v1.5'
    }
]

result = ingest_multiple_documents(spec_files)
print(f"Ingested {result['total_chunks']} chunks in {result['duration_seconds']}s")

# Step 2: Add related documents
ingest_project_document(
    '/docs/drawings.pdf',
    'Electrical_Drawings_E-101_to_E-110.pdf',
    'drawing',
    '2026-01-10',
    'v1'
)

# Step 3: Start answering questions
answer = answer_question(
    "What is the maximum cooling capacity and redundancy requirement?"
)

print("=== RFI Answer ===")
print(answer['answer'])
print(f"\nConfidence: {answer['answer_confidence']}")
print(f"Sources: {answer['sources_retrieved']}")
for citation in answer['citations']:
    print(f"  - {citation['filename']} ({citation['relevance_score']:.2f})")
```

---

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Ingest 25-page PDF | 2-3s | Includes extraction + chunking + embedding |
| Query + Answer | 2-3s | ChromaDB search + Cerebras LLM call |
| Semantic search (6 results) | 100-200ms | Local embeddings, very fast |
| LLM generation | 1-2s | Cerebras @1000+ tokens/sec |

**Memory Usage:**
- ChromaDB instance: ~500MB for 10,000 embeddings
- Typical project: 5-10 documents = 1000-2000 chunks = 50-100MB

---

## Best Practices

### Document Organization

1. **Specs:** Always ingest master specifications early
2. **Drawings:** Include electrical, mechanical, architectural for context
3. **Meeting Minutes:** Valuable for design decisions and rationale
4. **Prior RFIs:** Prevents duplicate questions and accelerates knowledge

### Asking Good Questions

**Good Questions:**
- "What are the cooling system requirements and acceptance criteria?"
- "How should we handle backup power for IT systems?"
- "What is the commissioning procedure for UPS systems?"

**Avoid:**
- Too vague: "Tell me about the spec"
- Too specific: Questions about specific serial numbers not in documents
- Leading: "The spec says X, right?" (Let the search find it)

### Handling Ambiguities

If the LLM response says "Not specified in available documentation":
- This is valuable! It identifies specification gaps
- Add clarifying documents (standards, vendor docs)
- Create formal RFI/addendum to specification

---

## Troubleshooting

### Low Confidence Answer

**Symptom:** answer_confidence = "LOW"

**Causes:**
- Not enough documents ingested
- Question too specific or poorly worded
- Relevant documents not yet added

**Solution:**
- Ingest more project documents
- Rephrase question more broadly
- Check get_document_list() to verify documents present

### Slow Query Response

**Symptom:** processing_time_ms > 5000

**Causes:**
- Large number of chunks (>10,000)
- Network latency to Cerebras
- LLM generating very long response

**Solution:**
- Use doc_type_filter to narrow search scope
- Ask more specific questions
- Monitor Cerebras API usage

### Missing Information in Answer

**Symptom:** Answer doesn't reference relevant document

**Causes:**
- Document not yet ingested
- Phrasing different from question
- Relevance scoring didn't rank it highly

**Solution:**
- Verify document ingested with get_document_list()
- Try reformulated question
- Check ChromaDB stats with chroma.get_collection_stats()

---

## Integration with Other Agents

The RFI Agent can feed other agents:

```python
from agents.rfi_agent import answer_question
from agents.compliance_agent import analyze_submittal

# Get answer from RFI agent
rfi_answer = answer_question("What are the compliance requirements?")

# Use answer context for compliance analysis
compliance_result = analyze_submittal(
    submittal_doc=vendor_doc,
    spec_context=rfi_answer['answer'],  # Use RFI context
    citations=rfi_answer['citations']
)
```

---

## Production Deployment

### Prerequisites
- Cerebras API key configured
- Supabase database ready
- ChromaDB persistent storage available

### Initialization
```python
# On app startup
from agents import rfi_agent
from db.chroma_client import get_chroma_manager

# Verify ChromaDB is ready
chroma = get_chroma_manager()
stats = chroma.get_collection_stats(COLLECTION_PROJECT_DOCS)
print(f"Ready with {stats['document_count']} documents")
```

### Monitoring
- Track answer_confidence distribution (aim for >70% HIGH)
- Monitor processing_time_ms (aim for <3000ms)
- Log failed ingestions
- Track LLM token usage

---

## Next Steps

1. **Test with sample documents** - Use sample_data/ PDFs
2. **Frontend integration** - Build RFI chat UI
3. **Multi-language support** - Cerebras supports multiple languages
4. **Export to PDF** - Generate formal RFI responses
5. **Webhook notifications** - Alert project team of new RFIs
