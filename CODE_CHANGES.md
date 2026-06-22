# Exact Code Changes - Copy/Paste Ready

## FILE 1: /backend/agents/rfi_agent.py

### Change 1: Add Import (Line 16)

```python
# ADD THIS LINE:
import asyncio
```

**Location**: After other imports, before router declaration

---

### Change 2: Key Pattern Used Throughout

Any blocking ChromaDB operation should use this pattern:

```python
# FOR ANY BLOCKING OPERATION:
def _blocking_operation():
    return chroma.ingest_chunks(...)  # or any blocking call

result = await asyncio.to_thread(_blocking_operation)
```

---

### Change 3: New Async Function (Add After Existing ingest_project_document)

```python
async def ingest_project_document_async(
    file_path: str,
    filename: str,
    doc_type: str,
    date: str = "",
    revision: str = "v1"
) -> Dict[str, Any]:
    """
    Async version of ingest_project_document.
    Offloads blocking ChromaDB operations to thread pool.
    """
    try:
        logger.info(f"[STEP 1] Starting async ingestion for {filename} (type: {doc_type})")
        
        chroma = get_chroma_manager()
        logger.info(f"[STEP 1.5] ChromaDB manager initialized")
        
        # PDF extraction
        logger.info(f"[STEP 2] PDF extraction starting...")
        pdf_result = pdf_parser.extract_text_with_ocr_fallback(file_path)
        logger.info(f"[STEP 2] PDF extraction complete: success={pdf_result['success']}")
        
        if not pdf_result['success']:
            error_msg = f"PDF extraction failed: {pdf_result.get('error')}"
            logger.error(error_msg)
            return {
                'filename': filename,
                'doc_type': doc_type,
                'chunks_ingested': 0,
                'pages_processed': 0,
                'tables_found': 0,
                'success': False,
                'error': error_msg
            }
        
        pages = pdf_result.get('pages', [])
        pages_processed = len(pages)
        logger.info(f"[STEP 3] Extracted {pages_processed} pages")
        
        # Tables
        logger.info(f"[STEP 4] Table extraction starting...")
        tables = pdf_parser.extract_tables_pdfplumber(file_path)
        tables_found = len(tables)
        logger.info(f"[STEP 4] Table extraction complete: {tables_found} tables found")
        
        # Metadata
        base_metadata = {
            'doc_type': doc_type,
            'filename': filename,
            'date': date,
            'revision': revision,
            'source_collection': COLLECTION_PROJECT_DOCS
        }
        logger.info(f"[STEP 5] Base metadata created")
        
        # Chunking
        logger.info(f"[STEP 6] Chunking starting...")
        chunks = chunker.chunk_pdf_by_page(
            pages,
            base_metadata,
            chunk_size=1024,
            overlap=128
        )
        logger.info(f"[STEP 6] Chunking complete: {len(chunks)} chunks created")
        
        # Summary
        logger.info(f"[STEP 7] Creating summary chunk...")
        summary_chunk = chunker.create_document_summary_chunk(
            pdf_result.get('full_text', ''),
            base_metadata
        )
        logger.info(f"[STEP 7] Summary chunk: {summary_chunk is not None}")
        
        if summary_chunk:
            chunks.append(summary_chunk)
            logger.info(f"[STEP 7b] Summary chunk added, total chunks now: {len(chunks)}")
        
        # 🔴 KEY FIX: Ingest in thread pool to avoid blocking event loop
        logger.info(f"[STEP 8] ChromaDB ingestion starting for {len(chunks)} chunks (running in thread pool)...")
        
        def _blocking_ingest():
            return chroma.ingest_chunks(COLLECTION_PROJECT_DOCS, chunks)
        
        ingest_result = await asyncio.to_thread(_blocking_ingest)
        logger.info(f"[STEP 8] ChromaDB ingestion complete: {ingest_result}")
        logger.info(
            f"[STEP 9] Ingestion complete for {filename}: "
            f"{ingest_result['ingested']} chunks, {pages_processed} pages, {tables_found} tables"
        )
        
        logger.info(f"[STEP 10] Returning success response for {filename}")
        return {
            'filename': filename,
            'doc_type': doc_type,
            'chunks_ingested': ingest_result['ingested'],
            'pages_processed': pages_processed,
            'tables_found': tables_found,
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Error ingesting document: {str(e)}"
        logger.exception(error_msg)
        logger.error(f"Exception traceback: {type(e).__name__}")
        return {
            'filename': filename,
            'doc_type': doc_type,
            'chunks_ingested': 0,
            'pages_processed': 0,
            'tables_found': 0,
            'success': False,
            'error': error_msg
        }
```

---

### Change 4: New Async Batch Function (Add After ingest_project_document_async)

