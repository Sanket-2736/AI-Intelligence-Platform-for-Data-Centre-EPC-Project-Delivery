# Database Layer - Complete Documentation

## Overview

The Database Layer provides a complete abstraction over:
1. **ChromaDB** - Vector store for semantic search (RAG)
2. **Supabase PostgreSQL** - Relational database for structured data

Both use **singleton pattern** to ensure single instance across the application.

---

## Architecture

```
Ingestion Layer
       ↓
   Data Chunks
       ↓
┌──────────────────────────────────────┐
│      Database Layer (Managers)       │
├──────────────────┬───────────────────┤
│ ChromaManager    │ SupabaseManager   │
├──────────────────┼───────────────────┤
│ Vector Search    │ Structured Data   │
│ (5 collections)  │ (5 tables)        │
│ RAG Context      │ Persistent State  │
└──────────────────┴───────────────────┘
       ↓                    ↓
   ChromaDB           Supabase PostgreSQL
 Embeddings          CRUD + Analytics
```

---

## ChromaDB Client

### Overview

**Purpose:** Store document embeddings and enable semantic search for all agents.

**Singleton:** `ChromaManager` class ensures one instance per application.

**Collections (5 total):**
```python
COLLECTION_PROJECT_DOCS        # General project documents (RFI agent)
COLLECTION_SPECS               # Specifications (Compliance agent)
COLLECTION_COMMISSIONING       # Commissioning standards (Commissioning agent)
COLLECTION_SUPPLY_CHAIN        # Supply chain context (Supply chain agent)
COLLECTION_SCHEDULES           # Project schedules (Schedule agent)
```

### Initialization

```python
from db.chroma_client import get_chroma_manager

# Get singleton instance
chroma = get_chroma_manager()

# Automatically:
# - Creates persistent client at CHROMA_DB_PATH
# - Initializes SentenceTransformer embeddings (all-MiniLM-L6-v2)
# - Sets up collection caching
```

### Key Methods

#### `get_collection(name: str) -> chromadb.Collection`

Get or create a collection.

```python
specs_collection = chroma.get_collection(COLLECTION_SPECS)
# Returns cached collection if exists, creates otherwise
```

#### `ingest_chunks(collection_name, chunks) -> Dict`

Ingest chunks from ingestion layer into ChromaDB.

**Input chunks format (from chunker.py):**
```python
chunks = [
    {
        'text': 'The specification requires that...',
        'metadata': {
            'filename': 'spec.pdf',
            'page_number': 1,
            'chunk_index': 0,
            'doc_type': 'specification'
        }
    },
    ...
]
```

**Usage:**
```python
from ingestion import file_router
from ingestion.file_router import FileType
from db.chroma_client import get_chroma_manager, COLLECTION_SPECS

# 1. Ingest PDF
result = file_router.route_file('spec.pdf', 'spec.pdf')
chunks = chunker.chunk_pdf_by_page(result['data']['pages'], result['metadata'])

# 2. Store in ChromaDB
chroma = get_chroma_manager()
ingest_result = chroma.ingest_chunks(COLLECTION_SPECS, chunks)

print(f"Ingested: {ingest_result['ingested']}")
print(f"Duration: {ingest_result['duration_seconds']:.2f}s")
```

**Output:**
```python
{
    'ingested': 45,              # New chunks added
    'skipped': 0,                # Duplicates skipped
    'total': 45,                 # Total processed
    'collection': 'specifications',
    'duration_seconds': 1.23,
    'success': True,
    'error': None
}
```

**Features:**
- Deterministic ID generation (MD5 of collection + text[:100])
- Prevents duplicates via upsert
- Batch processing (groups of 100)
- Full error handling

#### `query(collection_name, query_text, n_results=5, filters=None) -> Dict`

Semantic search with optional metadata filtering.

**Basic query:**
```python
result = chroma.query(
    collection_name=COLLECTION_SPECS,
    query_text="What are the cooling requirements?",
    n_results=5
)

for doc in result['results']:
    print(f"Score: {doc['relevance_score']:.3f}")
    print(f"Text: {doc['text'][:200]}...")
    print(f"Source: {doc['metadata'].get('filename')}")
```

**Query with filters:**
```python
result = chroma.query(
    collection_name=COLLECTION_PROJECT_DOCS,
    query_text="previous RFI responses",
    n_results=3,
    filters={"doc_type": {"$eq": "rfi"}}  # Only RFI documents
)
```

**Output:**
```python
{
    'query': 'What are the cooling requirements?',
    'results': [
        {
            'id': 'a1b2c3d4...',
            'text': 'Cooling: Maintain temperature between 18-27°C...',
            'metadata': {'filename': 'spec.pdf', 'page': 5},
            'distance': 0.15,
            'relevance_score': 0.85  # 1 - distance
        },
        ...
    ],
    'collection': 'specifications',
    'count': 3,
    'success': True,
    'error': None
}
```

