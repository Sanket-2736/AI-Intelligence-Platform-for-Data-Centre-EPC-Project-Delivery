"""
Specification & Quality Compliance Agent module.
Analyzes vendor submittals against master specifications, identifies non-conformances,
and recommends corrective actions using Cerebras LLM.
Production-quality with comprehensive error handling and Supabase integration.
"""

import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from pydantic import BaseModel
import tempfile
import uuid

from ingestion import pdf_parser
from utils import chunker, cerebras_client
from db.chroma_client import get_chroma_manager, COLLECTION_SPECS
from db.supabase_client import get_supabase_manager
from agents.prompts import COMPLIANCE_SYSTEM_PROMPT, DEVIATION_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class SeverityLevel(str, Enum):
    """Severity levels for non-conformances."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "informational"


class NonConformanceRecord(BaseModel):
    """Model for a single non-conformance finding."""
    id: str
    severity: SeverityLevel
    clause_reference: str
    spec_requirement: str
    submittal_value: str
    deviation_description: str
    recommended_action: str
    tier_certification_impact: str


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""
    summary: str
    overall_status: str  # COMPLIANT|MINOR_DEVIATIONS|MAJOR_DEVIATIONS|NON_COMPLIANT
    compliance_score: int  # 0-100
    total_findings: int
    critical_issues: int
    findings: List[NonConformanceRecord]
    processing_time_ms: int
    success: bool
    error: Optional[str] = None


class ComplianceDashboard(BaseModel):
    """Dashboard summary statistics."""
    total_ncs: int
    open_critical: int
    open_major: int
    open_minor: int
    closed_count: int
    recent_critical: List[Dict[str, Any]]


class NCUpdateRequest(BaseModel):
    """Request to update non-conformance status."""
    resolution_notes: str
    closed_by: str


# ============================================================================
# CORE COMPLIANCE FUNCTIONS
# ============================================================================


def check_submittal_against_spec(
    submittal_path: str,
    spec_path: str,
    equipment_type: str = "general",
    project_code: str = "PRJ-001"
) -> Dict[str, Any]:
    """
    Check submittal compliance against specification.
    
    Full pipeline: extract documents, build context, call Cerebras, log findings.
    
    Args:
        submittal_path: Path to vendor submittal PDF
        spec_path: Path to master specification PDF
        equipment_type: Type of equipment (HVAC, electrical, power, etc.)
        project_code: Project identifier
        
    Returns:
        {
            'summary': str,
            'overall_status': str,
            'compliance_score': int,
            'total_findings': int,
            'critical_issues': int,
            'findings': List[Dict],
            'processing_time_ms': int,
            'success': bool,
            'error': Optional[str]
        }
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting compliance check for {equipment_type} submittal")
        
        # Step 1: Extract specification
        spec_result = pdf_parser.extract_text_with_ocr_fallback(spec_path)
        if not spec_result['success']:
            return {
                'summary': 'Failed to extract specification',
                'overall_status': 'ERROR',
                'compliance_score': 0,
                'total_findings': 0,
                'critical_issues': 0,
                'findings': [],
                'processing_time_ms': round((time.time() - start_time) * 1000, 0),
                'success': False,
                'error': spec_result.get('error')
            }
        
        # Step 2: Extract submittal
        submittal_result = pdf_parser.extract_text_with_ocr_fallback(submittal_path)
        if not submittal_result['success']:
            return {
                'summary': 'Failed to extract submittal',
                'overall_status': 'ERROR',
                'compliance_score': 0,
                'total_findings': 0,
                'critical_issues': 0,
                'findings': [],
                'processing_time_ms': round((time.time() - start_time) * 1000, 0),
                'success': False,
                'error': submittal_result.get('error')
            }
        
        # Step 3: Extract tables
        spec_tables = pdf_parser.extract_tables_pdfplumber(spec_path)
        submittal_tables = pdf_parser.extract_tables_pdfplumber(submittal_path)
        
        # Step 4: Smart truncation for context (fits in llama-3.3-70b)
        spec_text = spec_result['full_text'][:8000]
        submittal_text = submittal_result['full_text'][:6000]
        
        # Add tables as formatted text
        spec_text += "\n\nTABLES FROM SPECIFICATION:\n"
        for table in spec_tables[:3]:  # First 3 tables
            spec_text += _format_table(table) + "\n"
        
        submittal_text += "\n\nTABLES FROM SUBMITTAL:\n"
        for table in submittal_tables[:3]:  # First 3 tables
            submittal_text += _format_table(table) + "\n"
        
        # Step 5: Build user message
        user_message = f"""EQUIPMENT TYPE: {equipment_type}
PROJECT CODE: {project_code}

MASTER SPECIFICATION:
{spec_text}

VENDOR SUBMITTAL:
{submittal_text}

Please perform a detailed compliance analysis comparing the submittal to the specification."""
        
        # Step 6: Call Cerebras with structured output
        llm = cerebras_client.get_cerebras_client()
        
        result = llm.call_structured(
            system_prompt=COMPLIANCE_SYSTEM_PROMPT,
            user_message=user_message
        )
        
        if result.get('error'):
            logger.error(f"Cerebras error: {result.get('error')}")
            return {
                'summary': 'LLM analysis failed',
                'overall_status': 'ERROR',
                'compliance_score': 0,
                'total_findings': 0,
                'critical_issues': 0,
                'findings': [],
                'processing_time_ms': round((time.time() - start_time) * 1000, 0),
                'success': False,
                'error': result.get('error')
            }
        
        # Step 7: Log findings to Supabase
        db = get_supabase_manager()
        submittal_filename = Path(submittal_path).name
        spec_filename = Path(spec_path).name
        
        critical_count = 0
        
        for finding in result.get('findings', []):
            nc_id = f"NC-{project_code}-{uuid.uuid4().hex[:8].upper()}"
            
            nc_data = {
                'nc_id': nc_id,
                'severity': finding.get('severity', 'minor').lower(),
                'clause_ref': finding.get('clause_reference', ''),
                'description': finding.get('deviation_description', ''),
                'submittal_file': submittal_filename,
                'spec_file': spec_filename,
                'recommended_action': finding.get('recommended_action', ''),
                'status': 'open'
            }
            
            db.insert_non_conformance(nc_data)
            
            if finding.get('severity', '').lower() == 'critical':
                critical_count += 1
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Compliance check complete: {result.get('overall_status', 'UNKNOWN')}, "
            f"score: {result.get('compliance_score', 0)}, "
            f"findings: {result.get('total_findings', 0)}"
        )
        
        return {
            'summary': result.get('summary', ''),
            'overall_status': result.get('overall_status', 'UNKNOWN'),
            'compliance_score': result.get('compliance_score', 0),
            'total_findings': result.get('total_findings', 0),
            'critical_issues': critical_count,
            'findings': result.get('findings', []),
            'processing_time_ms': round(processing_time_ms, 0),
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Compliance check error: {str(e)}"
        logger.error(error_msg)
        return {
            'summary': 'Compliance check failed',
            'overall_status': 'ERROR',
            'compliance_score': 0,
            'total_findings': 0,
            'critical_issues': 0,
            'findings': [],
            'processing_time_ms': round((time.time() - start_time) * 1000, 0),
            'success': False,
            'error': error_msg
        }


def check_submittal_via_rag(
    submittal_path: str,
    equipment_type: str,
    spec_collection: str = "specifications"
) -> Dict[str, Any]:
    """
    Check submittal using RAG against ingested specification collection.
    
    For when specification is already in ChromaDB.
    
    Args:
        submittal_path: Path to submittal PDF
        equipment_type: Equipment type
        spec_collection: ChromaDB collection name
        
    Returns:
        Compliance check result
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting RAG-based compliance check for {equipment_type}")
        
        # Extract submittal
        submittal_result = pdf_parser.extract_text_with_ocr_fallback(submittal_path)
        if not submittal_result['success']:
            return {
                'summary': 'Failed to extract submittal',
                'overall_status': 'ERROR',
                'compliance_score': 0,
                'total_findings': 0,
                'critical_issues': 0,
                'findings': [],
                'processing_time_ms': round((time.time() - start_time) * 1000, 0),
                'success': False,
                'error': submittal_result.get('error')
            }
        
        submittal_text = submittal_result['full_text'][:6000]
        
        # Query ChromaDB for relevant spec sections
        chroma = get_chroma_manager()
        
        # Split submittal into sections and query each
        sections = submittal_text.split('\n\n')[:5]  # First 5 sections
        all_findings = []
        total_score = 0
        
        for section_idx, section in enumerate(sections):
            if len(section) < 100:
                continue
            
            # Search for relevant spec clauses
            search_result = chroma.query(
                collection_name=COLLECTION_SPECS,
                query_text=section[:300],  # First 300 chars of section
                n_results=3
            )
            
            retrieved_specs = search_result.get('results', [])
            
            if not retrieved_specs:
                continue
            
            # Build context
            context = "RELEVANT SPECIFICATION CLAUSES:\n"
            for i, spec_chunk in enumerate(retrieved_specs):
                context += f"\n[SPEC {i+1}]:\n{spec_chunk['text'][:400]}\n"
            
            # Analyze this section
            section_prompt = f"""SUBMITTAL SECTION:
{section[:500]}

{context}

Analyze this submittal section for compliance with the specification clauses above."""
            
            llm = cerebras_client.get_cerebras_client()
            
            section_result = llm.call_structured(
                system_prompt=COMPLIANCE_SYSTEM_PROMPT,
                user_message=section_prompt
            )
            
            if not section_result.get('error'):
                all_findings.extend(section_result.get('findings', []))
                total_score += section_result.get('compliance_score', 0)
        
        # Aggregate results
        avg_score = round(total_score / max(len(sections), 1), 0)
        critical_count = sum(1 for f in all_findings if f.get('severity', '').lower() == 'critical')
        
        # Determine overall status
        if critical_count > 0:
            overall_status = 'NON_COMPLIANT'
        elif len([f for f in all_findings if f.get('severity', '').lower() in ['critical', 'major']]) > 0:
            overall_status = 'MAJOR_DEVIATIONS'
        elif len([f for f in all_findings if f.get('severity', '').lower() == 'minor']) > 0:
            overall_status = 'MINOR_DEVIATIONS'
        else:
            overall_status = 'COMPLIANT'
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return {
            'summary': f'RAG-based analysis: {overall_status}',
            'overall_status': overall_status,
            'compliance_score': int(avg_score),
            'total_findings': len(all_findings),
            'critical_issues': critical_count,
            'findings': all_findings,
            'processing_time_ms': round(processing_time_ms, 0),
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"RAG compliance check error: {str(e)}"
        logger.error(error_msg)
        return {
            'summary': 'RAG compliance check failed',
            'overall_status': 'ERROR',
            'compliance_score': 0,
            'total_findings': 0,
            'critical_issues': 0,
            'findings': [],
            'processing_time_ms': round((time.time() - start_time) * 1000, 0),
            'success': False,
            'error': error_msg
        }


def ingest_master_spec(
    spec_path: str,
    spec_name: str,
    equipment_category: str
) -> Dict[str, Any]:
    """
    Ingest master specification into ChromaDB for RAG.
    
    Args:
        spec_path: Path to specification PDF
        spec_name: Name of specification
        equipment_category: Category (HVAC, electrical, power, etc.)
        
    Returns:
        Ingestion stats
    """
    try:
        logger.info(f"Ingesting spec: {spec_name}")
        
        # Extract spec
        spec_result = pdf_parser.extract_text_with_ocr_fallback(spec_path)
        if not spec_result['success']:
            return {
                'success': False,
                'error': spec_result.get('error'),
                'chunks_ingested': 0
            }
        
        pages = spec_result.get('pages', [])
        
        # Create metadata
        metadata = {
            'spec_name': spec_name,
            'equipment_category': equipment_category,
            'type': 'master_spec',
            'doc_type': 'spec'
        }
        
        # Chunk by page
        chunks = chunker.chunk_pdf_by_page(pages, metadata)
        
        # Add summary
        summary_chunk = chunker.create_document_summary_chunk(
            spec_result.get('full_text', ''),
            metadata
        )
        if summary_chunk:
            chunks.append(summary_chunk)
        
        # Ingest
        chroma = get_chroma_manager()
        ingest_result = chroma.ingest_chunks(COLLECTION_SPECS, chunks)
        
        logger.info(f"Spec ingested: {ingest_result['ingested']} chunks")
        
        return {
            'success': True,
            'spec_name': spec_name,
            'equipment_category': equipment_category,
            'chunks_ingested': ingest_result['ingested'],
            'pages_processed': len(pages)
        }
        
    except Exception as e:
        error_msg = f"Error ingesting spec: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'chunks_ingested': 0
        }


def get_nc_dashboard() -> Dict[str, Any]:
    """
    Get compliance dashboard summary.
    
    Returns:
        Dashboard with stats and recent critical NCs
    """
    try:
        db = get_supabase_manager()
        
        # Get summary stats
        stats = db.get_nc_summary_stats()
        
        # Get open NCs
        open_ncs = db.get_all_non_conformances(status='open')
        
        # Find recent critical
        recent_critical = [nc for nc in open_ncs if nc.get('severity', '').lower() == 'critical'][:5]
        
        return {
            'total_ncs': stats.get('total', 0),
            'open_critical': stats.get('by_status', {}).get('open', 0),  # Will refine
            'open_major': 0,  # Detailed stats
            'open_minor': 0,
            'closed_count': stats.get('by_status', {}).get('closed', 0),
            'recent_critical': recent_critical
        }
        
    except Exception as e:
        logger.error(f"Error getting NC dashboard: {str(e)}")
        return {
            'total_ncs': 0,
            'open_critical': 0,
            'open_major': 0,
            'open_minor': 0,
            'closed_count': 0,
            'recent_critical': []
        }


def close_non_conformance(
    nc_id: str,
    resolution_notes: str,
    closed_by: str
) -> Dict[str, Any]:
    """
    Close a non-conformance.
    
    Args:
        nc_id: Non-conformance ID
        resolution_notes: How it was resolved
        closed_by: Who closed it
        
    Returns:
        Updated NC record
    """
    try:
        db = get_supabase_manager()
        
        result = db.update_nc_status(
            nc_id=nc_id,
            status='closed',
            resolution=resolution_notes
        )
        
        logger.info(f"NC {nc_id} closed")
        
        return result
        
    except Exception as e:
        logger.error(f"Error closing NC: {str(e)}")
        return {'success': False, 'error': str(e)}


def generate_ncr_report_text(nc_list: List[Dict[str, Any]]) -> str:
    """
    Generate professional NCR (Non-Conformance Report) narrative.
    
    Args:
        nc_list: List of non-conformance records
        
    Returns:
        Professional NCR narrative text
    """
    try:
        if not nc_list:
            return "No non-conformances to report."
        
        # Format NCs for LLM
        nc_text = "NON-CONFORMANCES TO SUMMARIZE:\n"
        for i, nc in enumerate(nc_list, 1):
            nc_text += f"\n{i}. {nc.get('nc_id')}: {nc.get('severity', 'UNKNOWN').upper()}\n"
            nc_text += f"   Clause: {nc.get('clause_ref')}\n"
            nc_text += f"   Issue: {nc.get('description')}\n"
            nc_text += f"   Recommendation: {nc.get('recommended_action')}\n"
        
        user_message = nc_text + "\n\nGenerate a professional, formal NCR narrative summary suitable for client submission."
        
        llm = cerebras_client.get_cerebras_client()
        
        report_text = llm.call(
            system_prompt="You are a professional technical report writer specializing in compliance documentation.",
            user_message=user_message,
            temperature=0.4,  # Slightly more narrative
            max_tokens=2000
        )
        
        return report_text
        
    except Exception as e:
        logger.error(f"Error generating NCR: {str(e)}")
        return f"Error generating report: {str(e)}"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _format_table(table: Dict[str, Any]) -> str:
    """Format extracted table for LLM context."""
    try:
        result = f"Table from page {table.get('page')}:\n"
        
        # Add headers
        if table.get('headers'):
            result += " | ".join(str(h) for h in table['headers']) + "\n"
            result += "-" * 80 + "\n"
        
        # Add data rows (limit to first 5)
        for row in table.get('data', [])[:5]:
            result += " | ".join(str(cell) for cell in row) + "\n"
        
        if len(table.get('data', [])) > 5:
            result += f"... ({len(table['data']) - 5} more rows)\n"
        
        return result
    except Exception as e:
        logger.warning(f"Error formatting table: {str(e)}")
        return "Table extraction error"


# ============================================================================
# FASTAPI ENDPOINTS
# ============================================================================


@router.post("/check", response_model=ComplianceCheckResponse, tags=["Compliance Agent"])
async def check_submittal(
    submittal: UploadFile = File(...),
    master_spec: UploadFile = File(...),
    equipment_type: str = Form(...),
    project_code: str = Form(default="PRJ-001")
) -> ComplianceCheckResponse:
    """
    Check submittal compliance against specification.
    
    Args:
        submittal: Vendor submittal PDF
        master_spec: Master specification PDF
        equipment_type: Equipment type
        project_code: Project code
        
    Returns:
        Full compliance check with findings
    """
    temp_files = []
    try:
        # Save files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            submittal.seek(0)
            tmp.write(await submittal.read())
            submittal_path = tmp.name
            temp_files.append(submittal_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            master_spec.seek(0)
            tmp.write(await master_spec.read())
            spec_path = tmp.name
            temp_files.append(spec_path)
        
        result = check_submittal_against_spec(
            submittal_path=submittal_path,
            spec_path=spec_path,
            equipment_type=equipment_type,
            project_code=project_code
        )
        
        return ComplianceCheckResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in check endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for path in temp_files:
            Path(path).unlink(missing_ok=True)


@router.post("/spec/ingest", tags=["Compliance Agent"])
async def ingest_spec(
    spec_file: UploadFile = File(...),
    spec_name: str = Form(...),
    equipment_category: str = Form(...)
):
    """
    Ingest master specification for RAG.
    
    Args:
        spec_file: Specification PDF
        spec_name: Specification name
        equipment_category: Equipment category
        
    Returns:
        Ingestion confirmation
    """
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            spec_file.seek(0)
            tmp.write(await spec_file.read())
            temp_path = tmp.name
        
        result = ingest_master_spec(
            spec_path=temp_path,
            spec_name=spec_name,
            equipment_category=equipment_category
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in spec ingest endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@router.post("/check/rag", response_model=ComplianceCheckResponse, tags=["Compliance Agent"])
async def check_submittal_rag(
    submittal: UploadFile = File(...),
    equipment_type: str = Form(...)
) -> ComplianceCheckResponse:
    """
    Check submittal using ingested specifications (RAG).
    
    Args:
        submittal: Vendor submittal PDF
        equipment_type: Equipment type
        
    Returns:
        RAG-based compliance check
    """
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            submittal.seek(0)
            tmp.write(await submittal.read())
            temp_path = tmp.name
        
        result = check_submittal_via_rag(
            submittal_path=temp_path,
            equipment_type=equipment_type
        )
        
        return ComplianceCheckResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in RAG check endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@router.get("/dashboard", response_model=ComplianceDashboard, tags=["Compliance Agent"])
async def get_dashboard() -> ComplianceDashboard:
    """Get compliance dashboard."""
    try:
        result = get_nc_dashboard()
        return ComplianceDashboard(**result)
    except Exception as e:
        logger.error(f"Error in dashboard endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/nc/{nc_id}/close", tags=["Compliance Agent"])
async def close_nc(
    nc_id: str,
    request: NCUpdateRequest = Body(...)
):
    """
    Close a non-conformance.
    
    Args:
        nc_id: Non-conformance ID
        request: Resolution details
        
    Returns:
        Updated NC record
    """
    try:
        result = close_non_conformance(
            nc_id=nc_id,
            resolution_notes=request.resolution_notes,
            closed_by=request.closed_by
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error closing NC: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ncs", tags=["Compliance Agent"])
async def get_ncs(
    status: Optional[str] = None,
    severity: Optional[str] = None
):
    """
    Get non-conformances with optional filters.
    
    Args:
        status: OPEN|CLOSED|DEFERRED
        severity: CRITICAL|MAJOR|MINOR
        
    Returns:
        Filtered NC list
    """
    try:
        db = get_supabase_manager()
        
        ncs = db.get_all_non_conformances(status=status)
        
        if severity:
            ncs = [nc for nc in ncs if nc.get('severity', '').lower() == severity.lower()]
        
        return {'count': len(ncs), 'ncs': ncs}
        
    except Exception as e:
        logger.error(f"Error getting NCs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
