# Data Ingestion Layer - Complete Documentation

## Overview

The Data Ingestion Layer is the foundation of the EPC Intelligence Platform. It handles extraction, normalization, and preparation of all incoming documents for processing by the five specialized agents.

**Key responsibility:** Convert raw files into standardized, structured data that agents can reliably analyze.

## Architecture

```
Input Files (PDF, Excel, CSV, DWG, JSON, XML)
           ↓
    File Type Detection (magic bytes + extension)
           ↓
    Format-Specific Extractors
    ├── PDF Parser (PyMuPDF + pdfplumber)
    ├── Excel Parser (openpyxl + pandas)
    ├── CSV Parser (pandas)
    ├── CAD Parser (ezdxf)
    ├── JSON/XML Parsers
           ↓
    Data Normalization
    (format detection, column mapping, field standardization)
           ↓
    Text Chunking (sliding window with overlap)
           ↓
    Vector Embedding Ready
    (for ChromaDB and Cerebras context)
```

## Module Breakdown

### 1. pdf_parser.py

**Purpose:** Extract text, metadata, and tables from PDF documents.

#### Key Functions

**`extract_text_pymupdf(file_path: str) -> Dict`**
- Extracts text from PDF using PyMuPDF (fitz)
- Handles encrypted/corrupt PDFs gracefully
- Returns per-page statistics: character count, bounding boxes
- Concatenates full document text for analysis

**Input:** PDF file path
**Output:**
```python
{
    'filename': 'spec.pdf',
    'total_pages': 25,
    'pages': [
        {'page': 1, 'text': '...', 'char_count': 2500, 'bbox': (0,0,595,842)},
        ...
    ],
    'full_text': '...',
    'success': True,
    'error': None
}
```

**`is_scanned_pdf(file_path: str) -> bool`**
- Detects if PDF is image-based (scanned) vs text-based
- Heuristic: avg chars per page < 100 = scanned
- Important for determining if OCR fallback needed

**Use case:** Specification documents are often scanned PDFs.

**`extract_tables_pdfplumber(file_path: str) -> List[Dict]`**
- Extracts all tables from PDF
- Converts cells to strings, handles None values
- Preserves page numbers and table indexes

**Output:**
```python
[
    {
        'page': 1,
        'table_index': 0,
        'headers': ['Requirement', 'Value', 'Unit'],
        'data': [['Temperature Range', '-10 to 40', 'C'], ...],
        'row_count': 5,
        'col_count': 3
    }
]
```

**`extract_pdf_metadata(file_path: str) -> Dict`**
- Extracts: title, author, creation_date, modification_date, producer, creator
- Useful for document tracking and versioning

**`extract_text_with_ocr_fallback(file_path: str) -> Dict`**
- Main entry point for PDF extraction
- Wraps PyMuPDF extraction
- Adds `ocr_warning` flag for scanned documents
- Note: Actual OCR via pytesseract would be added separately

### 2. excel_parser.py

**Purpose:** Parse project schedules and procurement data from Excel/CSV.

#### Key Functions

**`parse_schedule_excel(file_path: str) -> Dict`**
- Loads Excel with openpyxl (data_only=True for values)
- Auto-detects header row
- Normalizes dates to ISO strings
- **Calculates derived fields:**
  - `days_remaining`: (Finish - today)
  - `is_overdue`: today > Finish AND % Complete < 100
  - `float_days`: (Finish - Baseline Finish)

**Output:**
```python
{
    'total_tasks': 120,
    'columns': ['Task ID', 'Task Name', 'Start', 'Finish', ...],
    'tasks': [
        {
            'Task ID': 'TASK-A-001',
            'Task Name': 'Site Prep',
            'Start': '2026-01-15',
            'Finish': '2026-01-30',
            'Duration': 15,
            '% Complete': 75,
            'days_remaining': -5,  # OVERDUE
            'is_overdue': True,
            'float_days': 0
        },
        ...
    ],
    'overdue_count': 3,
    'at_risk_count': 8,
    'summary_stats': {
        'pct_complete_avg': 62.5,
        'tasks_completed': 45,
        'tasks_in_progress': 50,
        'tasks_not_started': 25
    },
    'success': True
}
```

**`detect_schedule_format(file_path: str) -> str`**
- Returns: "P6" | "MS_PROJECT" | "GENERIC"
- P6 indicators: "Activity ID", "Activity Name", "Baseline Start/Finish"
- MS Project indicators: "Task Name", "Duration", "Predecessors"

**Use case:** Different tools export schedules with different column names. Detection enables proper normalization.

**`normalize_task_columns(tasks: List[Dict], format: str) -> List[Dict]`**
- Maps format-specific column names to standard names
- Standard names: `task_id, task_name, start_date, end_date, duration_days, pct_complete, predecessors, resources`
- All original fields preserved + normalized versions added