**Relevance Score:** 0-1 scale where 1.0 = perfect match, 0.0 = no match.

#### `search_similar_rfis(question, n_results=3) -> List[Dict]`

Convenience method to find similar past RFIs.

```python
similar = chroma.search_similar_rfis(
    "How do we handle software upgrades?",
    n_results=3
)

if similar:
    print(f"Found {len(similar)} similar RFIs")
    for rfi in similar:
        print(f"Score: {rfi['relevance_score']:.3f}")
        print(f"Previous Q&A: {rfi['text'][:200]}...")
```

#### `get_collection_stats(name) -> Dict`

Get collection statistics.

```python
stats = chroma.get_collection_stats(COLLECTION_SPECS)

print(f"Documents: {stats['document_count']}")
print(f"Embedding dims: {stats['embedding_dimensions']}")  # 384 for all-MiniLM-L6-v2
```

#### `delete_collection(name) -> bool`

Delete and clear a collection (careful!).

```python
# Re-ingest specs
chroma.delete_collection(COLLECTION_SPECS)
# Now can ingest new specs without conflicts
```

---

## Supabase Client

### Overview

**Purpose:** Store and query structured data for all EPC platform operations.

**Singleton:** `SupabaseManager` class ensures one instance per application.

**Tables (5 total):**
- non_conformances
- schedule_risks
- shipments
- commissioning_records
- rfi_log

### Initialization

```python
from db.supabase_client import get_supabase_manager

# Get singleton instance
db = get_supabase_manager()

# Automatically:
# - Creates Supabase client with SUPABASE_URL and SUPABASE_ANON_KEY
# - Tests database connection
# - Logs initialization status
```

### Non-Conformances CRUD

#### Insert
```python
db = get_supabase_manager()

result = db.insert_non_conformance({
    'nc_id': 'NC-2026-001',
    'severity': 'critical',
    'clause_ref': '3.2.1 Cooling Requirements',
    'description': 'Cooling unit not rated for required ambient',
    'submittal_file': 'submittal_pump.pdf',
    'spec_file': 'spec_hvac.pdf',
    'recommended_action': 'Source alternative unit from Schneider Electric',
    'status': 'open'  # Defaults if not provided
})

if result['success']:
    print(f"Created: {result['data']['id']}")
else:
    print(f"Error: {result['error']}")
```

#### Retrieve All (with optional filter)
```python
# All non-conformances
all_ncs = db.get_all_non_conformances()

# Only open
open_ncs = db.get_all_non_conformances(status='open')

# Only critical open
critical_open = [nc for nc in db.get_all_non_conformances('open')
                  if nc['severity'].lower() == 'critical']
```

#### Update Status
```python
result = db.update_nc_status(
    nc_id='NC-2026-001',
    status='closed',
    resolution='Alternative unit sourced and approved'
)
```

#### Statistics
```python
stats = db.get_nc_summary_stats()

print(f"Total NCs: {stats['total']}")
print(f"Critical: {stats['critical']}")
print(f"Major: {stats['major']}")
print(f"By status: {stats['by_status']}")
# Output: {'open': 5, 'closed': 12, 'deferred': 2}
```

### Schedule Risks CRUD

#### Insert
```python
result = db.insert_schedule_risk({
    'task_name': 'Mechanical Installation - Phase 2',
    'risk_level': 'high',
    'risk_description': 'Supplier delay (Eaton transformer) could push critical path 3 weeks',
    'mitigation': 'Pre-order transformer, use expedited shipping from Germany',
    'snapshot_date': '2026-01-20'  # Auto-defaults to today
})
```

#### Get Latest
```python
risks = db.get_latest_risks(limit=10)

for risk in risks:
    print(f"{risk['task_name']}: {risk['risk_level']}")
    print(f"  Mitigation: {risk['mitigation']}")
```

#### Risk Trend
```python
trend = db.get_risk_trend(days=30)

for day in trend:
    print(f"{day['date']}: {day['high']} high, {day['medium']} medium, {day['low']} low")
```

### Shipments CRUD

#### Upsert (Insert or Update)
```python
result = db.upsert_shipment({
    'equipment_name': 'Power Distribution Unit - 500kVA',
    'supplier': 'Schneider Electric',
    'origin_country': 'France',
    'current_location': 'Port of Rotterdam',
    'eta': '2026-02-15',
    'required_on_site': '2026-02-20',
    'status': 'in_transit',
    'lat': 51.9225,
    'lng': 4.4792,
    'cost_usd': 125000
})

# Updates if equipment_name already exists
```

