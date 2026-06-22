# Ingestion Layer - Quick Reference

## Import Everything You Need

```python
from ingestion import pdf_parser, excel_parser, file_router
from ingestion.file_router import FileType
from utils import chunker
import logging
```

## Processing by File Type

### 📄 PDF Specification
```python
# Full extraction with text + tables + metadata
result = file_router.route_file('spec.pdf', 'spec.pdf')

if result['success']:
    full_text = result['data']['full_text']
    pages = result['data']['pages']
    metadata = result['metadata']
    
    # Chunk for embedding
    chunks = chunker.chunk_pdf_by_page(pages, metadata)
    
    # Create overview
    summary = chunker.create_document_summary_chunk(full_text, metadata)
```

### 📊 Project Schedule (Excel)
```python
# Parse with format auto-detection
result = file_router.route_file('schedule.xlsx', 'schedule.xlsx')

if result['success']:
    parse_data = result['data']
    detected_format = result['metadata']['detected_format']
    
    # Get key metrics
    total_tasks = parse_data['total_tasks']
    overdue_count = parse_data['overdue_count']
    at_risk_count = parse_data['at_risk_count']
    
    # Access normalized tasks
    tasks = parse_data['tasks']
    for task in tasks:
        print(f"{task['task_id']}: {task['is_overdue']}, {task['days_remaining']} days remaining")
```

### 📦 Procurement (CSV)
```python
# Parse with at-risk flagging
result = file_router.route_file('shipments.csv', 'shipments.csv')

if result['success']:
    parse_data = result['data']
    
    # Immediate access to at-risk
    at_risk = parse_data['at_risk_items']
    print(f"Warning: {len(at_risk)} items at risk")
    
    for item in at_risk:
        print(f"  {item['equipment_name']}: {item['buffer_days']} day buffer")
```

## Common Patterns

### Check PDF Type
```python
is_scanned = pdf_parser.is_scanned_pdf('document.pdf')
if is_scanned:
    print("This is a scanned PDF - OCR recommended")
else:
    print("This is a text-based PDF")
```

### Extract Tables from PDF
```python
tables = pdf_parser.extract_tables_pdfplumber('spec.pdf')
for table in tables:
    print(f"Page {table['page']}: {table['row_count']} rows × {table['col_count']} cols")
    print(f"Headers: {table['headers']}")
```

### Detect Schedule Format
```python
format = excel_parser.detect_schedule_format('schedule.xlsx')
# Returns: "P6", "MS_PROJECT", or "GENERIC"

if format == "P6":
    print("This is a Primavera P6 export")
elif format == "MS_PROJECT":
    print("This is a Microsoft Project export")
```

### Find Overdue Tasks
```python
result = file_router.route_file('schedule.xlsx', 'schedule.xlsx')
tasks = result['data']['tasks']

overdue_tasks = [t for t in tasks if t.get('is_overdue')]
for task in overdue_tasks:
    days_late = abs(task['days_remaining'])
    print(f"OVERDUE: {task['task_name']} ({days_late} days late)")
```

### Find At-Risk Shipments
```python
result = file_router.route_file('shipments.csv', 'shipments.csv')
at_risk = result['data']['at_risk_items']

critical = [item for item in at_risk if item['buffer_days'] < 7]
for item in critical:
    print(f"CRITICAL: {item['equipment_name']} - arrives in {item['buffer_days']} days")
```

### Chunk Multiple Documents
```python
documents = ['spec1.pdf', 'spec2.pdf', 'schedule.xlsx']
all_chunks = []

for doc in documents:
    result = file_router.route_file(doc, doc)
    if result['success']:
        if result['file_type'].startswith('pdf'):
            chunks = chunker.chunk_pdf_by_page(
                result['data']['pages'],
                result['metadata']
            )
        else:
            text = str(result['data'])
            chunks = chunker.chunk_text_with_metadata(text, result['metadata'])
        
        all_chunks.extend(chunks)

print(f"Total chunks: {len(all_chunks)}")
```

## Return Value Structure

### file_router.route_file()
```python
{
    'file_type': FileType.PDF_TEXT,
    'filename': 'document.pdf',
    'extraction_method': 'PyMuPDF + pdfplumber',
    'data': {...},  # Parser-specific output
    'success': True,
    'error_message': None,
    'metadata': {...}
}
```

### Chunk Structure
```python
{
    'text': 'The extracted text content...',
    'metadata': {
        'filename': 'spec.pdf',
        'file_type': 'pdf_text',
        'chunk_index': 0,
        'char_start': 0,
        'char_end': 800,
        'chunk_size': 800,
        'page_number': 1  # if from PDF
    }
}
```

### Task Structure (from parse_schedule_excel)
```python
{
    'task_id': 'TASK-A-001',
    'task_name': 'Site Preparation',
    'start_date': '2026-01-15',
    'end_date': '2026-01-30',
    'duration_days': 15,
    'pct_complete': 75,
    'predecessors': None,
    'resources': 3,
    'days_remaining': -5,  # CALCULATED
    'is_overdue': True,    # CALCULATED
    'float_days': 0        # CALCULATED
}
```