**Output:** Tasks ready for Cerebras analysis with consistent field names.

**`parse_procurement_csv(file_path: str) -> Dict`**
- Parses CSV with columns: equipment_name, supplier, eta, required_on_site, status, etc.
- **Calculates:**
  - `buffer_days`: (required_on_site - eta)
  - `at_risk`: buffer_days < 14 OR status == "DELAYED"

**Output:**
```python
{
    'total_items': 20,
    'at_risk_count': 3,
    'items': [...],
    'at_risk_items': [
        {
            'Equipment': 'Power Distribution Unit',
            'Supplier': 'Schneider Electric',
            'ETA': '2026-02-15',
            'Required On Site': '2026-02-20',
            'buffer_days': 5,
            'at_risk': True,
            'status': 'DELAYED'
        },
        ...
    ],
    'success': True
}
```

### 3. file_router.py

**Purpose:** Master routing logic for all file types.

#### FileType Enum
```python
PDF_TEXT      # Text-based PDF
PDF_SCANNED   # Image-based PDF (scanned)
EXCEL         # Excel schedules
CSV           # Procurement/shipment data
DWG_DXF       # CAD drawings
JSON          # Project data (JSON format)
XML           # Configuration files (XML format)
UNKNOWN       # Unsupported type
```

#### Key Functions

**`detect_file_type(file_path: str) -> FileType`**
- Detects by extension AND magic bytes (first 8 bytes)
- Magic bytes:
  - PDF: `%PDF`
  - Excel: `PK` (zip header) or `\xd0\xcf` (OLE)
  - All others: extension fallback

**`route_file(file_path: str, original_filename: str) -> Dict`**
- Master router: detects type, calls appropriate parser
- Returns unified output structure

**Output:**
```python
{
    'file_type': 'pdf_text',
    'filename': 'specification.pdf',
    'extraction_method': 'PyMuPDF + pdfplumber',
    'data': {
        'filename': '...',
        'total_pages': 25,
        'pages': [...],
        'full_text': '...',
        'success': True
    },
    'success': True,
    'error_message': None,
    'metadata': {
        'title': 'Data Centre Specification',
        'author': 'Engineering Team',
        'creation_date': '2026-01-01',
        'num_pages': 25
    }
}
```

**`validate_file_size(file_path: str, max_mb: int = 50) -> bool`**
- Prevents processing of extremely large files
- Default: 50MB limit (configurable)

**`_extract_cad_file(file_path: str) -> Dict`**
- Uses ezdxf to extract DWG/DXF entities
- Returns: list of entities with type, layer, color
- Useful for facility layouts

**`_extract_json_file(file_path: str) -> Dict`**
- Parses JSON and returns parsed data
- Error handling for malformed JSON

**`_extract_xml_file(file_path: str) -> Dict`**
- Parses XML and returns root tag, children count, text content
- First 1000 chars of content returned

### 4. chunker.py (in utils/)

**Purpose:** Convert extracted text into embedding-ready chunks.

#### Key Functions

**`chunk_text_with_metadata(text, metadata, chunk_size=800, overlap=100) -> List[Dict]`**
- Sliding window chunking approach
- Each chunk includes original metadata + chunk-specific metadata
- Skips chunks < 50 characters

**Output:**
```python
[
    {
        'text': 'The specification requires that...',
        'metadata': {
            'filename': 'spec.pdf',
            'file_type': 'pdf_text',
            'chunk_index': 0,
            'char_start': 0,
            'char_end': 800,
            'chunk_size': 800
        }
    },
    {
        'text': 'that temperature control must maintain...',  # overlaps with previous
        'metadata': {
            'filename': 'spec.pdf',
            'file_type': 'pdf_text',
            'chunk_index': 1,
            'char_start': 700,  # 100 char overlap
            'char_end': 1500,
            'chunk_size': 800
        }
    }
]
```

**`chunk_pdf_by_page(pages, metadata) -> List[Dict]`**
- Chunks by page boundary first, then by size within page
- Preserves page_number in metadata
- Better for specs where page structure matters

**Use case:** Specification document with "Section 1 on Page 1", "Section 2 on Page 2", etc.

**`create_document_summary_chunk(full_text, metadata) -> Optional[Dict]`**
- Creates single overview chunk from document
- Uses: first 500 chars + last 200 chars
- Tagged with `chunk_type: 'summary'`

**Use case:** Quick document-level retrieval without full content.

## Integration Patterns

### Pattern 1: PDF Specification Ingestion

```python
from ingestion import file_router
from utils import chunker

# Route file
result = file_router.route_file('spec.pdf', 'spec.pdf')

if result['success']:
    # Extract data
    pages = result['data'].get('pages', [])
    
    # Chunk by page for specs (page structure meaningful)
    chunks = chunker.chunk_pdf_by_page(
        pages,
        {'document_type': 'specification', 'source': 'pdf'},
        chunk_size=1024,
        overlap=128
    )
    
    # Store chunks in ChromaDB
    # Each chunk ready for embedding
```

