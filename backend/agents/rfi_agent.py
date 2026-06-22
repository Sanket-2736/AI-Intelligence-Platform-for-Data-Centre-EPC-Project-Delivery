"""
RFI Intelligence Agent module.
Handles Request For Information (RFI) processing using RAG.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import logging
from pathlib import Path
import tempfile
import asyncio

from ingestion import pdf_parser
from utils import chunker, cerebras_client
from db.chroma_client import get_chroma_manager, COLLECTION_PROJECT_DOCS
from db.supabase_client import get_supabase_manager
from agents.prompts import RFI_SYSTEM_PROMPT, build_rfi_user_message

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================


class DocumentMetadata(BaseModel):
    """Metadata for a document to ingest."""
    path: str
    filename: str
    doc_type: str
    date: Optional[str] = None
    revision: Optional[str] = "v1"


class IngestionResponse(BaseModel):
    """Response from document ingestion."""
    filename: str
    doc_type: str
    chunks_ingested: int
    pages_processed: int
    tables_found: int
    success: bool
    error: Optional[str] = None


class BatchIngestionResponse(BaseModel):
    """Response from batch ingestion."""
    total_files: int
    total_chunks: int
    failed_files: List[str]
    duration_seconds: float
    success: bool


class Citation(BaseModel):
    """Citation for an answer."""
    source_id: str
    filename: str
    doc_type: str
    date: Optional[str] = None
    revision: Optional[str] = None
    relevance_score: float


class PastRFI(BaseModel):
    """Previous RFI for reference."""
    question: str
    answer: str
    date: str
    relevance_score: Optional[float] = None


class RFIAnswer(BaseModel):
    """Complete RFI answer with citations."""
    question: str
    answer: str
    citations: List[Citation]
    similar_past_rfis: List[PastRFI]
    sources_retrieved: int
    processing_time_ms: int
    answer_confidence: str  # HIGH|MEDIUM|LOW


class QueryRequest(BaseModel):
    """Request model for RFI query."""
    question: str
    doc_type_filter: Optional[str] = None


class DocumentInfo(BaseModel):
    """Information about an ingested document."""
    filename: str
    doc_type: str
    chunks_count: int


# ============================================================================
# CORE AGENT FUNCTIONS
# ============================================================================


def ingest_project_document(
    file_path: str,
    filename: str,
    doc_type: str,
    date: str = "",
    revision: str = "v1"
) -> Dict[str, Any]:
    """
    Synchronous version of document ingestion.
    WARNING: This will block if called from async context. Use ingest_project_document_async instead.
    
    Ingest a single project document into the RAG system.
    
    Extracts text, tables, creates chunks, and stores in ChromaDB.
    
    Args:
        file_path: Path to the document file
        filename: Original filename for metadata
        doc_type: Type of document (spec, rfi, submittal, meeting_minutes, change_order, drawing, standard)
        date: Document date (optional)
        revision: Document revision (default: v1)
        
    Returns:
        {
            'filename': str,
            'doc_type': str,
            'chunks_ingested': int,
            'pages_processed': int,
            'tables_found': int,
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        logger.info(f"[SYNC] Starting synchronous ingestion for {filename} (type: {doc_type})")
        
        chroma = get_chroma_manager()
        logger.info(f"[SYNC] ChromaDB manager initialized")
        
        # Step 1: Extract text and metadata
        logger.info(f"[SYNC] PDF extraction starting...")
        pdf_result = pdf_parser.extract_text_with_ocr_fallback(file_path)
        logger.info(f"[SYNC] PDF extraction complete: success={pdf_result['success']}")
        
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
        logger.info(f"[SYNC] Extracted {pages_processed} pages")
        
        # Step 2: Extract tables
        logger.info(f"[SYNC] Table extraction starting...")
        tables = pdf_parser.extract_tables_pdfplumber(file_path)
        tables_found = len(tables)
        logger.info(f"[SYNC] Table extraction complete: {tables_found} tables found")
        
        # Step 3: Create metadata for chunks
        base_metadata = {
            'doc_type': doc_type,
            'filename': filename,
            'date': date,
            'revision': revision,
            'source_collection': COLLECTION_PROJECT_DOCS
        }
        logger.info(f"[SYNC] Base metadata created")
        
        # Step 4: Chunk by page (preserves page structure for specs)
        logger.info(f"[SYNC] Chunking starting...")
        chunks = chunker.chunk_pdf_by_page(
            pages,
            base_metadata,
            chunk_size=1024,
            overlap=128
        )
        logger.info(f"[SYNC] Chunking complete: {len(chunks)} chunks created")
        
        # Step 5: Create summary chunk
        logger.info(f"[SYNC] Creating summary chunk...")
        summary_chunk = chunker.create_document_summary_chunk(
            pdf_result.get('full_text', ''),
            base_metadata
        )
        logger.info(f"[SYNC] Summary chunk: {summary_chunk is not None}")
        
        if summary_chunk:
            chunks.append(summary_chunk)
            logger.info(f"[SYNC] Summary chunk added, total chunks now: {len(chunks)}")
        
        # Step 6: Ingest into ChromaDB (WARNING: This is blocking)
        logger.info(f"[SYNC] ChromaDB ingestion starting for {len(chunks)} chunks (BLOCKING CALL)...")
        ingest_result = chroma.ingest_chunks(COLLECTION_PROJECT_DOCS, chunks)
        logger.info(f"[SYNC] ChromaDB ingestion complete: {ingest_result}")
        logger.info(
            f"[SYNC] Ingestion complete for {filename}: "
            f"{ingest_result['ingested']} chunks, {pages_processed} pages, {tables_found} tables"
        )
        
        logger.info(f"[SYNC] Returning success response for {filename}")
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
    
    Ingest a single project document into the RAG system.
    
    Extracts text, tables, creates chunks, and stores in ChromaDB.
    
    Args:
        file_path: Path to the document file
        filename: Original filename for metadata
        doc_type: Type of document (spec, rfi, submittal, meeting_minutes, change_order, drawing, standard)
        date: Document date (optional)
        revision: Document revision (default: v1)
        
    Returns:
        {
            'filename': str,
            'doc_type': str,
            'chunks_ingested': int,
            'pages_processed': int,
            'tables_found': int,
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        logger.info(f"[STEP 1] Starting async ingestion for {filename} (type: {doc_type})")
        
        chroma = get_chroma_manager()
        logger.info(f"[STEP 1.5] ChromaDB manager initialized")
        
        # Step 1: Extract text and metadata (CPU-bound but relatively quick)
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
        
        # Step 2: Extract tables
        logger.info(f"[STEP 4] Table extraction starting...")
        tables = pdf_parser.extract_tables_pdfplumber(file_path)
        tables_found = len(tables)
        logger.info(f"[STEP 4] Table extraction complete: {tables_found} tables found")
        
        # Step 3: Create metadata for chunks
        base_metadata = {
            'doc_type': doc_type,
            'filename': filename,
            'date': date,
            'revision': revision,
            'source_collection': COLLECTION_PROJECT_DOCS
        }
        logger.info(f"[STEP 5] Base metadata created")
        
        # Step 4: Chunk by page (preserves page structure for specs)
        logger.info(f"[STEP 6] Chunking starting...")
        chunks = chunker.chunk_pdf_by_page(
            pages,
            base_metadata,
            chunk_size=1024,
            overlap=128
        )
        logger.info(f"[STEP 6] Chunking complete: {len(chunks)} chunks created")
        
        # Step 5: Create summary chunk
        logger.info(f"[STEP 7] Creating summary chunk...")
        summary_chunk = chunker.create_document_summary_chunk(
            pdf_result.get('full_text', ''),
            base_metadata
        )
        logger.info(f"[STEP 7] Summary chunk: {summary_chunk is not None}")
        
        if summary_chunk:
            chunks.append(summary_chunk)
            logger.info(f"[STEP 7b] Summary chunk added, total chunks now: {len(chunks)}")
        
        # Step 6: Ingest into ChromaDB (BLOCKING - run in thread pool)
        logger.info(f"[STEP 8] ChromaDB ingestion starting for {len(chunks)} chunks (running in thread pool)...")
        
        # Run the blocking ingest_chunks operation in a thread pool to avoid blocking event loop
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


def answer_question(
    question: str,
    doc_type_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Answer an RFI question using RAG with Cerebras LLM.
    
    Args:
        question: RFI question
        doc_type_filter: Optional filter (spec, rfi, submittal, etc.)
        
    Returns:
        {
            'question': str,
            'answer': str (with inline citations),
            'citations': List[Citation],
            'similar_past_rfis': List[PastRFI],
            'sources_retrieved': int,
            'processing_time_ms': int,
            'answer_confidence': 'HIGH|MEDIUM|LOW',
            'success': bool,
            'error': Optional[str]
        }
    """
    start_time = time.time()
    
    try:
        chroma = get_chroma_manager()
        db = get_supabase_manager()
        llm = cerebras_client.get_cerebras_client()
        
        logger.info(f"Processing RFI question: {question[:100]}...")
        
        # Step 1: Query ChromaDB for relevant documents
        filters = None
        if doc_type_filter:
            filters = {"doc_type": {"$eq": doc_type_filter}}
        
        search_result = chroma.query(
            collection_name=COLLECTION_PROJECT_DOCS,
            query_text=question,
            n_results=6,
            filters=filters
        )
        
        retrieved_docs = search_result.get('results', [])
        sources_retrieved = len(retrieved_docs)
        
        logger.info(f"Retrieved {sources_retrieved} documents from ChromaDB")
        
        # Step 2: Search for similar past RFIs
        similar_rfis = chroma.search_similar_rfis(question, n_results=3)
        
        # Step 3: Build context string with citations
        context_text = "RELEVANT PROJECT DOCUMENTATION:\n"
        citations = []
        
        for i, doc in enumerate(retrieved_docs):
            source_num = i + 1
            context_text += f"\n[SOURCE {source_num}]: {doc['metadata'].get('filename', 'Unknown')} "
            context_text += f"({doc['metadata'].get('doc_type', 'document')})\n"
            context_text += f"{doc['text'][:300]}...\n"
            
            # Create citation
            citations.append(Citation(
                source_id=doc.get('id', ''),
                filename=doc['metadata'].get('filename', 'Unknown'),
                doc_type=doc['metadata'].get('doc_type', 'document'),
                date=doc['metadata'].get('date'),
                revision=doc['metadata'].get('revision'),
                relevance_score=round(doc.get('relevance_score', 0), 3)
            ))
        
        # Step 4: Add similar RFIs context
        similar_context = ""
        past_rfis = []
        
        if similar_rfis:
            similar_context = "\n\nSIMILAR PREVIOUSLY RESOLVED RFIs:\n"
            for rfi in similar_rfis:
                similar_context += f"- {rfi.get('text', '')[:200]}\n"
                past_rfis.append(PastRFI(
                    question=rfi.get('metadata', {}).get('question', 'N/A'),
                    answer=rfi.get('text', 'N/A'),
                    date=rfi.get('metadata', {}).get('date', 'N/A'),
                    relevance_score=rfi.get('relevance_score')
                ))
        
        # Step 5: Build user message
        user_message = build_rfi_user_message(question, retrieved_docs)
        full_user_message = user_message + context_text + similar_context
        
        # Step 6: Call Cerebras LLM
        answer = llm.call(
            system_prompt=RFI_SYSTEM_PROMPT,
            user_message=full_user_message,
            temperature=0.1,  # Low temperature for accuracy
            max_tokens=2048
        )
        
        # Step 7: Log to Supabase
        db.log_rfi(
            question=question,
            answer=answer,
            citations=[c.filename for c in citations]
        )

        print("=" * 100)
        print("QUESTION:", question)
        print("RETRIEVED RESULTS:", len(retrieved_docs))
        print("CONTEXT:")
        print(context_text[:5000])
        print("=" * 100)
                
        # Determine confidence based on sources
        if sources_retrieved >= 5 and retrieved_docs[0]['relevance_score'] > 0.7:
            confidence = "HIGH"
        elif sources_retrieved >= 3 and retrieved_docs[0]['relevance_score'] > 0.5:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"RFI answered in {processing_time_ms}ms with confidence: {confidence}")
        
        # Convert Pydantic objects to dicts for JSON serialization
        citations_dict = [c.dict() for c in citations]
        past_rfis_dict = [p.dict() for p in past_rfis]
        
        return {
            'question': question,
            'answer': answer,
            'citations': citations_dict,
            'similar_past_rfis': past_rfis_dict,
            'sources_retrieved': sources_retrieved,
            'processing_time_ms': processing_time_ms,
            'answer_confidence': confidence,
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Error answering question: {str(e)}"
        logger.error(error_msg, exc_info=True)
        processing_time_ms = int((time.time() - start_time) * 1000)
        return {
            'question': question,
            'answer': '',
            'citations': [],
            'similar_past_rfis': [],
            'sources_retrieved': 0,
            'processing_time_ms': processing_time_ms,
            'answer_confidence': 'LOW',
            'success': False,
            'error': error_msg
        }


def get_document_list() -> List[Dict[str, Any]]:
    """
    Get list of all ingested documents.
    
    Returns:
        List of {filename, doc_type, chunks_count}
    """
    try:
        chroma = get_chroma_manager()
        
        # Get collection stats
        stats = chroma.get_collection_stats(COLLECTION_PROJECT_DOCS)
        
        # In a real implementation, we'd track unique documents
        # For now, return aggregated stats
        return [{
            'filename': 'All ingested documents',
            'doc_type': 'Mixed',
            'chunks_count': stats['document_count'],
            'collection': COLLECTION_PROJECT_DOCS
        }]
        
    except Exception as e:
        logger.error(f"Error getting document list: {str(e)}")
        return []


def clear_project_documents() -> Dict[str, Any]:
    """
    Clear and reset the project documents collection.
    
    Used for fresh project start or cleanup.
    
    Returns:
        {
            'success': bool,
            'message': str,
            'error': Optional[str]
        }
    """
    try:
        chroma = get_chroma_manager()
        
        # Delete collection
        success = chroma.delete_collection(COLLECTION_PROJECT_DOCS)
        
        if success:
            logger.info("Project documents collection cleared")
            return {
                'success': True,
                'message': f"Cleared {COLLECTION_PROJECT_DOCS} collection",
                'error': None
            }
        else:
            return {
                'success': False,
                'message': 'Failed to delete collection',
                'error': 'Unknown error'
            }
            
    except Exception as e:
        error_msg = f"Error clearing documents: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'message': 'Failed to clear collection',
            'error': error_msg
        }


# ============================================================================
# FASTAPI ENDPOINTS
# ============================================================================


@router.post("/ingest/single", response_model=IngestionResponse, tags=["RFI Agent - Ingestion"])
async def ingest_single_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    date: str = Form(default=""),
    revision: str = Form(default="v1")
) -> IngestionResponse:
    """
    Ingest a single project document.
    
    Args:
        file: PDF document file
        doc_type: Document type (spec, rfi, submittal, meeting_minutes, change_order, drawing, standard)
        date: Document date (optional)
        revision: Document revision (default: v1)
        
    Returns:
        Ingestion result with chunk and page counts
    """
    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Ingest document
            result = ingest_project_document(
                file_path=tmp_path,
                filename=file.filename,
                doc_type=doc_type,
                date=date,
                revision=revision
            )
            
            return IngestionResponse(**result)
            
        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)
            
    except Exception as e:
        logger.error(f"Error in ingest endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest/batch", response_model=BatchIngestionResponse, tags=["RFI Agent - Ingestion"])
async def ingest_batch_documents(
    files: List[UploadFile] = File(...),
    doc_types: List[str] = Form(default=[]),
    dates: List[str] = Form(default=[]),
    revisions: List[str] = Form(default=[])
) -> BatchIngestionResponse:
    """
    Batch ingest multiple documents.
    
    Args:
        files: List of PDF files
        doc_types: Optional list of document types (default: "document" for each file)
        dates: Optional list of dates
        revisions: Optional list of revisions
        
    Returns:
        Batch ingestion result
    """
    try:
        logger.info(f"[ENDPOINT] POST /ingest/batch called with {len(files)} files")
        logger.debug(f"[ENDPOINT] Files: {[f.filename for f in files]}")
        logger.debug(f"[ENDPOINT] Doc types provided: {len(doc_types)}, Values: {doc_types}")
        
        # Use default doc_type if not provided
        if not doc_types or len(doc_types) == 0:
            logger.info(f"[ENDPOINT] No doc_types provided, using default 'document' for {len(files)} files")
            doc_types = ["document"] * len(files)
        
        if len(files) != len(doc_types):
            error_msg = f"Files ({len(files)}) and doc_types ({len(doc_types)}) length mismatch"
            logger.error(f"[ENDPOINT] {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        file_list = []
        temp_files = []
        
        try:
            # Save all files to temp location
            logger.info(f"[ENDPOINT] Saving {len(files)} files to temp location")
            for i, file in enumerate(files):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    content = await file.read()
                    tmp.write(content)
                    temp_files.append(tmp.name)
                    logger.debug(f"[ENDPOINT] File {i+1}: {file.filename} → {tmp.name}")
                    
                    file_list.append({
                        'path': tmp.name,
                        'filename': file.filename,
                        'doc_type': doc_types[i],
                        'date': dates[i] if i < len(dates) else '',
                        'revision': revisions[i] if i < len(revisions) else 'v1'
                    })

            logger.info(f"[ENDPOINT] Prepared {len(file_list)} files for ingestion")
            
            # Ingest batch using async function
            logger.info(f"[ENDPOINT] Calling ingest_multiple_documents_async")
            result = await ingest_multiple_documents_async(file_list)
            logger.info(f"[ENDPOINT] ingest_multiple_documents_async returned: {result}")
            
            logger.info(f"[ENDPOINT] Creating BatchIngestionResponse")
            response = BatchIngestionResponse(**result)
            logger.info(f"[ENDPOINT] BatchIngestionResponse created successfully")
            logger.info(f"[ENDPOINT] Returning response")
            
            return response
            
        finally:
            # Clean up temp files
            logger.info(f"[ENDPOINT] Cleaning up {len(temp_files)} temp files")
            for tmp_path in temp_files:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                    logger.debug(f"[ENDPOINT] Deleted temp file: {tmp_path}")
                except Exception as e:
                    logger.warning(f"[ENDPOINT] Failed to delete temp file {tmp_path}: {e}")
            logger.info(f"[ENDPOINT] Cleanup complete")
                
    except HTTPException as e:
        logger.error(f"[ENDPOINT] HTTPException: {e.detail}")
        raise
    except Exception as e:
        logger.exception(f"[ENDPOINT] Exception in batch ingest endpoint")
        logger.error(f"[ENDPOINT] Exception type: {type(e).__name__}")
        logger.error(f"[ENDPOINT] Exception message: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/query", response_model=RFIAnswer, tags=["RFI Agent - Query"])
async def query_rfi(request: QueryRequest) -> RFIAnswer:
    """
    Answer an RFI question using RAG with Cerebras LLM.
    
    Args:
        request: Query request containing question and optional doc_type_filter
        
    Returns:
        Complete answer with citations and similar past RFIs
    """
    try:
        # Validate question
        if not request.question or not request.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        logger.info(f"Received RFI query: {request.question[:100]}...")
        
        result = answer_question(request.question, request.doc_type_filter)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error'))
        
        return RFIAnswer(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents", response_model=List[DocumentInfo], tags=["RFI Agent - Documents"])
async def list_documents() -> List[DocumentInfo]:
    """
    Get list of all ingested project documents.
    
    Returns:
        List of document information
    """
    try:
        logger.info("GET /documents endpoint called")
        docs = get_document_list()
        logger.info(f"Retrieved {len(docs)} documents from database")
        logger.debug(f"Document list before validation: {docs}")
        
        validated_docs = [DocumentInfo(**doc) for doc in docs]
        logger.info(f"Successfully validated and returned {len(validated_docs)} documents")
        return validated_docs
        
    except Exception as e:
        logger.exception(f"Error in documents endpoint: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", tags=["RFI Agent - History"])
async def get_rfi_history(limit: int = 20):
    """
    Get recent RFI history from database.
    
    Args:
        limit: Number of recent RFIs to return
        
    Returns:
        List of recent RFI Q&A pairs
    """
    try:
        db = get_supabase_manager()
        rfis = db.get_recent_rfis(limit=limit)
        
        return {
            'count': len(rfis),
            'rfis': rfis
        }
        
    except Exception as e:
        logger.error(f"Error in history endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reset", tags=["RFI Agent - Admin"])
async def reset_project():
    """
    Reset and clear all project documents.
    
    WARNING: This clears all ingested documents.
    
    Returns:
        Confirmation of reset
    """
    try:
        result = clear_project_documents()
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error'))
        
        return {
            'success': True,
            'message': result.get('message')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reset endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
