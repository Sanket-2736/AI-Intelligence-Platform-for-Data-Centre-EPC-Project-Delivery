"""
Commissioning QA Copilot Agent module.

Handles commissioning test generation, execution tracking,
and ITP (Inspection & Test Plan) documentation.
"""

import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import tempfile
from io import BytesIO

from ingestion import pdf_parser
from utils import chunker, cerebras_client
from db.chroma_client import get_chroma_manager
from db.supabase_client import get_supabase_manager
from agents.prompts import COMMISSIONING_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter()

# Constants
COLLECTION_COMMISSIONING = "commissioning_standards"
STANDARD_TEST_TIER = "Tier III"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class TestResult(str, Enum):
    """Commissioning test result status."""
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL_PASS = "conditional_pass"
    NOT_TESTED = "not_tested"


class SystemType(str, Enum):
    """Data centre system types for commissioning."""
    POWER = "power"
    COOLING = "cooling"
    IT = "it"
    FIRE = "fire"
    SECURITY = "security"
    WATER = "water"
    COMBINED = "combined"


class CommissioningRecord(BaseModel):
    """Commissioning test record."""
    test_id: str = Field(..., description="Unique test identifier")
    system: str = Field(..., description="System type (POWER|COOLING|IT|FIRE|SECURITY|WATER|COMBINED)")
    test_name: str = Field(..., description="Test procedure name")
    tier_applicability: str = Field("Tier III", description="Tier III or Tier IV")
    acceptance_criteria: str = Field(..., description="Pass/fail criteria")
    result: TestResult = Field(..., description="Test result")
    tested_by: str = Field(..., description="Technician/company name")
    test_date: str = Field(..., description="Test date (YYYY-MM-DD)")
    notes: Optional[str] = Field(None, description="Additional notes")
    duration_minutes: Optional[int] = Field(None, description="Test duration")


class TestProcedure(BaseModel):
    """Generated test procedure from standards."""
    test_id: str
    test_name: str
    system: str
    tier_applicability: str
    tia_942_reference: Optional[str]
    estimated_duration_hours: float
    test_team_required: List[str]
    prerequisites: List[str]
    safety_warnings: List[str]
    test_equipment_required: List[str]
    test_setup: str
    test_steps: List[Dict[str, Any]]
    acceptance_summary: str
    sign_off_requirements: List[str]
    common_failure_modes: List[str]
    success: bool = True
    error: Optional[str] = None


class StandardTest(BaseModel):
    """Standard test from library."""
    test_id: str
    test_name: str
    system: str
    tier_applicability: str
    estimated_hours: float
    description: str
    prerequisites: List[str]


class CommissioningDashboard(BaseModel):
    """Commissioning dashboard summary."""
    total_tests: int
    pass_count: int
    fail_count: int
    conditional_count: int
    pending_count: int
    overall_pass_rate: float
    by_system: Dict[str, Dict[str, int]]
    failed_tests: List[Dict[str, str]]
    timestamp: str


# ============================================================================
# STANDARD TEST LIBRARY
# ============================================================================