### Pattern 2: Schedule Analysis

```python
from ingestion import file_router, excel_parser

# Route file
result = file_router.route_file('schedule.xlsx', 'schedule.xlsx')

if result['success']:
    parse_result = result['data']
    detected_format = result['metadata']['detected_format']
    
    # Normalize column names
    normalized_tasks = excel_parser.normalize_task_columns(
        parse_result['tasks'],
        detected_format
    )
    
    # Analyze for risks
    overdue = [t for t in normalized_tasks if t.get('is_overdue')]
    at_risk = [t for t in normalized_tasks if t.get('days_remaining', 0) < 0]
    
    # Create text for LLM analysis
    tasks_text = '\n'.join([
        f"{t['task_id']}: {t['task_name']} - {t['pct_complete']}% complete"
        for t in normalized_tasks
    ])
    
    # Chunk for context
    chunks = chunker.chunk_text_with_metadata(
        tasks_text,
        {'document_type': 'schedule', 'format': detected_format},
        chunk_size=2048  # Larger for schedules
    )
```

### Pattern 3: Procurement Risk Detection

```python
from ingestion import file_router

# Route file
result = file_router.route_file('shipments.csv', 'shipments.csv')

if result['success']:
    parse_result = result['data']
    
    # Immediate access to at-risk items
    at_risk_items = parse_result['at_risk_items']
    
    # Flag priority items
    for item in at_risk_items:
        priority = 'CRITICAL' if item['buffer_days'] < 7 else 'HIGH'
        logger.warning(f"{priority}: {item['Equipment']} - Buffer: {item['buffer_days']} days")
```

## Data Flow to Agents

```
Ingestion Layer Output (Chunks + Metadata)
                ↓
        ChromaDB Vector Store
        (embedding + storage)
                ↓
        Agent Query → Semantic Search
        (retrieve relevant chunks)
                ↓
        Cerebras LLM Context
        (input chunks as RAG context)
                ↓
        Agent Analysis
        (structured JSON output)
```

## Error Handling

All functions include comprehensive error handling:

1. **File Not Found** → Returns `success: False` with error message
2. **Corrupt/Encrypted PDF** → Returns `success: False`, suggests manual review
3. **Malformed Excel** → Logs warning, returns partial results if possible
4. **CSV Parsing Error** → Returns `success: False` with row number
5. **Unsupported File Type** → Returns `success: False`, suggests supported formats

**Pattern:** All functions return consistent structure with `success` boolean and `error` message.

## Performance Considerations

**PDF Processing:**
- Large PDFs (>50 pages): Extract text only, skip tables initially
- Tables: Extracted separately via pdfplumber (faster than full page analysis)
- Scanned detection: Heuristic check, minimal overhead

**Schedule Processing:**
- Excel parsing: ~100ms per 1000 rows
- Format detection: ~10ms
- Column normalization: ~5ms per task
- Derived field calculation: ~1ms per task

**Chunking:**
- Text chunking: ~1ms per 1000 characters
- PDF by-page: ~5ms per page
- Summary chunk: Negligible

**Optimization:** For large documents (>10MB), implement streaming/batch processing.

## Testing

Example test patterns:

```python
# Test PDF extraction
def test_pdf_extraction():
    result = pdf_parser.extract_text_pymupdf('test_spec.pdf')
    assert result['success']
    assert result['total_pages'] > 0
    assert len(result['full_text']) > 0

# Test schedule parsing
def test_schedule_parsing():
    result = excel_parser.parse_schedule_excel('test_schedule.xlsx')
    assert result['success']
    assert result['total_tasks'] > 0
    assert all('task_id' in t for t in result['tasks'])

# Test chunking
def test_chunking():
    text = "Lorem ipsum " * 100
    chunks = chunker.chunk_text_with_metadata(text, {}, chunk_size=100)
    assert len(chunks) > 1
    assert chunks[0]['metadata']['char_start'] == 0
```

## Future Enhancements

1. **OCR Support:** Implement pytesseract for scanned PDFs
2. **Streaming:** Handle large files with streaming parsers
3. **Caching:** Cache extracted metadata for frequently accessed documents
4. **Custom Formats:** Add parsers for industry-specific formats
5. **Quality Scoring:** Confidence scores for extracted data
6. **Deduplication:** Detect and flag duplicate documents

## Production Deployment

**Requirements:**
- Python 3.11+
- Dependencies: pdfplumber, openpyxl, pandas, ezdxf, fitz (PyMuPDF)
- File storage: Local disk or cloud storage (S3/GCS)
- Logging: Structured JSON logs to monitoring system

**Monitoring:**
- Track extraction success rates by file type
- Monitor processing time per file
- Alert on repeated format detection failures
- Log all errors for debugging
