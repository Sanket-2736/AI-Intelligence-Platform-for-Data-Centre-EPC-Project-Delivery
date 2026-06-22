"""
RFI Intelligence Agent module.
Handles Request For Information (RFI) processing using RAG (Retrieval-Augmented Generation).
Ingests project documents, performs semantic search, and generates answers using Cerebras LLM.
Production-quality with comprehensive error handling and logging.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import logging
from pathlib import Path
import tempfile

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
        logger.info(f"Starting ingestion for {filename} (type: {doc_type})")
        
        chroma = get_chroma_manager()
        
        # Step 1: Extract text and metadata
        pdf_result = pdf_parser.extract_text_with_ocr_fallback(file_path)
        
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
        
        # Step 2: Extract tables
        tables = pdf_parser.extract_tables_pdfplumber(file_path)
        tables_found = len(tables)
        
        # Step 3: Create metadata for chunks
        base_metadata = {
            'doc_type': doc_type,
            'filename': filename,
            'date': date,
            'revision': revision,
            'source_collection': COLLECTION_PROJECT_DOCS
        }
        
        # Step 4: Chunk by page (preserves page structure for specs)
        chunks = chunker.chunk_pdf_by_page(
            pages,
            base_metadata,
            chunk_size=1024,
            overlap=128
        )
        
        # Step 5: Create summary chunk
        summary_chunk = chunker.create_document_summary_chunk(
            pdf_result.get('full_text', ''),
            base_metadata
        )
        
        if summary_chunk:
            chunks.append(summary_chunk)
        
        # Step 6: Ingest into ChromaDB
        ingest_result = chroma.ingest_chunks(COLLECTION_PROJECT_DOCS, chunks)
        
        logger.info(
            f"Ingestion complete for {filename}: "
            f"{ingest_result['ingested']} chunks, {pages_processed} pages, {tables_found} tables"
        )
        
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


def ingest_multiple_documents(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Batch ingest multiple documents.
    
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
        logger.info(f"Starting batch ingestion of {len(files)} documents")
        
        for file_info in files:
            try:
                result = ingest_project_document(
                    file_path=file_info['path'],
                    filename=file_info['filename'],
                    doc_type=file_info['doc_type'],
                    date=file_info.get('date', ''),
                    revision=file_info.get('revision', 'v1')
                )
                
                if result['success']:
                    total_chunks += result['chunks_ingested']
                else:
                    failed_files.append(file_info['filename'])
                    
            except Exception as e:
                logger.warning(f"Failed to ingest {file_info['filename']}: {str(e)}")
                failed_files.append(file_info['filename'])
        
        duration = time.time() - start_time
        
        logger.info(
            f"Batch ingestion complete: {len(files) - len(failed_files)} successful, "
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
        error_msg = f"Error in batch ingestion: {str(e)}"
        logger.error(error_msg)
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
        
        # Determine confidence based on sources
        if sources_retrieved >= 5 and retrieved_docs[0]['relevance_score'] > 0.7:
            confidence = "HIGH"
        elif sources_retrieved >= 3 and retrieved_docs[0]['relevance_score'] > 0.5:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"RFI answered in {processing_time_ms:.0f}ms with confidence: {confidence}")
        
        return {
            'question': question,
            'answer': answer,
            'citations': citations,
            'similar_past_rfis': past_rfis,
            'sources_retrieved': sources_retrieved,
            'processing_time_ms': round(processing_time_ms, 0),
            'answer_confidence': confidence,
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Error answering question: {str(e)}"
        logger.error(error_msg)
        return {
            'question': question,
            'answer': '',
            'citations': [],
            'similar_past_rfis': [],
            'sources_retrieved': 0,
            'processing_time_ms': round((time.time() - start_time) * 1000, 0),
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
        logger.info(f"POST /ingest/batch called with {len(files)} files")
        logger.debug(f"Files: {[f.filename for f in files]}")
        logger.debug(f"Doc types provided: {len(doc_types)}, Values: {doc_types}")
        
        # Use default doc_type if not provided
        if not doc_types or len(doc_types) == 0:
            logger.info(f"No doc_types provided, using default 'document' for {len(files)} files")
            doc_types = ["document"] * len(files)
        
        if len(files) != len(doc_types):
            error_msg = f"Files ({len(files)}) and doc_types ({len(doc_types)}) length mismatch"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        file_list = []
        temp_files = []
        
        try:
            # Save all files to temp location
            for i, file in enumerate(files):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    content = await file.read()
                    tmp.write(content)
                    temp_files.append(tmp.name)
                    logger.debug(f"File {i+1}: {file.filename} → {tmp.name}")
                    
                    file_list.append({
                        'path': tmp.name,
                        'filename': file.filename,
                        'doc_type': doc_types[i],
                        'date': dates[i] if i < len(dates) else '',
                        'revision': revisions[i] if i < len(revisions) else 'v1'
                    })
            
            logger.info(f"Prepared {len(file_list)} files for ingestion")
            # Ingest batch
            result = ingest_multiple_documents(file_list)
            logger.info(f"Batch ingestion successful: {result}")
            
            return BatchIngestionResponse(**result)
            
        finally:
            # Clean up temp files
            for tmp_path in temp_files:
                Path(tmp_path).unlink(missing_ok=True)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in batch ingest endpoint: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/query", response_model=RFIAnswer, tags=["RFI Agent - Query"])
async def query_rfi(
    question: str,
    doc_type_filter: Optional[str] = None
) -> RFIAnswer:
    """
    Answer an RFI question using RAG with Cerebras LLM.
    
    Args:
        question: The RFI question
        doc_type_filter: Optional document type filter
        
    Returns:
        Complete answer with citations and similar past RFIs
    """
    try:
        result = answer_question(question, doc_type_filter)
        
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