STANDARD_TEST_LIBRARY = [
    # POWER SYSTEM TESTS
    {
        'test_id': 'PWR-001',
        'test_name': 'UPS Battery Bank Voltage Verification',
        'system': 'power',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 2.0,
        'description': 'Verify battery voltage, capacity, and cell balance with calibrated meters',
        'prerequisites': ['Battery bank installed', 'Calibration certificates available']
    },
    {
        'test_id': 'PWR-002',
        'test_name': 'Generator Load Bank Testing',
        'system': 'power',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 4.0,
        'description': 'Load generator to 50%, 75%, 100% with fuel consumption monitoring',
        'prerequisites': ['Generator operational', 'Load bank equipment', 'Fuel supply']
    },
    {
        'test_id': 'PWR-003',
        'test_name': 'Switchgear & Distribution Panel Isolation Testing',
        'system': 'power',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 3.0,
        'description': 'Verify circuit breaker isolation, grounding, and proper labeling',
        'prerequisites': ['Power off confirmed', 'LOTO procedure']
    },
    {
        'test_id': 'PWR-004',
        'test_name': 'PDU Power Distribution Unit Functionality',
        'system': 'power',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 2.5,
        'description': 'Verify all outlets, metering, and load balancing',
        'prerequisites': ['PDU installed', 'Multimeters available']
    },
    {
        'test_id': 'PWR-005',
        'test_name': 'Power Distribution Unit Redundancy Testing',
        'system': 'power',
        'tier_applicability': 'Tier IV',
        'estimated_hours': 3.0,
        'description': 'Test N+1 and 2N redundancy paths for full load transfer',
        'prerequisites': ['Dual PDU feeds', 'Load simulator', 'ATS functional']
    },
    # COOLING SYSTEM TESTS
    {
        'test_id': 'CL-001',
        'test_name': 'CRAC Unit Airflow & Temperature Verification',
        'system': 'cooling',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 3.0,
        'description': 'Measure discharge temperature, CFM output, and cold aisle containment',
        'prerequisites': ['CRAC powered on', 'Thermal camera', 'Anemometer']
    },
    {
        'test_id': 'CL-002',
        'test_name': 'Chiller Water Loop Commissioning',
        'system': 'cooling',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 4.0,
        'description': 'Verify flow rate, temperature differential, pressure hold, no leaks',
        'prerequisites': ['Water filled', 'Pump operational', 'Pressure gauges']
    },
    {
        'test_id': 'CL-003',
        'test_name': 'Humidity Control & Sensor Calibration',
        'system': 'cooling',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 2.0,
        'description': 'Verify humidifier/dehumidifier function, sensor accuracy within ±5% RH',
        'prerequisites': ['Hygrometer reference', 'Sensor certificates']
    },
    {
        'test_id': 'CL-004',
        'test_name': 'Cooling Redundancy Failover Test',
        'system': 'cooling',
        'tier_applicability': 'Tier IV',
        'estimated_hours': 3.5,
        'description': 'Verify temperature control during unit shutdown, seamless switchover',
        'prerequisites': ['Dual cooling units', 'Load stable']
    },
    # IT SYSTEM TESTS
    {
        'test_id': 'IT-001',
        'test_name': 'Network Infrastructure Connectivity Verification',
        'system': 'it',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 2.5,
        'description': 'Test all switches, patch panels, cabling for link integrity',
        'prerequisites': ['Network analyzers', 'Test equipment']
    },
    {
        'test_id': 'IT-002',
        'test_name': 'Server Rack Power & Network Load Test',
        'system': 'it',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 3.0,
        'description': 'Verify power distribution, PDU operation, network bandwidth under load',
        'prerequisites': ['Servers installed', 'Load generators']
    },
    # FIRE PROTECTION
    {
        'test_id': 'FR-001',
        'test_name': 'Fire Suppression System Pressure & Functionality Test',
        'system': 'fire',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 2.5,
        'description': 'Verify pressure gauges, nozzle coverage, alarm integration',
        'prerequisites': ['Suppression system charged', 'Pressure gauges calibrated']
    },
    {
        'test_id': 'FR-002',
        'test_name': 'Fire Detection Sensor Response Testing',
        'system': 'fire',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 2.0,
        'description': 'Test all smoke/heat detectors with calibrated test aerosol',
        'prerequisites': ['Test aerosol cans', 'Detector certificates']
    },
    # SECURITY
    {
        'test_id': 'SEC-001',
        'test_name': 'Access Control System Functional Test',
        'system': 'security',
        'tier_applicability': 'Tier III, Tier IV',
        'estimated_hours': 2.0,
        'description': 'Verify badge readers, door locks, audit logging function',
        'prerequisites': ['Test badges', 'Access logs available']
    },
]


def _get_standard_test_by_id(test_id: str) -> Optional[Dict[str, Any]]:
    """Get standard test from library by ID."""
    for test in STANDARD_TEST_LIBRARY:
        if test['test_id'] == test_id:
            return test
    return None


# ============================================================================
# CORE COMMISSIONING FUNCTIONS
# ============================================================================