```python
async def ingest_multiple_documents_async(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Async batch ingest multiple documents.
    
    Args:
        files: List of {path, filename, doc_type, date, revision}
        
    Returns:
        {
            'total_files': int,
            'total_chunks': int,
            'failed_files': List[str],
            'duration_seconds': float,
            'success': bool
        }
    """
    start_time = time.time()
    total_chunks = 0
    failed_files = []
    
    try:
        logger.info(f"[BATCH] Starting async batch ingestion of {len(files)} documents")
        
        for idx, file_info in enumerate(files):
            try:
                logger.info(f"[BATCH {idx+1}/{len(files)}] Processing {file_info['filename']}")
                result = await ingest_project_document_async(
                    file_path=file_info['path'],
                    filename=file_info['filename'],
                    doc_type=file_info['doc_type'],
                    date=file_info.get('date', ''),
                    revision=file_info.get('revision', 'v1')
                )
                logger.info(f"[BATCH {idx+1}/{len(files)}] Result: {result}")
                
                if result['success']:
                    total_chunks += result['chunks_ingested']
                    logger.info(f"[BATCH {idx+1}/{len(files)}] Success! Total chunks so far: {total_chunks}")
                else:
                    failed_files.append(file_info['filename'])
                    logger.error(f"[BATCH {idx+1}/{len(files)}] Failed: {result.get('error')}")
                    
            except Exception as e:
                logger.exception(f"[BATCH {idx+1}/{len(files)}] Exception in file processing")
                logger.warning(f"Failed to ingest {file_info['filename']}: {str(e)}")
                failed_files.append(file_info['filename'])
        
        duration = time.time() - start_time
        
        logger.info(
            f"[BATCH COMPLETE] Async batch ingestion complete: {len(files) - len(failed_files)} successful, "
            f"{len(failed_files)} failed, {total_chunks} chunks ingested in {duration:.1f}s"
        )
        
        return {
            'total_files': len(files),
            'total_chunks': total_chunks,
            'failed_files': failed_files,
            'duration_seconds': duration,
            'success': len(failed_files) == 0
        }
        
    except Exception as e:
        error_msg = f"Error in async batch ingestion: {str(e)}"
        logger.exception(error_msg)
        return {
            'total_files': len(files),
            'total_chunks': 0,
            'failed_files': [f['filename'] for f in files],
            'duration_seconds': time.time() - start_time,
            'success': False
        }
```

---

### Change 5: Update Endpoint (Replace OLD ingest_batch_documents)

**BEFORE**:
```python
result = ingest_multiple_documents(file_list)
logger.info(f"Batch ingestion successful: {result}")
```

**AFTER**:
```python
result = await ingest_multiple_documents_async(file_list)
logger.info(f"[ENDPOINT] ingest_multiple_documents_async returned: {result}")
```

---

## FILE 2: /backend/db/chroma_client.py

### Add Logging to ingest_chunks() Method

**Add at the very beginning of the try block**:

```python
logger.info(f"[CHROMA] ingest_chunks called: collection={collection_name}, chunks={len(chunks)}")

if not chunks:
    logger.warning(f"[CHROMA] No chunks provided for {collection_name}")
    return { ... }

logger.info(f"[CHROMA] Getting collection: {collection_name}")
collection = self.get_collection(collection_name)
logger.info(f"[CHROMA] Collection retrieved successfully")

logger.info(f"[CHROMA] Preparing {len(chunks)} chunks for batch insert")
```

**In the loop where chunks are prepared**:

```python
for i, chunk in enumerate(chunks):
    try:
        # ... existing code ...
    except Exception as e:
        logger.warning(f"[CHROMA] Error processing chunk {i}: {str(e)}")
        skipped += 1
        continue

logger.info(f"[CHROMA] Prepared {len(ids)} documents for upsert (skipped {skipped})")
```

**In the upsert loop**:

```python
for batch_num, i in enumerate(range(0, len(ids), batch_size)):
    batch_ids = ids[i:i+batch_size]
    batch_texts = texts[i:i+batch_size]
    batch_metadatas = metadatas[i:i+batch_size]
    
    try:
        logger.info(f"[CHROMA] Upserting batch {batch_num + 1} ({len(batch_ids)} documents)...")
        collection.upsert(
            ids=batch_ids,
            documents=batch_texts,
            metadatas=batch_metadatas
        )
        ingested += len(batch_ids)
        logger.info(f"[CHROMA] Batch {batch_num + 1} upserted successfully. Total ingested so far: {ingested}")
        
    except Exception as e:
        logger.error(f"[CHROMA] Error upserting batch {batch_num + 1}: {str(e)}")
        logger.exception(f"[CHROMA] Batch upsert exception traceback")
        skipped += len(batch_ids)
```

**At the end**:

```python
logger.info(
    f"[CHROMA] Ingestion complete for {collection_name}: "
    f"{ingested} ingested, {skipped} skipped in {duration:.2f}s"
)
```

---

## Summary of Changes

| File | Type | Lines Added | Breaking |
|------|------|-------------|----------|
| rfi_agent.py | Add import + 2 async functions | ~150 | No |
| chroma_client.py | Logging only | ~40 | No |
| **Total** | | **~190** | **No** |

---

## Verification Commands

```bash
# Compile check
python -m py_compile backend/agents/rfi_agent.py
python -m py_compile backend/db/chroma_client.py

# Should print no errors
```

---

## Testing Sequence

1. Upload PDF file
2. Watch backend logs for `[ENDPOINT]` and `[STEP N]` markers
3. Should see `[ENDPOINT] Returning response` within 10 seconds
4. Frontend spinner should stop
5. Check ChromaDB: `stats['document_count']` should be > 0

---

**ALL CHANGES ARE BACKWARD COMPATIBLE AND NON-BREAKING** ✅