### Shipment Structure (from parse_procurement_csv)
```python
{
    'equipment_name': 'Power Distribution Unit',
    'supplier': 'Schneider Electric',
    'po_number': 'PO-2026-001',
    'order_date': '2026-01-01',
    'required_on_site': '2026-02-20',
    'eta': '2026-02-15',
    'status': 'in_transit',
    'cost_usd': 50000,
    'lat': 51.5074,
    'lng': -0.1278,
    'buffer_days': 5,      # CALCULATED
    'at_risk': False       # CALCULATED
}
```

## Error Handling

All functions return consistent error structure:

```python
result = file_router.route_file('missing.pdf', 'missing.pdf')

if not result['success']:
    print(f"Error: {result['error_message']}")
    # error_message contains: reason, suggestion, or technical details
```

Common errors:
- `"File not found: ..."` → Check file path
- `"File exceeds 50MB limit"` → File too large
- `"Invalid Excel: ..."` → Malformed Excel file
- `"This PDF appears to be scanned..."` → May need OCR
- `"Unsupported file type"` → Not in supported formats

## Configuration (from config.py)

```python
import config

# Chunking defaults
chunk_size = config.MAX_CHUNK_SIZE  # 1024
overlap = config.CHUNK_OVERLAP      # 128

# Database
chroma_path = config.CHROMA_DB_PATH # "./chroma_data"

# LLM
model = config.EMBEDDING_MODEL      # "all-MiniLM-L6-v2"
```

## Logging

All operations are logged:

```python
import logging
logger = logging.getLogger(__name__)

# Set level for ingestion logging
logging.getLogger('ingestion').setLevel(logging.DEBUG)

# Example log messages:
# INFO: Detected P6 format for schedule.xlsx
# INFO: Extracted 120 tasks from file
# INFO: PDF 'spec.pdf': avg 2500 chars/page - TEXT-BASED
# WARNING: PDF exceeds 50MB limit: 65.2MB
# ERROR: Error extracting PDF: [details]
```

## File Type Detection

```python
file_type = file_router.detect_file_type('document.ext')

# Returns FileType enum:
# - FileType.PDF_TEXT
# - FileType.PDF_SCANNED
# - FileType.EXCEL
# - FileType.CSV
# - FileType.DWG_DXF
# - FileType.JSON
# - FileType.XML
# - FileType.UNKNOWN
```

## Supported Files

| Type | Extensions | Extraction | Tables | Metadata |
|------|-----------|-----------|--------|----------|
| PDF (text) | .pdf | ✅ | ✅ | ✅ |
| PDF (scanned) | .pdf | ⚠️ | ✅ | ✅ |
| Excel | .xlsx, .xlsm, .xls | ✅ | ✅ | - |
| CSV | .csv | ✅ | - | - |
| CAD | .dwg, .dxf | ✅ | - | - |
| JSON | .json | ✅ | - | - |
| XML | .xml | ✅ | - | - |

## Performance Tips

1. **Large PDFs**: Extract tables separately from text for faster processing
2. **Schedules**: Normalize columns once, cache format detection
3. **Chunking**: Adjust chunk_size based on LLM context window
4. **Caching**: Store parsed results for frequently accessed documents
5. **Streaming**: For >100MB files, implement incremental processing

## Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Inspect extraction result
result = file_router.route_file('document.pdf', 'document.pdf')
print(f"Type: {result['file_type']}")
print(f"Success: {result['success']}")
print(f"Method: {result['extraction_method']}")
print(f"Error: {result['error_message']}")
print(f"Data keys: {result['data'].keys()}")

# Check chunk quality
chunks = chunker.chunk_text_with_metadata(text, {})
for i, chunk in enumerate(chunks):
    print(f"Chunk {i}: {len(chunk['text'])} chars, meta: {chunk['metadata']}")
```

## Integration with Agents

```python
# Example: Feed parsed schedule to Schedule Agent
from agents import schedule_agent

result = file_router.route_file('schedule.xlsx', 'schedule.xlsx')
parsed_schedule = result['data']

# Pass to agent
analysis = schedule_agent.analyze_schedule(parsed_schedule)
```

## One-Liner Examples

```python
# Just extract text
text = file_router.route_file('spec.pdf', 'spec.pdf')['data']['full_text']

# Just get at-risk items
at_risk = file_router.route_file('shipments.csv', 'shipments.csv')['data']['at_risk_items']

# Just get tasks
tasks = file_router.route_file('schedule.xlsx', 'schedule.xlsx')['data']['tasks']

# Just check if scanned
is_scanned = pdf_parser.is_scanned_pdf('document.pdf')

# Just create chunks
chunks = chunker.chunk_text_with_metadata("text here", {'doc': 'example'})
```