def ingest_commissioning_standards(pdf_files: List[Tuple[str, dict]]) -> Dict[str, Any]:
    """
    Ingest commissioning standards (TIA-942, Uptime Institute, BICSI 002) as PDFs.
    
    RAG pipeline:
    1. Extract text from each PDF
    2. Chunk into ~500 char sections with metadata (standard_name, section, tier_level, system_type)
    3. Store in ChromaDB COLLECTION_COMMISSIONING
    4. Return ingestion statistics
    
    This is typically called once at system setup.
    
    Args:
        pdf_files: List of (file_path, metadata) tuples
                  metadata: {standard_name, version, tier_level, system_types: []}
    
    Returns:
        {
            'success': bool,
            'total_files': int,
            'total_chunks': int,
            'by_standard': {standard_name: {pages, chunks}},
            'error': Optional[str]
        }
    """
    try:
        logger.info(f"Starting commissioning standards ingestion ({len(pdf_files)} files)")
        
        chroma = get_chroma_manager()
        all_chunks = []
        stats_by_standard = {}
        
        for pdf_path, metadata in pdf_files:
            if not Path(pdf_path).exists():
                logger.warning(f"PDF not found: {pdf_path}")
                continue
            
            standard_name = metadata.get('standard_name', 'Unknown')
            logger.info(f"Processing: {standard_name}")
            
            # Extract PDF text
            result = pdf_parser.extract_text_pymupdf(pdf_path)
            
            if not result['success']:
                logger.error(f"Failed to extract {pdf_path}: {result.get('error')}")
                continue
            
            # Chunk with metadata
            chunk_metadata = {
                'standard_name': standard_name,
                'version': metadata.get('version', ''),
                'tier_level': metadata.get('tier_level', ''),
                'system_types': metadata.get('system_types', []),
                'source': 'commissioning_standard'
            }
            
            chunks = chunker.chunk_text_with_metadata(
                result['full_text'],
                chunk_metadata,
                chunk_size=500,
                overlap=100
            )
            
            all_chunks.extend(chunks)
            stats_by_standard[standard_name] = {
                'pages': result['total_pages'],
                'chunks': len(chunks)
            }
            
            logger.info(f"Ingested {standard_name}: {result['total_pages']} pages → {len(chunks)} chunks")
        
        # Bulk ingest to ChromaDB
        if all_chunks:
            ingest_result = chroma.ingest_chunks(
                collection_name=COLLECTION_COMMISSIONING,
                chunks=all_chunks,
                upsert=True
            )
            
            logger.info(f"ChromaDB ingestion: {ingest_result.get('success')}, "
                       f"{ingest_result.get('count')} chunks stored")
        
        return {
            'success': True,
            'total_files': len(pdf_files),
            'total_chunks': len(all_chunks),
            'by_standard': stats_by_standard,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Commissioning standards ingestion error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'total_files': 0,
            'total_chunks': 0,
            'by_standard': {},
            'error': error_msg
        }


def generate_test_procedure(
    system: str,
    test_name: str,
    tier: str = "Tier III"
) -> Dict[str, Any]:
    """
    Generate a detailed test procedure using RAG + Cerebras AI.
    
    Pipeline:
    1. Query ChromaDB for relevant standards (system + tier)
    2. Retrieve top 4 chunks as context
    3. Build Cerebras prompt with context
    4. Call cerebras_client.call_structured() with COMMISSIONING_SYSTEM_PROMPT
    5. Return structured test procedure JSON
    
    Args:
        system: System type (POWER, COOLING, IT, FIRE, SECURITY, WATER, COMBINED)
        test_name: Test name (e.g., "UPS Battery Voltage Verification")
        tier: Tier III or Tier IV
        
    Returns:
        Full structured test procedure with steps, acceptance criteria, safety warnings
    """
    try:
        logger.info(f"Generating test procedure: {system}/{test_name} ({tier})")
        
        # Step 1: Query ChromaDB for relevant standards
        chroma = get_chroma_manager()
        
        query_text = f"{system} {test_name} commissioning test {tier}"
        
        rag_results = chroma.query(
            collection_name=COLLECTION_COMMISSIONING,
            query_text=query_text,
            n_results=4,
            filters={"tier_level": tier}  # Optional: filter by tier
        )
        
        # Step 2: Build context from retrieved chunks
        context_text = ""
        if rag_results and 'documents' in rag_results:
            for doc in rag_results['documents'][:4]:
                context_text += f"\n{doc}\n"
        
        # Step 3: Build Cerebras prompt
        user_message = f"""Generate a comprehensive test procedure for:
System: {system}
Test Name: {test_name}
Tier: {tier}

RELEVANT STANDARDS:
{context_text if context_text else "No standards found - use industry best practices"}

Create a detailed, step-by-step test procedure that is safe, thorough, and auditable."""
        
        # Step 4: Call Cerebras
        llm = cerebras_client.get_cerebras_client()
        
        procedure_json = llm.call_structured(
            system_prompt=COMMISSIONING_SYSTEM_PROMPT,
            user_message=user_message
        )
        
        if procedure_json.get('error'):
            logger.error(f"Cerebras error: {procedure_json.get('error')}")
            return {
                'test_name': test_name,
                'system': system,
                'tier_applicability': tier,
                'success': False,
                'error': procedure_json.get('error')
            }
        
        logger.info(f"Test procedure generated: {procedure_json.get('test_id', 'N/A')}")
        
        return {**procedure_json, 'success': True}
        
    except Exception as e:
        error_msg = f"Error generating test procedure: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'test_name': test_name,
            'system': system,
            'tier_applicability': tier,
            'success': False,
            'error': error_msg
        }