#### Get All
```python
all_shipments = db.get_all_shipments()

for ship in all_shipments:
    print(f"{ship['equipment_name']} from {ship['supplier']}")
    print(f"  ETA: {ship['eta']}, Required: {ship['required_on_site']}")
    print(f"  Status: {ship['status']}")
```

#### Get At-Risk
```python
at_risk = db.get_at_risk_shipments()

for ship in at_risk:
    print(f"⚠️  {ship['equipment_name']} - Status: {ship['status']}")
    print(f"   ETA: {ship['eta']}, Required: {ship['required_on_site']}")
```

#### Bulk Upsert
```python
shipments = [
    {'equipment_name': 'PDU 1', 'supplier': 'Schneider', ...},
    {'equipment_name': 'PDU 2', 'supplier': 'Eaton', ...},
    {'equipment_name': 'PDU 3', 'supplier': 'ABB', ...},
]

result = db.bulk_upsert_shipments(shipments)
print(f"Upserted: {result['count']} shipments")
```

### Commissioning Records CRUD

#### Insert
```python
result = db.insert_commissioning_record({
    'test_id': 'TEST-HVAC-001',
    'system': 'HVAC - Cooling Unit',
    'test_name': 'Cold Water Loop Pressure Test',
    'acceptance_criteria': 'Pressure holds at 80 PSI for 4 hours without drop',
    'result': 'pass',
    'tested_by': 'John Smith',
    'test_date': '2026-02-10',
    'notes': 'All gauges calibrated. Test completed at 14:30 UTC'
})
```

#### Get by System
```python
hvac_tests = db.get_records_by_system('HVAC - Cooling Unit')

for test in hvac_tests:
    print(f"{test['test_name']}: {test['result'].upper()}")
```

#### Summary
```python
summary = db.get_commissioning_summary()

print(f"Pass Rate: {summary['pass_rate']:.1f}%")
print(f"Passed: {summary['pass_count']}, Failed: {summary['fail_count']}, Pending: {summary['pending_count']}")
print(f"By system:")
for system, counts in summary['by_system'].items():
    print(f"  {system}: {counts['pass']}/{counts['pass']+counts['fail']+counts['pending']}")
```

#### ITP Export
```python
# Get all records for Inspection & Test Plan export
all_records = db.get_all_records_for_itp()

# Can be exported to PDF or Excel for project documentation
```

### RFI Log CRUD

#### Log
```python
result = db.log_rfi(
    question="What is the maximum ambient temperature the cooling system can handle?",
    answer="According to Specification Section 3.2.1, the system is rated for ambient up to 40°C continuous operation with proper maintenance.",
    citations=[
        "HVAC_Specification.pdf:3.2.1",
        "Cooling_System_Datasheet.pdf:page 4"
    ]
)
```

#### Retrieve Recent
```python
rfis = db.get_recent_rfis(limit=20)

for rfi in rfis:
    print(f"Q: {rfi['question'][:100]}...")
    print(f"A: {rfi['answer'][:100]}...")
    print(f"Citations: {len(json.loads(rfi['citations_json']))} sources")
    print()
```

### Dashboard Summary

#### Combined Stats
```python
summary = db.get_dashboard_summary()

print(f"Non-Conformances: {summary['total_ncs']} (Critical: {summary['open_critical_ncs']})")
print(f"At-Risk Shipments: {summary['at_risk_shipments']}")
print(f"Schedule Red Flags: {summary['schedule_red_flags']}")
print(f"Commissioning Pass Rate: {summary['commissioning_pass_rate']:.1f}%")
print(f"Recent RFIs: {summary['recent_rfis_count']}")
```

---

## Integration Patterns

### Pattern 1: Complete Ingestion → Storage Pipeline

```python
from ingestion import file_router
from ingestion import pdf_parser
from utils import chunker
from db.chroma_client import get_chroma_manager, COLLECTION_SPECS
from db.supabase_client import get_supabase_manager

# 1. Ingest document
result = file_router.route_file('specification.pdf', 'specification.pdf')

if result['success']:
    # 2. Create chunks
    chunks = chunker.chunk_pdf_by_page(
        result['data']['pages'],
        result['metadata']
    )
    
    # 3. Store in ChromaDB
    chroma = get_chroma_manager()
    ingest_result = chroma.ingest_chunks(COLLECTION_SPECS, chunks)
    
    # 4. Log in Supabase
    db = get_supabase_manager()
    db.client.table('documents').insert({
        'file_name': result['filename'],
        'file_type': result['file_type'],
        'total_chunks': ingest_result['ingested'],
        'source_collection': COLLECTION_SPECS
    }).execute()
    
    print(f"✓ Stored {ingest_result['ingested']} chunks in ChromaDB")
    print(f"✓ Logged metadata in Supabase")
```

### Pattern 2: Non-Conformance Workflow