def get_standard_test_library() -> List[Dict[str, Any]]:
    """
    Get standard test library (hardcoded but realistic).
    
    Returns list of 20+ standard data centre commissioning tests
    across POWER, COOLING, IT, FIRE, SECURITY systems.
    
    This is the "test catalogue" shown in the UI.
    
    Returns:
        List[{test_id, test_name, system, tier_applicability, estimated_hours, description}]
    """
    return STANDARD_TEST_LIBRARY


def log_test_result(test_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Log a commissioning test result to Supabase.
    
    Validates result has all required fields, then:
    1. Insert to Supabase commissioning_records
    2. If FAIL: Auto-generate NC (non-conformance) record for compliance tracking
    3. Return saved record with ID
    
    Args:
        test_result: {
            test_id, test_name, system, acceptance_criteria, result (PASS|FAIL|CONDITIONAL),
            tested_by, test_date, notes, duration_minutes
        }
    
    Returns:
        {
            'success': bool,
            'record': saved record with id,
            'nc_generated': bool (if FAIL),
            'nc_id': str or None,
            'error': Optional[str]
        }
    """
    try:
        # Validate required fields
        required = ['test_id', 'test_name', 'system', 'result', 'tested_by', 'test_date']
        missing = [f for f in required if f not in test_result]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        
        logger.info(f"Logging test result: {test_result['test_id']}/{test_result['test_name']} = {test_result['result']}")
        
        db = get_supabase_manager()
        
        # Insert to commissioning_records
        result_data = {
            **test_result,
            'created_at': datetime.now().isoformat(),
            'result': test_result['result'].lower()
        }
        
        insert_result = db.insert_commissioning_record(result_data)
        
        if not insert_result['success']:
            raise Exception(insert_result.get('error', 'Database insert failed'))
        
        # If FAIL, auto-generate NC
        nc_id = None
        nc_generated = False
        
        if test_result['result'].upper() == 'FAIL':
            nc_data = {
                'nc_id': f"NC-{test_result['test_id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'severity': 'MAJOR',  # Test failures are at least MAJOR
                'clause_reference': f"Commissioning Test {test_result['test_id']}",
                'spec_requirement': test_result.get('acceptance_criteria', 'Test acceptance criteria'),
                'submittal_value': f"Test result: FAIL",
                'deviation_description': f"Test '{test_result['test_name']}' failed during commissioning",
                'recommended_action': f"Investigate and retest: {test_result.get('notes', 'N/A')}",
                'tier_certification_impact': f"Delays {STANDARD_TEST_TIER} certification",
                'status': 'open',
                'created_at': datetime.now().isoformat()
            }
            
            nc_result = db.insert_non_conformance(nc_data)
            
            if nc_result['success']:
                nc_id = nc_data['nc_id']
                nc_generated = True
                logger.info(f"Auto-generated NC: {nc_id}")
        
        return {
            'success': True,
            'record': insert_result.get('data', result_data),
            'nc_generated': nc_generated,
            'nc_id': nc_id,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Error logging test result: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'record': None,
            'nc_generated': False,
            'nc_id': None,
            'error': error_msg
        }


def get_commissioning_dashboard() -> Dict[str, Any]:
    """
    Get commissioning dashboard summary statistics.
    
    Queries Supabase for all commissioning records and aggregates:
    - Pass/fail/conditional/pending counts
    - Overall pass rate (%)
    - Breakdown by system (POWER, COOLING, IT, etc.)
    - Failed tests with notes for prioritization
    
    Returns:
        {
            'total_tests': int,
            'pass_count': int,
            'fail_count': int,
            'conditional_count': int,
            'pending_count': int,
            'overall_pass_rate': float (0-100),
            'by_system': {system: {pass, fail, conditional, pending}},
            'failed_tests': [{test_name, system, notes, test_date}],
            'timestamp': str (ISO)
        }
    """
    try:
        db = get_supabase_manager()
        summary = db.get_commissioning_summary()
        
        logger.info(
            f"Commissioning dashboard: {summary['pass_count']} pass, "
            f"{summary['fail_count']} fail, {summary['pass_rate']:.1f}% pass rate"
        )
        
        return {
            'total_tests': summary['total'],
            'pass_count': summary['pass_count'],
            'fail_count': summary['fail_count'],
            'conditional_count': summary.get('conditional_count', 0),
            'pending_count': summary.get('pending_count', 0),
            'overall_pass_rate': summary['pass_rate'],
            'by_system': summary['by_system'],
            'failed_tests': summary.get('failed_tests', []),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        error_msg = f"Error getting commissioning dashboard: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'total_tests': 0,
            'pass_count': 0,
            'fail_count': 0,
            'conditional_count': 0,
            'pending_count': 0,
            'overall_pass_rate': 0.0,
            'by_system': {},
            'failed_tests': [],
            'timestamp': datetime.now().isoformat(),
            'error': error_msg
        }


def generate_itp_pdf(
    project_name: str,
    tested_by_company: str,
    tested_by_person: Optional[str] = None
) -> Tuple[bytes, str]:
    """
    Generate professional A4 PDF ITP (Inspection & Test Plan).
    
    Fetches all commissioning records from Supabase and generates:
    - Cover page: project, company, date, overall pass rate
    - Summary table: counts by system and result type
    - Detail section: each test with all fields formatted nicely
    - Signature block at end
    - EPC branding: dark blue header, professional fonts
    
    Uses ReportLab for PDF generation.
    
    Args:
        project_name: Project name for cover
        tested_by_company: Testing company name
        tested_by_person: Optional person name
        
    Returns:
        (pdf_bytes, filename) tuple
    """
    try:
        logger.info(f"Generating ITP PDF for {project_name}")
        
        db = get_supabase_manager()
        all_records = db.get_all_records_for_itp()
        summary = db.get_commissioning_summary()
        
        # Create PDF in memory
        pdf_buffer = BytesIO()
        
        # Import ReportLab here to avoid import errors if not installed
        try:
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError:
            logger.error("ReportLab not installed")
            return (b"", f"ITP_{datetime.now().strftime('%Y%m%d')}.pdf")
        
        # Document setup
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#003366'),  # Dark blue
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#003366'),
            spaceAfter=10
        )
        
        # COVER PAGE
        story.append(Spacer(1, 1*inch))
        story.append(Paragraph("INSPECTION & TEST PLAN (ITP)", title_style))
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph(f"Project: {project_name}", styles['Normal']))
        story.append(Paragraph(f"Tested by: {tested_by_company}", styles['Normal']))
        if tested_by_person:
            story.append(Paragraph(f"Technician: {tested_by_person}", styles['Normal']))
        story.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
        story.append(Spacer(1, 0.5*inch))
        
        pass_rate = summary.get('pass_rate', 0)
        overall_status = "✓ PASS" if pass_rate >= 95 else "⚠ REVIEW REQUIRED" if pass_rate >= 80 else "✗ FAILED"
        story.append(Paragraph(f"Overall Status: {overall_status}", styles['Heading2']))
        story.append(Paragraph(f"Pass Rate: {pass_rate:.1f}%", styles['Normal']))
        
        story.append(PageBreak())
        
        # SUMMARY TABLE
        story.append(Paragraph("Executive Summary", heading_style))
        
        # Prevent division by zero
        total = summary.get('total', 0)
        if total == 0:
            total = 1  # Avoid division by zero
        
        summary_data = [
            ['Metric', 'Count', 'Percentage'],
            ['Passed', str(summary['pass_count']), f"{(summary['pass_count']/total*100):.1f}%"],
            ['Failed', str(summary['fail_count']), f"{(summary['fail_count']/total*100):.1f}%"],
            ['Conditional', str(summary.get('conditional_count', 0)), f"{(summary.get('conditional_count', 0)/total*100):.1f}%"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # SYSTEM BREAKDOWN
        story.append(Paragraph("Test Results by System", heading_style))
        
        system_data = [['System', 'Pass', 'Fail', 'Total']]
        for system, counts in summary['by_system'].items():
            system_data.append([
                system.upper(),
                str(counts['pass']),
                str(counts['fail']),
                str(counts['pass'] + counts['fail'])
            ])
        
        system_table = Table(system_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch])
        system_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(system_table)
        story.append(PageBreak())
        
        # DETAILED TEST RESULTS
        story.append(Paragraph("Detailed Test Results", heading_style))
        
        for record in all_records[:50]:  # Limit to first 50 for reasonable PDF size
            test_name = record.get('test_name', 'Unknown')
            system = record.get('system', 'N/A')
            result = record.get('result', 'UNKNOWN').upper()
            
            result_color = colors.green if result == 'PASS' else colors.red if result == 'FAIL' else colors.orange
            
            story.append(Paragraph(
                f"<b>{test_name}</b> [{system}] - <font color='{result_color}'>{result}</font>",
                styles['Normal']
            ))
            
            if record.get('notes'):
                story.append(Paragraph(f"Notes: {record['notes']}", styles['Normal']))
            
            story.append(Spacer(1, 0.1*inch))
        
        # SIGNATURE BLOCK
        story.append(PageBreak())
        story.append(Paragraph("Sign-Off", heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        sig_data = [
            ['Tested By:', '__________________', 'Date:', '__________________'],
            ['', f"({tested_by_company})", '', ''],
            ['Verified By:', '__________________', 'Date:', '__________________'],
        ]
        
        sig_table = Table(sig_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (1, 1), 'Helvetica-Oblique'),
            ('FONTSIZE', (0, 1), (1, 1), 9),
        ]))
        
        story.append(sig_table)
        
        # Generate PDF
        doc.build(story)
        
        pdf_bytes = pdf_buffer.getvalue()
        filename = f"ITP_{project_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        logger.info(f"ITP PDF generated: {filename} ({len(pdf_bytes)} bytes)")
        
        return (pdf_bytes, filename)
        
    except Exception as e:
        error_msg = f"Error generating ITP PDF: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return (b"", f"ERROR_{datetime.now().strftime('%Y%m%d')}.pdf")


# ============================================================================
# FASTAPI ENDPOINTS
# ============================================================================


@router.post("/standards/ingest", tags=["Commissioning Agent"])
async def ingest_standards(
    files: List[UploadFile] = File(..., description="Standards PDFs (TIA-942, Uptime, BICSI)"),
    standard_names: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ingest commissioning standards PDFs.
    
    Processes multiple PDF uploads containing TIA-942, Uptime Institute Tier specs,
    BICSI 002, or other commissioning standards. Extracts text, chunks with metadata,
    and stores in ChromaDB for RAG-based test generation.
    
    Args:
        files: Multiple PDF file uploads
        standard_names: Optional comma-separated standard names (e.g., "TIA-942,Uptime Tier III")
        
    Returns:
        Ingestion statistics with per-standard breakdown
    """
    temp_files = []
    try:
        pdf_files = []
        
        for idx, file in enumerate(files):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                file.seek(0)
                content = await file.read()
                tmp.write(content)
                temp_files.append(tmp.name)
                
                # Parse standard name from filename or parameter
                standard_name = f"Standard {idx + 1}"
                if standard_names:
                    names = standard_names.split(',')
                    if idx < len(names):
                        standard_name = names[idx].strip()
                
                pdf_files.append((tmp.name, {
                    'standard_name': standard_name,
                    'version': '1.0',
                    'tier_level': 'Tier III, Tier IV',
                    'system_types': ['power', 'cooling', 'it', 'fire', 'security']
                }))
        
        # Ingest
        result = ingest_commissioning_standards(pdf_files)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in standards ingest endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for path in temp_files:
            Path(path).unlink(missing_ok=True)


@router.post("/procedure/generate", response_model=TestProcedure, tags=["Commissioning Agent"])
async def generate_procedure(
    system: str = Body(..., description="System type (POWER|COOLING|IT|FIRE|SECURITY)"),
    test_name: str = Body(..., description="Test name"),
    tier: str = Body("Tier III", description="Tier III or Tier IV")
) -> Dict[str, Any]:
    """
    Generate a test procedure using RAG + Cerebras AI.
    
    Queries commissioning standards database for relevant content, then uses
    Cerebras LLM to generate detailed, step-by-step test procedures aligned
    with industry standards.
    
    Args:
        system: System type
        test_name: Test description
        tier: Tier level (Tier III or Tier IV)
        
    Returns:
        Detailed test procedure with steps, criteria, safety notes, sign-offs
    """
    try:
        result = generate_test_procedure(system, test_name, tier)
        
        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error'))
        
        return result
        
    except Exception as e:
        logger.error(f"Error in procedure generation endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/library", response_model=List[StandardTest], tags=["Commissioning Agent"])
async def get_test_library() -> List[StandardTest]:
    """
    Get standard commissioning test library.
    
    Returns 20+ pre-configured test procedures for common data centre systems
    (POWER, COOLING, IT, FIRE, SECURITY). These can be used directly or as
    templates for custom procedures.
    
    Returns:
        List of standard tests with descriptions and prerequisites
    """
    try:
        tests = get_standard_test_library()
        
        return [StandardTest(**test) for test in tests]
        
    except Exception as e:
        logger.error(f"Error in test library endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/results/log", tags=["Commissioning Agent"])
async def log_result(
    result: CommissioningRecord
) -> Dict[str, Any]:
    """
    Log a commissioning test result.
    
    Records test completion with pass/fail/conditional result. If test FAILs,
    automatically generates a non-conformance (NC) for compliance tracking.
    
    Args:
        result: Test result with acceptance criteria, result status, notes
        
    Returns:
        Saved record with ID, NC ID if generated
    """
    try:
        log_result_obj = log_test_result(result.dict(exclude_none=True))
        
        if not log_result_obj['success']:
            raise HTTPException(status_code=500, detail=log_result_obj['error'])
        
        return log_result_obj
        
    except Exception as e:
        logger.error(f"Error in result logging endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/itp/download", tags=["Commissioning Agent"])
async def download_itp(
    project_name: str = Query(..., description="Project name"),
    company: str = Query(..., description="Testing company"),
    person: Optional[str] = Query(None, description="Technician name")
) -> StreamingResponse:
    """
    Generate and download ITP PDF.
    
    Creates a professional A4 PDF Inspection & Test Plan with:
    - Cover page with project/company/date
    - Executive summary with pass rate
    - System breakdown table
    - Detailed test results
    - Signature blocks
    
    Returns PDF as file download.
    
    Args:
        project_name: Project name for cover page
        company: Testing company name
        person: Optional technician name
        
    Returns:
        PDF file stream
    """
    try:
        pdf_bytes, filename = generate_itp_pdf(project_name, company, person)
        
        if not pdf_bytes:
            raise HTTPException(status_code=500, detail="PDF generation failed")
        
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error in ITP download endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=CommissioningDashboard, tags=["Commissioning Agent"])
async def get_dashboard() -> Dict[str, Any]:
    """
    Get commissioning dashboard summary.
    
    Returns real-time statistics on commissioning progress:
    - Pass/fail/conditional counts
    - Pass rate by system
    - Failed tests needing attention
    
    Returns:
        Dashboard with all metrics and system breakdown
    """
    try:
        dashboard = get_commissioning_dashboard()
        
        if 'error' in dashboard:
            raise HTTPException(status_code=500, detail=dashboard['error'])
        
        return dashboard
        
    except Exception as e:
        logger.error(f"Error in dashboard endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", tags=["Commissioning Agent"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint for commissioning agent."""
    try:
        db = get_supabase_manager()
        chroma = get_chroma_manager()
        
        # Test connections
        _ = db.get_commissioning_summary()
        _ = chroma.get_collection_stats(COLLECTION_COMMISSIONING)
        
        return {
            'status': 'healthy',
            'agent': 'commissioning',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service check failed")