```python
from db.supabase_client import get_supabase_manager

db = get_supabase_manager()

# 1. Create non-conformance
nc = db.insert_non_conformance({
    'nc_id': 'NC-001',
    'severity': 'major',
    'clause_ref': '4.1.2',
    'description': 'Unit does not meet spec',
})

# 2. Monitor status
open_ncs = db.get_all_non_conformances('open')

# 3. Update when resolved
db.update_nc_status('NC-001', 'closed', 'Resolved by vendor')

# 4. Get metrics
stats = db.get_nc_summary_stats()
critical_count = stats['critical']
```

### Pattern 3: Supply Chain Tracking

```python
from db.supabase_client import get_supabase_manager

db = get_supabase_manager()

# 1. Bulk ingest shipment data from CSV
shipments_data = [...]  # From ingestion layer

result = db.bulk_upsert_shipments(shipments_data)
print(f"Updated {result['count']} shipments")

# 2. Real-time monitoring
at_risk = db.get_at_risk_shipments()
print(f"⚠️  {len(at_risk)} at-risk shipments")

# 3. Dashboard view
for ship in at_risk:
    print(f"{ship['equipment_name']}: {ship['status']}")
```

### Pattern 4: RFI with RAG

```python
from db.chroma_client import get_chroma_manager, COLLECTION_PROJECT_DOCS
from db.supabase_client import get_supabase_manager

chroma = get_chroma_manager()
db = get_supabase_manager()

# 1. Get similar past RFIs
similar = chroma.search_similar_rfis("cooling system requirements", n_results=3)

# 2. Search all documents for context
context = chroma.query(
    COLLECTION_PROJECT_DOCS,
    "cooling system requirements",
    n_results=10
)

# 3. Send to Cerebras with context (see agents implementation)

# 4. Log the answer
db.log_rfi(
    question="What are the cooling requirements?",
    answer="Based on specification section 3.2.1...",
    citations=[doc['metadata'].get('filename') for doc in context['results']]
)
```

---

## Error Handling

All methods return consistent error structure:

```python
result = db.insert_non_conformance({...})

if result['success']:
    print(f"Created: {result['data']}")
else:
    print(f"Error: {result['error']}")
    # Never raises exception, always returns False + error message
```

Common errors are logged but never crash the application:
- Connection failures
- Invalid data
- Missing tables
- Query errors

---

## Performance Considerations

### ChromaDB
- **Embedding speed:** ~0.5ms per document (local model)
- **Search latency:** ~10-50ms per query
- **Batch insert:** 100 documents per batch
- **Memory:** ~500MB for 10,000 embeddings

### Supabase
- **Insert latency:** ~50-100ms
- **Query latency:** ~20-100ms depending on filter complexity
- **Batch upsert:** Efficient via bulk operations
- **Rate limits:** Managed by Free tier (5GB storage, etc.)

---

## Configuration

Both clients load from `config.py`:

```python
# ChromaDB
CHROMA_DB_PATH = "./chroma_data"              # Persistent storage location
EMBEDDING_MODEL = "all-MiniLM-L6-v2"          # Local embedding model
MAX_CHUNK_SIZE = 1024                         # For ingestion

# Supabase
SUPABASE_URL = "https://...supabase.co"       # From environment
SUPABASE_ANON_KEY = "..."                     # From environment
```

---

## Testing

Both managers are easily testable:

```python
def test_chroma_ingest():
    chroma = get_chroma_manager()
    chunks = [{'text': 'test', 'metadata': {}}]
    result = chroma.ingest_chunks('test_collection', chunks)
    assert result['success']
    assert result['ingested'] == 1

def test_supabase_nc():
    db = get_supabase_manager()
    result = db.insert_non_conformance({'nc_id': 'TEST-001', ...})
    assert result['success']
    assert result['data']['nc_id'] == 'TEST-001'
```

---

## Monitoring & Troubleshooting

### Check ChromaDB Status
```python
chroma = get_chroma_manager()

for collection_name in ['project_docs', 'specifications', 'commissioning_stds', 'supply_chain_context', 'schedules']:
    stats = chroma.get_collection_stats(collection_name)
    print(f"{collection_name}: {stats['document_count']} docs")
```

### Check Supabase Connection
```python
db = get_supabase_manager()

if db.test_connection():
    print("✓ Supabase connected")
else:
    print("✗ Supabase connection failed")
```

### Clear and Re-ingest
```python
chroma = get_chroma_manager()
chroma.clear_all_collections()  # Caution!

# Now re-ingest all documents
```

---

## Next Steps

1. **API Endpoints** - Expose via FastAPI routes
2. **Agent Integration** - Connect to agent implementations
3. **Monitoring** - Set up performance tracking
4. **Backups** - Configure Supabase backups
5. **Caching** - Add Redis for frequently accessed data
